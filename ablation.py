#!/usr/bin/env python3
"""Retrieval ablation: run the same panel with retrieval ON and OFF and score it.

The claim under test is narrow and checkable: with retrieval ON, every seat report
must carry citations that resolve to sources the retriever actually returned; with
retrieval OFF there is nothing to resolve against, so grounding should collapse.
A run "degrades" when the OFF condition has a lower grounded rate than ON.

Usage:
    python ablation.py panel.json --base-url https://openrouter.ai/api/v1 \
        --model <model> --search-provider ddg --runs 1 --out ablation.json

Everything is scored by the same verifier the pipeline uses at run time. This
script does not judge prose quality; it reports whether citations are real.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import run_panel
from citations import extract_citations, verify_citations
from retrieval import Source


def score(result: dict) -> dict:
    """Count cited reports and unresolved citations for one run result."""
    reports = result.get("seat_reports") or []
    retrieval = result.get("retrieval") or {}
    sources = [Source.from_dict(s) for s in retrieval.get("sources") or []]
    cited = 0
    problems: list[str] = []
    for report in reports:
        text = report.get("findings") or ""
        if extract_citations(text):
            cited += 1
        problems += [
            f"{report.get('seat')}: {p}"
            for p in verify_citations(text, sources, require_citation=False)
        ]
    synthesis = (result.get("panel") or {}).get("synthesis") or ""
    problems += [f"judge: {p}" for p in verify_citations(synthesis, sources, require_citation=False)]

    return {
        "success": bool(result.get("success")),
        "code": result.get("code"),
        "error": result.get("error"),
        "seat_reports": len(reports),
        "cited_seat_reports": cited,
        "sources": len(sources),
        "citation_problems": problems,
        "grounded": bool(reports)
        and len(sources) > 0
        and cited == len(reports)
        and not problems,
    }


def run_condition(mode: str, base_args: list[str], runs: int) -> dict:
    results = []
    for _ in range(runs):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = run_panel.main([*base_args, "--retrieval", mode])
        raw = buffer.getvalue()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {
                "success": False,
                "code": "unparseable_output",
                "error": raw[-800:],
            }
        payload["exit_code"] = code
        results.append(score(payload))
    n = len(results)
    return {
        "runs": n,
        "exit_ok": sum(1 for r in results if r["success"]),
        "grounded_runs": sum(1 for r in results if r["grounded"]),
        "grounded_rate": round(sum(1 for r in results if r["grounded"]) / n, 3),
        "cited_seat_reports": sum(r["cited_seat_reports"] for r in results),
        "seat_reports": sum(r["seat_reports"] for r in results),
        "sources": sum(r["sources"] for r in results),
        "citation_problems": sum(len(r["citation_problems"]) for r in results),
        "detail": results,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Retrieval ON vs OFF ablation")
    ap.add_argument("input", help="panel JSON (topic, seats, lineup, judge)")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--api-key-env", default="STORM_API_KEY")
    ap.add_argument("--model", default=None)
    ap.add_argument("--temperature", type=float)
    ap.add_argument("--max-tokens", type=int, default=1200)
    ap.add_argument("--judge-max-tokens", type=int, default=8192)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--search-provider", default="ddg")
    ap.add_argument("--search-url", default=None)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--out", help="write the ablation JSON here")
    ap.add_argument("--allow-http-loopback", action="store_true")
    args = ap.parse_args(argv)

    base = [args.input, "--max-tokens", str(args.max_tokens),
            "--judge-max-tokens", str(args.judge_max_tokens), "--timeout", str(args.timeout),
            "--search-provider", args.search_provider, "--top-k", str(args.top_k)]
    if args.base_url:
        base += ["--base-url", args.base_url]
    if args.api_key_env:
        base += ["--api-key-env", args.api_key_env]
    if args.model:
        base += ["--model", args.model]
    if args.temperature is not None:
        base += ["--temperature", str(args.temperature)]
    if args.search_url:
        base += ["--search-url", args.search_url]
    if args.cache_dir:
        base += ["--cache-dir", args.cache_dir]
    if args.allow_http_loopback:
        base += ["--allow-http-loopback"]

    on = run_condition("on", base, args.runs)
    off = run_condition("off", base, args.runs)
    verdict = "degraded (retrieval OFF scores lower)" if off["grounded_rate"] < on["grounded_rate"] else "NOT degraded"
    report = {
        "claim": "retrieval-OFF degrades citation grounding",
        "verdict": verdict,
        "on": on,
        "off": off,
        "notes": (
            "grounded = run succeeded, retrieval returned sources, every seat report cited "
            "at least one [S#], and no citation failed verification. Retrieval OFF cannot "
            "be grounded by construction: there is nothing to verify against."
        ),
    }
    output = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(output)
    return 0 if verdict.startswith("degraded") else 1


if __name__ == "__main__":
    sys.exit(main())
