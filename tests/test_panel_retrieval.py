"""Panel wiring: retrieved sources reach prompts, verifier blocks the run."""

from __future__ import annotations

import json

from helpers import FakeCtx, FakeLLM
from retrieval import RetrievalError, Source

import panel

SOURCES = [
    Source(title="Station throughput", url="https://ops.example.test/throughput", snippet="numbers"),
    Source(title="Ergonomics", url="https://safety.example.test/ergo", snippet="bend"),
]


class FakeRetriever:
    def __init__(self, sources=SOURCES, error=None):
        self.sources = sources
        self.error = error
        self.calls = []

    def search(self, query, top_k=5):
        self.calls.append((query, top_k))
        if self.error:
            raise self.error
        return self.sources[:top_k]


def run(llm, args, retriever):
    return json.loads(panel.make_panel_handler(FakeCtx(llm))({**args, "retriever": retriever}))


def test_sources_reach_the_seat_prompt(panel_args, valid_panel):
    llm = FakeLLM(seat_text="Throughput rises 12% [S1].", judge_parsed=valid_panel)
    retriever = FakeRetriever()
    res = run(llm, panel_args, retriever)

    assert res["success"] is True, res
    prompt = llm.calls[0]["messages"][0]["content"]
    assert "[S1]" in prompt
    assert "ops.example.test/throughput" in prompt
    assert "Do not invent sources" in prompt
    assert res["retrieval"]["mode"] == "on"
    assert [s["url"] for s in res["retrieval"]["sources"]] == [s.url for s in SOURCES]


def test_fabricated_marker_blocks_the_run(panel_args, valid_panel):
    llm = FakeLLM(seat_text="Throughput triples [S9].", judge_parsed=valid_panel)
    res = run(llm, panel_args, FakeRetriever())

    assert res["success"] is False
    assert res["code"] == "citation_mismatch"
    assert "S9" in res["error"]


def test_uncited_seat_report_blocks_the_run(panel_args, valid_panel):
    llm = FakeLLM(seat_text="Throughput rises, trust me.", judge_parsed=valid_panel)
    res = run(llm, panel_args, FakeRetriever())
    assert res["success"] is False
    assert res["code"] == "citation_mismatch"


def test_fabricated_url_blocks_the_run(panel_args, valid_panel):
    llm = FakeLLM(
        seat_text="Numbers [S1] per https://invented.example.test/report.",
        judge_parsed=valid_panel,
    )
    res = run(llm, panel_args, FakeRetriever())
    assert res["success"] is False
    assert res["code"] == "citation_mismatch"
    assert "invented" in res["error"]


def test_judge_cannot_add_new_citations(panel_args):
    judged = {
        "seat_reports": [{"seat": "associate", "model": "m", "findings": "x"}],
        "synthesis": "The panel cites [S9].",
    }
    llm = FakeLLM(seat_text="Fine [S1].", judge_parsed=judged)
    res = run(llm, panel_args, FakeRetriever())
    assert res["success"] is False
    assert res["code"] == "citation_mismatch"


def test_retrieval_off_marks_claims_unverified(panel_args, valid_panel):
    llm = FakeLLM(seat_text="No citations at all.", judge_parsed=valid_panel)
    res = json.loads(panel.make_panel_handler(FakeCtx(llm))({**panel_args, "retrieval": False}))

    assert res["success"] is True, res
    prompt = llm.calls[0]["messages"][0]["content"]
    assert "unverified" in prompt
    assert "[S1]" not in prompt
    assert res["retrieval"]["mode"] == "off"


def test_retrieval_failure_is_fail_closed(panel_args, valid_panel):
    llm = FakeLLM(judge_parsed=valid_panel)
    res = run(llm, panel_args, FakeRetriever(error=RetrievalError("search down")))
    assert res["success"] is False
    assert res["code"] == "retrieval_failed"
    assert not llm.calls
