"""A prose seat writes illustrative examples, not only sourced claims.

``Double-check the label before it ships: [example] "Ship to 4th & Main, dock 2"
reads badly.`` is the seat doing its job -- but the quote verifier reads every quoted
span as a claim and fails the run for a quote no source contains. The fix is explicit,
not a blanket exemption: a quote the seat marks as its own example is illustration.
Unmarked quotes stay hard-gated, and a marker never excuses a fabricated marker or URL.
"""

from __future__ import annotations

import json

import pytest

from citations import verify_citations
from helpers import FakeCtx, FakeLLM
from retrieval import Source

import panel

OPS = Source(
    title="Station throughput",
    url="https://ops.example.test/throughput",
    snippet="Station throughput rose 12% after the reallocation.",
)
SOURCES = [OPS]

GROUNDED = 'Throughput rose 12% after the reallocation [S1].'


def problems(text, require_citation=False):
    return verify_citations(text, list(SOURCES), require_citation=require_citation)


@pytest.mark.parametrize("prefix", ["[example]", "(example)", "[Example]", "( EXAMPLE )"])
def test_marked_example_quote_is_not_a_claim(prefix):
    text = f'{GROUNDED} Label check: {prefix} "Ship to 4th & Main, dock 2" reads badly.'
    assert problems(text) == []


def test_example_lead_in_does_not_exempt_a_quote():
    # The fail-open: a fabricated quote wearing the plain-english "example:" lead-in,
    # in a sentence that carries a real [S1], sailed through ungrounded.
    text = f'{GROUNDED} Label check: For example: "the line never stops for lunch" [S1].'
    assert problems(text) != []


def test_bracket_marker_does_not_exempt_a_quote_grounded_by_its_own_sentence():
    # Even the explicit marker stops meaning "illustration" once the same sentence
    # claims a source: that sentence is asserting the quote is checkable.
    text = f'{GROUNDED} Label check: [example] "the line never stops for lunch" [S1].'
    assert problems(text) != []


def test_marker_must_touch_the_quote_it_exempts():
    # A marker parked earlier in the sentence exempts nothing: the quote has to be
    # the thing the marker introduces.
    text = f'{GROUNDED} Label check: [example] the packing label says "Ship to 4th & Main, dock 2".'
    assert problems(text) != []


def test_marker_only_covers_the_quote_it_touches():
    text = (
        f'{GROUNDED} For instance [example] "Ship to 4th & Main, dock 2" is the pattern. '
        'But the source says "the line never stops for lunch" which it does not [S1].'
    )
    assert problems(text) != []


def test_unmarked_quote_is_still_gated():
    text = f'{GROUNDED} Label check: "Ship to 4th & Main, dock 2" reads badly.'
    assert problems(text) != []


def test_prose_phrasing_is_not_a_marker():
    # Deliberately narrow: prose lead-ins are exactly the phrasing a fabricated
    # citation would wear, so none of them exempts a quote.
    for phrase in ("For example,", "The counter-example:", "Example:", "example -", "Example \u2014"):
        text = f'{GROUNDED} {phrase} "Ship to 4th & Main, dock 2" reads badly.'
        assert problems(text) != [], phrase


def test_marker_does_not_excuse_a_fabricated_marker():
    text = f'{GROUNDED} [example] "Ship to 4th & Main, dock 2" and throughput tripled [S9].'
    flagged = problems(text)
    assert any("S9" in p for p in flagged), flagged


def test_marker_does_not_excuse_a_fabricated_url():
    text = f'{GROUNDED} [example] "Ship to 4th & Main, dock 2" per https://evil.test/x.'
    flagged = problems(text)
    assert any("evil.test" in p for p in flagged), flagged


def test_seat_prompt_teaches_the_marker():
    prompt = panel._seat_prompt("Packing station", {"name": "associate", "brief": "Pack boxes."}, SOURCES)
    content = prompt[0]["content"]
    assert "[example]" in content


def test_prose_seat_report_with_its_own_example_passes_the_run(valid_panel):
    seat_text = (
        'Throughput rose 12% after the reallocation [S1]. '
        'Write the label the way a picker reads it: [example] "Ship to 4th & Main, dock 2" '
        "is fine, and the dock number always goes last."
    )
    llm = FakeLLM(seat_text=seat_text, judge_parsed=valid_panel)

    class Retriever:
        def search(self, query, top_k=5):
            return list(SOURCES)

    args = {
        "topic": "Should the DC add a second packing station?",
        "seats": [{"name": "associate", "brief": "You pack boxes every shift."}],
        "retriever": Retriever(),
    }
    res = json.loads(panel.make_panel_handler(FakeCtx(llm))(args))
    assert res["success"] is True, res
