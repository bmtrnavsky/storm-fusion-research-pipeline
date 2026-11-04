"""Regression tests for the empty/truncated judge hole (gated review finding #1).

An empty judge, a truncated judge, or an unparsed judge must never come back as
``success: true``. These tests fail against the committed code.
"""

from __future__ import annotations

import json

import pytest
from helpers import FakeCtx, FakeLLM

import panel


def run(llm: FakeLLM, args: dict) -> dict:
    return json.loads(panel.make_panel_handler(FakeCtx(llm))(args))


def test_empty_judge_is_failure(panel_args):
    """REPRO: parsed=None, text='' used to return {'panel': {'raw': ''}} as success."""
    llm = FakeLLM(judge_parsed=None, judge_text="")
    res = run(llm, panel_args)

    assert res["success"] is False, res
    assert res["code"] == "empty_judge"
    assert "panel" not in res
    assert "raw" not in json.dumps(res)


def test_whitespace_judge_is_failure(panel_args):
    res = run(FakeLLM(judge_parsed=None, judge_text="  \n\t "), panel_args)
    assert res["success"] is False
    assert res["code"] == "empty_judge"


def test_unparsed_prose_judge_is_failure(panel_args):
    """Prose is not a panel. It must not be smuggled through under 'raw'."""
    res = run(FakeLLM(judge_parsed=None, judge_text="I recommend the station."), panel_args)
    assert res["success"] is False
    assert res["code"] == "invalid_judge_json"
    assert "panel" not in res


def test_empty_judge_object_is_failure(panel_args):
    res = run(FakeLLM(judge_parsed={}, judge_text="{ }"), panel_args)
    assert res["success"] is False
    assert res["code"] == "empty_judge"


def test_judge_panel_without_synthesis_is_failure(panel_args):
    parsed = {"seat_reports": [{"seat": "a", "model": "m", "findings": "x"}], "synthesis": "  "}
    res = run(FakeLLM(judge_parsed=parsed, judge_text="{}"), panel_args)
    assert res["success"] is False
    assert res["code"] == "invalid_judge_json"


def test_judge_length_finish_reason_is_failure(panel_args, valid_panel):
    """A judge cut off by max_tokens must not be accepted."""
    res = run(
        FakeLLM(judge_parsed=valid_panel, judge_finish_reason="length"),
        panel_args,
    )
    assert res["success"] is False
    assert res["code"] == "judge_truncated"


def test_seat_length_finish_reason_is_failure(panel_args, valid_panel):
    res = run(
        FakeLLM(seat_finish_reason="length", judge_parsed=valid_panel),
        panel_args,
    )
    assert res["success"] is False
    assert res["code"] == "seat_truncated"


def test_empty_seat_report_is_failure(panel_args, valid_panel):
    res = run(FakeLLM(seat_text="   ", judge_parsed=valid_panel), panel_args)
    assert res["success"] is False
    assert res["code"] == "empty_seat_report"


def test_judge_budget_is_independent_of_generation_budget(panel_args, valid_panel):
    """The old code passed the same max_tokens to generator and judge."""
    llm = FakeLLM(judge_parsed=valid_panel)
    res = run(llm, {**panel_args, "max_tokens": 256})

    assert res["success"] is True, res
    seat_calls = [c for c in llm.calls if c["kind"] == "seat"]
    judge_calls = [c for c in llm.calls if c["kind"] == "judge"]
    assert seat_calls and all(c["max_tokens"] == 256 for c in seat_calls)
    assert all(c["max_tokens"] == panel.JUDGE_DEFAULT_MAX_TOKENS for c in judge_calls)
    assert res["budgets"] == {"generation": 256, "judge": panel.JUDGE_DEFAULT_MAX_TOKENS}


def test_explicit_judge_budget_is_used(panel_args, valid_panel):
    llm = FakeLLM(judge_parsed=valid_panel)
    res = run(llm, {**panel_args, "max_tokens": 256, "judge_max_tokens": 6000})
    assert res["success"] is True, res
    judge_calls = [c for c in llm.calls if c["kind"] == "judge"]
    assert judge_calls[0]["max_tokens"] == 6000


def test_too_small_judge_budget_is_rejected(panel_args, valid_panel):
    res = run(FakeLLM(judge_parsed=valid_panel), {**panel_args, "judge_max_tokens": 64})
    assert res["success"] is False
    assert res["code"] == "bad_arguments"


def test_valid_judge_still_succeeds(panel_args, valid_panel):
    res = run(FakeLLM(judge_parsed=valid_panel), panel_args)
    assert res["success"] is True, res
    assert res["panel"] == valid_panel
    assert len(res["usage"]) == 2


@pytest.mark.parametrize(
    ("max_tokens", "judge_max_tokens", "expected"),
    [
        (None, None, (None, 8192)),
        (1000, None, (1000, 8192)),
        (1000, 4000, (1000, 4000)),
    ],
)
def test_resolve_budgets(max_tokens, judge_max_tokens, expected):
    assert panel.JUDGE_DEFAULT_MAX_TOKENS == 8192
    assert panel.resolve_budgets(max_tokens, judge_max_tokens) == expected
