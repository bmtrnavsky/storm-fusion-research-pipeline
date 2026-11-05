"""A marker keeps its meaning when a report wraps it in brackets or parens.

Round-3 taught the verifier to read a paren *group* as a citation. It still read the
group's body verbatim, so a bracket marker glossed inside a parenthesis --
``Claim ([S1]).`` -- arrived at the range check as the token ``[S1]`` and was reported
as unrecognized. A clean citation failed the gate on punctuation alone, while the
same marker unwrapped passed. Both spellings name the same source.
"""

from __future__ import annotations

import pytest

from citations import extract_citations, verify_citations
from retrieval import Source

SOURCES = [
    Source(title="Station throughput", url="https://ops.example.test/throughput", snippet="numbers"),
    Source(title="Ergonomics", url="https://safety.example.test/ergo", snippet="bend"),
]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Claim ([S1]).", {1}),
        ("Claim ([S1] and [S2]).", {1, 2}),
        ("Claim ([S1], [S2]).", {1, 2}),
        ("Claim (([S1])).", {1}),
        ("Claim [[S1]].", {1}),
    ],
    ids=["paren-wrapped", "and-joined", "comma-joined", "double-paren", "double-bracket"],
)
def test_wrapped_marker_parses_like_its_bare_spelling(text: str, expected: set[int]):
    """Whatever wraps the marker is decoration; the marker itself is what counts."""
    assert extract_citations(text) == expected
    assert verify_citations(text, SOURCES) == []


def test_wrapped_marker_is_identical_to_bare_marker():
    """The wrapped and bare spellings must produce the same verdict, not a near-miss."""
    sources = SOURCES[:1]
    assert verify_citations("Claim ([S1]).", sources) == verify_citations("Claim [S1].", sources)


@pytest.mark.parametrize(
    "text",
    ["Claim ([S9]).", "Claim ([S8-S9])."],
    ids=["out-of-range", "out-of-range-range"],
)
def test_wrapped_fabricated_marker_is_still_range_checked(text: str):
    """Peeling the wrapper must not turn a fabricated marker into an unrecognized one."""
    problems = verify_citations(text, SOURCES, require_citation=False)
    assert any("only 2 sources" in problem for problem in problems), problems
    assert not any("unrecognized" in problem for problem in problems), problems
