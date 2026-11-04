"""Storm panel execution: per-seat multi-model fanout plus judge synthesis.

The agent passes the lineup inline (resolved from the human's MoA preset or
chosen ad hoc). The plugin never invents models. Every LLM call goes through
the host-owned ``ctx.llm`` lane, so the plugin never sees keys or tokens.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from citations import CitationError, format_sources, require_clean, verify_citations
from retrieval import RetrievalError, make_retriever

logger = logging.getLogger(__name__)

# The judge reads every seat report plus the topic, so it needs its own budget.
# Sharing the generation budget is what silently emptied the judge.
JUDGE_DEFAULT_MAX_TOKENS = 8192
MIN_JUDGE_MAX_TOKENS = 512


class PanelError(RuntimeError):
    """A run-stopping panel failure with a stable machine-readable code."""

    def __init__(self, message: str, code: str = "panel_error"):
        super().__init__(message)
        self.code = code


def resolve_budgets(max_tokens, judge_max_tokens) -> tuple[int | None, int]:
    """Generation and judge budgets are independent; the judge never inherits."""
    if judge_max_tokens is not None and (
        not isinstance(judge_max_tokens, int) or judge_max_tokens < MIN_JUDGE_MAX_TOKENS
    ):
        raise PanelError(
            f"judge_max_tokens must be an integer >= {MIN_JUDGE_MAX_TOKENS} "
            "(the judge must be able to emit the full panel JSON)",
            code="bad_arguments",
        )
    judge = JUDGE_DEFAULT_MAX_TOKENS if judge_max_tokens is None else judge_max_tokens
    gen = max_tokens if isinstance(max_tokens, int) else None
    return gen, judge


def parse_panel_json(text: str) -> dict | None:
    """Parse a JSON object out of model text. Returns None instead of raising."""
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def validate_judge_panel(parsed, text: str = "") -> dict:
    """Fail closed unless the judge produced a real panel object."""
    if parsed is None:
        if not (text or "").strip():
            raise PanelError(
                "judge returned empty output (no content, no parsed panel); "
                "raise judge_max_tokens",
                code="empty_judge",
            )
        raise PanelError(
            "judge returned text that is not a JSON panel object",
            code="invalid_judge_json",
        )
    if hasattr(parsed, "model_dump"):
        parsed = parsed.model_dump()
    if not isinstance(parsed, dict):
        raise PanelError("judge panel is not an object", code="invalid_judge_json")
    if not parsed:
        raise PanelError("judge returned an empty panel object", code="empty_judge")
    reports = parsed.get("seat_reports")
    if not isinstance(reports, list) or not reports:
        raise PanelError("judge panel has no seat_reports", code="invalid_judge_json")
    synthesis = parsed.get("synthesis")
    if not isinstance(synthesis, str) or not synthesis.strip():
        raise PanelError("judge panel has no synthesis", code="invalid_judge_json")
    return parsed


SEAT_SCHEMA = {
    "type": "object",
    "properties": {
        "seat_reports": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "seat": {"type": "string"},
                    "model": {"type": "string"},
                    "findings": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["seat", "model", "findings"],
            },
        },
        "synthesis": {"type": "string"},
        "contradictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "seats_for": {"type": "array", "items": {"type": "string"}},
                    "seats_against": {"type": "array", "items": {"type": "string"}},
                    "weight": {"type": "string"},
                },
                "required": ["claim"],
            },
        },
        "unresolved": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["seat_reports", "synthesis"],
    "additionalProperties": False,
}

PANEL_TOOL_SCHEMA = {
    "name": "storm_run_panel",
    "description": (
        "Run one perspective-panel round: fan each seat's brief out across the "
        "given model lineup, then judge-synthesize. Pass provider/model pairs "
        "explicitly; nothing is invented. Returns seat reports plus synthesis."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "The question under review."},
            "seats": {
                "type": "array",
                "description": "Seat cards: name, brief, sharpest questions.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "brief": {"type": "string"},
                        "questions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name", "brief"],
                },
            },
            "lineup": {
                "type": "array",
                "description": "Models per seat. Empty = active model, no override.",
                "items": {
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string"},
                        "model": {"type": "string"},
                    },
                    "required": ["model"],
                },
            },
            "judge": {
                "type": "object",
                "description": "Judge slot. Empty = active model, no override.",
                "properties": {
                    "provider": {"type": "string"},
                    "model": {"type": "string"},
                },
            },
            "temperature": {"type": "number"},
            "max_tokens": {
                "type": "integer",
                "description": "Per-seat generation budget. Does not apply to the judge.",
            },
            "judge_max_tokens": {
                "type": "integer",
                "description": (
                    "Judge output budget, independent of max_tokens. Default 8192; "
                    "must be >= 512 so the full panel JSON fits."
                ),
            },
            "retrieval": {
                "type": "boolean",
                "description": (
                    "Search the configured backend (STORM_SEARCH_PROVIDER/URL) and "
                    "require [S#] citations. Off by default; citations are unverified "
                    "when off."
                ),
            },
            "top_k": {
                "type": "integer",
                "description": "Sources retrieved per seat (default 5).",
            },
        },
        "required": ["topic", "seats"],
        "additionalProperties": False,
    },
}


def _seat_prompt(topic: str, seat: dict, sources=None) -> list[dict[str, Any]]:
    questions = "\n".join(f"- {q}" for q in seat.get("questions", [])) or "- (none given)"
    if sources:
        grounding = (
            f"{format_sources(sources)}\n\n"
            "Every factual claim must carry a citation marker [S#] pointing at one of "
            "the sources listed above. Quote only what those sources support. Do not "
            "invent sources and do not cite anything outside the list; if a claim is "
            "not supported, mark it unverified."
        )
    else:
        grounding = (
            "No retrieval sources are available for this run. Mark every factual claim "
            "unverified and do not fabricate citations or URLs."
        )
    return [
        {
            "role": "user",
            "content": (
                f"You are the {seat['name']} seat on a perspective panel.\n"
                f"Seat brief: {seat['brief']}\n"
                f"Topic: {topic}\n"
                f"Answer these questions from this seat's viewpoint only:\n{questions}\n"
                f"{grounding}\n"
                "End with 3-5 key findings."
            ),
        }
    ]


def _judge_prompt(topic: str, reports: list[dict], sources=None) -> str:
    chunks = "\n\n".join(
        f"--- {r['seat']} (via {r['model']}) ---\n{r['findings']}" for r in reports
    )
    citation_rule = ""
    if sources:
        citation_rule = (
            f"\n\n{format_sources(sources)}\n"
            "Keep the [S#] markers that appear in the reports. Do not add citations "
            "that are not in this list; name a claim unverified instead."
        )
    return (
        "You are the panel judge. Recommend, do not decide: the human makes the call.\n"
        f"Topic: {topic}\n\nSeat reports:\n{chunks}\n\n"
        "Synthesize: consensus first, then contradictions WITH weights (which seats, "
        "what evidence, never averaged away), then what stays unresolved or unverified. "
        "Ties and value calls go to the human with the trade stated plainly."
        f"{citation_rule}"
    )


def _hint(exc: Exception, lineup: list, judge: dict) -> str:
    """Plain-language next step for a failed run. Never swaps models for the user."""
    text = str(exc).lower()
    uses_moa = any(
        (slot or {}).get("provider") == "moa" for slot in list(lineup) + [judge or {}]
    )
    if "trust" in text or "override" in text or "not allowed" in text:
        return (
            "Model overrides need operator consent: set "
            "plugins.entries.storm-fusion-research.llm.allow_provider_override and "
            "allow_model_override to true in config.yaml. To limit what the plugin can "
            "reach, also set allowed_providers and allowed_models."
        )
    if uses_moa:
        return (
            "A slot uses provider 'moa'. The preset name must match one listed by "
            "'hermes model' under Mixture of Agents, and 'moa' must be in allowed_providers "
            "if you set that list. If your Hermes version will not route a MoA preset "
            "through a plugin, name the preset's reference models as separate lineup slots "
            "instead. That loses the inner merge."
        )
    return (
        "Check that every provider and model in the lineup is reachable right now. "
        "The run stopped; nothing was swapped in for the failed model."
    )


def make_panel_handler(ctx: Any):
    """Build the ``storm_run_panel`` handler bound to this plugin's ctx."""

    def handler(args: dict, **kwargs) -> str:
        try:
            topic = args["topic"]
            seats = args["seats"]
            lineup = args.get("lineup") or [{}]
            judge = args.get("judge") or {}
            temperature = args.get("temperature")
            max_tokens = args.get("max_tokens")
            judge_max_tokens = args.get("judge_max_tokens")
        except (KeyError, TypeError) as exc:
            return json.dumps({"success": False, "error": f"Bad arguments: {exc}"})

        try:
            # Separate budgets: the judge must never inherit the seat budget.
            max_tokens, judge_max_tokens = resolve_budgets(max_tokens, judge_max_tokens)
        except PanelError as exc:
            return json.dumps({"success": False, "error": str(exc), "code": exc.code})

        retriever = args.get("retriever")
        retrieval_flag = args.get("retrieval")
        if retriever is None and retrieval_flag:
            try:
                retriever = make_retriever()
            except RetrievalError as exc:
                return json.dumps(
                    {"success": False, "error": str(exc), "code": exc.code}
                )
            if retriever is None:
                return json.dumps(
                    {
                        "success": False,
                        "error": (
                            "retrieval was requested but no search backend is configured "
                            "(set STORM_SEARCH_PROVIDER and STORM_SEARCH_URL)"
                        ),
                        "code": "retrieval_not_configured",
                    }
                )
        retrieval_on = retriever is not None
        top_k = args.get("top_k") or 5

        sources_by_seat: dict[str, list] = {}
        all_sources: list = []
        if retrieval_on:
            for seat in seats:
                query = f"{topic} — {seat['name']}: {seat.get('brief', '')}"
                try:
                    found = retriever.search(query, top_k=top_k)
                except RetrievalError as exc:
                    return json.dumps(
                        {"success": False, "error": str(exc), "code": exc.code}
                    )
                except Exception as exc:  # search adapter bug: still fail closed
                    return json.dumps(
                        {"success": False, "error": str(exc), "code": "retrieval_failed"}
                    )
                if not found:
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"retrieval returned no sources for seat {seat['name']!r}",
                            "code": "retrieval_failed",
                        }
                    )
                sources_by_seat[seat["name"]] = found
                for source in found:
                    if all(source.url != s.url for s in all_sources):
                        all_sources.append(source)

        reports: list[dict] = []
        usage: list[dict] = []
        try:
            for seat in seats:
                # One global, stable numbering so a seat's [S2] and the judge's
                # [S2] mean the same source.
                seat_sources = all_sources
                for slot in lineup:
                    result = ctx.llm.complete(
                        _seat_prompt(topic, seat, seat_sources),
                        provider=slot.get("provider"),
                        model=slot.get("model"),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        purpose="storm-fusion-research.run_seat",
                    )
                    if getattr(result, "finish_reason", None) == "length":
                        raise PanelError(
                            f"seat '{seat['name']}' was cut off by max_tokens; "
                            "raise max_tokens and rerun",
                            code="seat_truncated",
                        )
                    if not (result.text or "").strip():
                        raise PanelError(
                            f"seat '{seat['name']}' returned an empty report",
                            code="empty_seat_report",
                        )
                    if retrieval_on:
                        require_clean(result.text, seat_sources, seat=seat["name"])
                    reports.append(
                        {
                            "seat": seat["name"],
                            "model": f"{result.provider}/{result.model}",
                            "findings": result.text,
                            "sources": [s.to_dict() for s in seat_sources],
                        }
                    )
                    usage.append(
                        {
                            "seat": seat["name"],
                            "model": f"{result.provider}/{result.model}",
                            "tokens": result.usage.total_tokens,
                        }
                    )
            judged = ctx.llm.complete_structured(
                instructions=_judge_prompt(topic, reports, all_sources if retrieval_on else None),
                input=[{"type": "text", "text": "Synthesize per instructions."}],
                json_schema=SEAT_SCHEMA,
                schema_name="storm.panel",
                provider=judge.get("provider"),
                model=judge.get("model"),
                temperature=temperature,
                max_tokens=judge_max_tokens,
                purpose="storm-fusion-research.judge",
            )
            if getattr(judged, "finish_reason", None) == "length":
                raise PanelError(
                    "judge was cut off by judge_max_tokens; raise judge_max_tokens "
                    "and rerun (nothing was accepted)",
                    code="judge_truncated",
                )
            panel = validate_judge_panel(judged.parsed, getattr(judged, "text", ""))
            if retrieval_on:
                problems = verify_citations(
                    panel.get("synthesis", ""), all_sources, require_citation=False
                )
                if problems:
                    raise CitationError("judge synthesis: " + "; ".join(problems))
        except (PanelError, CitationError, RetrievalError) as exc:
            code = getattr(exc, "code", "panel_error")
            logger.warning("storm_run_panel failed (%s): %s", code, exc)
            return json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "code": code,
                    "hint": _hint(exc, lineup, judge),
                    "seat_reports": reports,
                },
                ensure_ascii=False,
            )
        except Exception as exc:
            logger.warning("storm_run_panel failed: %s", exc)
            return json.dumps(
                {"success": False, "error": str(exc), "hint": _hint(exc, lineup, judge)}
            )

        return json.dumps(
            {
                "success": True,
                "panel": panel,
                "seat_reports": reports,
                "usage": usage,
                "budgets": {"generation": max_tokens, "judge": judge_max_tokens},
                "retrieval": {
                    "mode": "on" if retrieval_on else "off",
                    "top_k": top_k if retrieval_on else None,
                    "sources": [s.to_dict() for s in all_sources],
                },
            },
            ensure_ascii=False,
        )

    return handler
