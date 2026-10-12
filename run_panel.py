#!/usr/bin/env python3
"""Run a storm panel without Hermes, against any OpenAI-compatible chat endpoint.

Same input shape as the ``storm_run_panel`` tool (topic, seats, lineup, judge) and the same
seat and judge prompts, imported from panel.py so the two never drift apart. Standard
library only.

There is no "active model" outside Hermes, so every model is named explicitly: either in
the input file (``lineup`` and ``judge``) or with ``--model`` for one model everywhere.
This script never picks a model for you.

Examples:
    python run_panel.py panel.json --base-url https://openrouter.ai/api/v1
    python run_panel.py panel.json --base-url http://localhost:11434/v1 --model <local-model>
    python run_panel.py panel.json --dry-run     # print the prompts, call nothing

Endpoint and key come from --base-url / STORM_BASE_URL and the env var named by
--api-key-env (default STORM_API_KEY). A lineup slot can override either with its own
"base_url" and "api_key_env", which lets one panel span several providers.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

from panel import SEAT_SCHEMA, _judge_prompt, _seat_prompt

JSON_HINT = (
    "\n\nReturn ONLY one JSON object, with no prose and no code fences, matching this "
    "schema:\n" + json.dumps(SEAT_SCHEMA)
)


def complete(messages, slot, defaults, temperature, max_tokens, timeout):
    """One chat completion. Returns (text, total_tokens_or_None)."""
    model = slot.get("model") or defaults["model"]
    base_url = (slot.get("base_url") or defaults["base_url"] or "").rstrip("/")
    if not model:
        raise ValueError(
            "No model given. Set a model on each lineup slot and on judge, or pass --model. "
            "This script never picks a model for you."
        )
    if not base_url:
        raise ValueError("No endpoint. Pass --base-url or set STORM_BASE_URL.")

    key_env = slot.get("api_key_env") or defaults["api_key_env"]
    key = os.environ.get(key_env, "")
    body = {"model": model, "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    headers = {"Content-Type": "application/json"}
    if key:  # local servers often need no key, so the header is optional
        headers["Authorization"] = f"Bearer {key}"

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"{model} at {base_url}: HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{model} at {base_url}: {exc.reason}") from None

    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"{model}: unexpected response shape") from None
    tokens = (data.get("usage") or {}).get("total_tokens")
    return text, model, tokens


def parse_json(text):
    """Parse the judge's JSON, tolerating a code fence. Falls back to raw text."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw": text}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("input", help="JSON file: topic, seats, optional lineup and judge")
    ap.add_argument("--base-url", default=os.environ.get("STORM_BASE_URL"))
    ap.add_argument("--api-key-env", default="STORM_API_KEY")
    ap.add_argument("--model", help="one model for every seat and the judge")
    ap.add_argument("--temperature", type=float)
    ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--out", help="write the JSON result here instead of stdout")
    ap.add_argument("--dry-run", action="store_true", help="print prompts, call nothing")
    args = ap.parse_args(argv)

    with open(args.input, encoding="utf-8") as fh:
        spec = json.load(fh)
    try:
        topic, seats = spec["topic"], spec["seats"]
    except KeyError as exc:
        sys.exit(f"Input is missing {exc}. Expected topic and seats.")

    defaults = {
        "model": args.model,
        "base_url": args.base_url,
        "api_key_env": args.api_key_env,
    }
    lineup = spec.get("lineup") or [{}]
    judge = spec.get("judge") or {}

    if args.dry_run:
        for seat in seats:
            print(f"=== seat: {seat['name']} ===")
            print(_seat_prompt(topic, seat)[0]["content"], end="\n\n")
        print("=== judge (reports are filled in at run time) ===")
        print(_judge_prompt(topic, []) + JSON_HINT)
        return 0

    reports, usage = [], []
    try:
        for seat in seats:
            for slot in lineup:
                text, model, tokens = complete(
                    _seat_prompt(topic, seat), slot, defaults,
                    args.temperature, args.max_tokens, args.timeout,
                )
                reports.append({"seat": seat["name"], "model": model, "findings": text})
                usage.append({"seat": seat["name"], "model": model, "tokens": tokens})
        text, _, _ = complete(
            [{"role": "user", "content": _judge_prompt(topic, reports) + JSON_HINT}],
            judge, defaults, args.temperature, args.max_tokens, args.timeout,
        )
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        return 1

    result = {
        "success": True,
        "panel": parse_json(text),
        "seat_reports": reports,  # raw reports, so you can validate before trusting the verdict
        "usage": usage,
    }
    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(output + "\n")
        print(f"Wrote {args.out}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
