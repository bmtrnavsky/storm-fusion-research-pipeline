"""Storm panel execution: per-seat multi-model fanout plus judge synthesis.

The agent passes the lineup inline (resolved from the human's MoA preset or
chosen ad hoc). The plugin never invents models. Every LLM call goes through
the host-owned ``ctx.llm`` lane, so the plugin never sees keys or tokens.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

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
            "max_tokens": {"type": "integer"},
        },
        "required": ["topic", "seats"],
        "additionalProperties": False,
    },
}


def _seat_prompt(topic: str, seat: dict) -> list[dict[str, Any]]:
    questions = "\n".join(f"- {q}" for q in seat.get("questions", [])) or "- (none given)"
    return [
        {
            "role": "user",
            "content": (
                f"You are the {seat['name']} seat on a perspective panel.\n"
                f"Seat brief: {seat['brief']}\n"
                f"Topic: {topic}\n"
                f"Answer these questions from this seat's viewpoint only:\n{questions}\n"
                "Ground factual claims in retrievable sources and list them. "
                "Mark anything unsourced as unverified. End with 3-5 key findings."
            ),
        }
    ]


def _judge_prompt(topic: str, reports: list[dict]) -> str:
    chunks = "\n\n".join(
        f"--- {r['seat']} (via {r['model']}) ---\n{r['findings']}" for r in reports
    )
    return (
        "You are the panel judge. Recommend, do not decide: the human makes the call.\n"
        f"Topic: {topic}\n\nSeat reports:\n{chunks}\n\n"
        "Synthesize: consensus first, then contradictions WITH weights (which seats, "
        "what evidence, never averaged away), then what stays unresolved or unverified. "
        "Ties and value calls go to the human with the trade stated plainly."
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
        except (KeyError, TypeError) as exc:
            return json.dumps({"success": False, "error": f"Bad arguments: {exc}"})

        reports: list[dict] = []
        usage: list[dict] = []
        try:
            for seat in seats:
                for slot in lineup:
                    result = ctx.llm.complete(
                        _seat_prompt(topic, seat),
                        provider=slot.get("provider"),
                        model=slot.get("model"),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        purpose="storm-fusion-research.run_seat",
                    )
                    reports.append(
                        {
                            "seat": seat["name"],
                            "model": f"{result.provider}/{result.model}",
                            "findings": result.text,
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
                instructions=_judge_prompt(topic, reports),
                input=[{"type": "text", "text": "Synthesize per instructions."}],
                json_schema=SEAT_SCHEMA,
                schema_name="storm.panel",
                provider=judge.get("provider"),
                model=judge.get("model"),
                temperature=temperature,
                max_tokens=max_tokens,
                purpose="storm-fusion-research.judge",
            )
        except Exception as exc:
            logger.warning("storm_run_panel failed: %s", exc)
            return json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "hint": (
                        "Model overrides need operator consent: set "
                        "plugins.entries.storm-fusion-research.llm.allow_provider_override "
                        "and allow_model_override to true in config.yaml."
                    ),
                }
            )

        panel = judged.parsed if judged.parsed is not None else {"raw": judged.text}
        return json.dumps(
            {"success": True, "panel": panel, "usage": usage}, ensure_ascii=False
        )

    return handler
