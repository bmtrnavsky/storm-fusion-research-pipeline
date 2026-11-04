"""Query composition: a per-seat search query must stay inside the length a keyless
search backend will actually answer (DDG HTML returns zero results above ~130 chars).

A 200-char "topic — seat: brief" template reads well and searches badly: the backend
truncates or drops the query, so retrieval silently returns nothing and the run dies as
"retrieval returned no sources" for a seat that was never searched. The query is a
search-string, not a sentence: topic first, then the seat's distinctive words, inside a
hard character budget.
"""

from __future__ import annotations

import json

import pytest

from helpers import FakeCtx, FakeLLM
from retrieval import Source, compose_query

import panel

# The shape of a real live-run brief: long, second-person prose, punctuation heavy.
LONG_TOPIC = (
    "Should the DC add a second packing station before peak, and what should we "
    "fix about the handoff between pick and pack?"
)
LONG_BRIEF = (
    "You pack boxes every shift and know where the line jams. Speak from the floor: "
    "walk me through a normal hour, where you queue, what breaks, and what a second "
    "station would change for the people standing there."
)


def test_long_seat_query_stays_inside_the_backend_budget():
    query = compose_query(LONG_TOPIC, "associate", LONG_BRIEF)
    assert len(query) <= 120, query


def test_query_drops_the_sentence_scaffolding():
    query = compose_query(LONG_TOPIC, "associate", LONG_BRIEF)
    # The em dash + "seat:" template is what made the string long and the search empty.
    assert "\u2014" not in query
    assert ":" not in query


def test_query_keeps_the_topic_and_the_seat_signal():
    query = compose_query(LONG_TOPIC, "associate", LONG_BRIEF)
    lowered = query.lower()
    assert lowered.startswith("should the dc add a second packing station")
    # A word only the brief carries ("jams") proves the seat's angle survives.
    assert "jam" in lowered or "queue" in lowered


def test_topic_is_cut_at_a_clause_not_mid_clause():
    query = compose_query(LONG_TOPIC, "associate", LONG_BRIEF)
    lowered = query.lower()
    assert lowered.startswith("should the dc add a second packing station before peak")
    # The second clause ("and what should we fix about the handoff...") must go as a
    # unit, not leave a dangling "what should we fix" in front of the seat words.
    assert "what should we" not in lowered
    assert "handoff" not in lowered


def test_short_input_is_passed_through_unchanged():
    assert compose_query("Packing station throughput") == "Packing station throughput"


def test_overlong_topic_is_cut_on_a_word_boundary():
    topic = " ".join(f"word{i}" for i in range(60))
    query = compose_query(topic, "associate", "short brief")
    assert 0 < len(query) <= 120
    assert not query.endswith("wor")  # never a sliced word
    assert query == " ".join(query.split())


def test_empty_topic_falls_back_to_the_seat_signal():
    query = compose_query("", "safety", "bending risk on the raised bench")
    assert query
    assert len(query) <= 120
    assert "bending" in query.lower() or "safety" in query.lower()


def test_composition_is_deterministic():
    first = compose_query(LONG_TOPIC, "associate", LONG_BRIEF)
    second = compose_query(LONG_TOPIC, "associate", LONG_BRIEF)
    assert first == second


def test_panel_sends_the_compact_query_not_the_template(panel_args, valid_panel):
    long_args = {
        **panel_args,
        "seats": [{"name": "associate", "brief": LONG_BRIEF}],
    }
    llm = FakeLLM(seat_text="Throughput rises 12% [S1].", judge_parsed=valid_panel)
    retriever = _RecordingRetriever()
    res = json.loads(
        panel.make_panel_handler(FakeCtx(llm))({**long_args, "retriever": retriever})
    )
    assert res["success"] is True, res
    query = retriever.calls[0][0]
    assert len(query) <= 120, query
    assert "\u2014" not in query


class _RecordingRetriever:
    def __init__(self):
        self.calls = []

    def search(self, query, top_k=5):
        self.calls.append((query, top_k))
        return [
            Source(
                title="Station throughput",
                url="https://ops.example.test/throughput",
                snippet="Station throughput rose 12%.",
            )
        ]
