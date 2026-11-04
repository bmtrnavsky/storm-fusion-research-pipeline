"""Round-3 verifier hardening: three gate-breaking holes, each named by its test.

H4  silent drops in paren markers — a group whose body carries a locator
    (``(S99, page 4)``), a label (``(Source: S99)``) or no separating space
    (``claim(S99)``) used to fall through the prose filter and reset to "no
    citation", so a fabricated ``S99`` passed the gate untouched.
H5  partial-word grounding — a quote was confirmed by a bare substring test, so
    ``"plant growth increased"`` was accepted as a quote of "the transplant growth
    increased".
H6  tolerance in the eval bounds — ``fp <= 1`` / ``fn <= 1`` absorbed a whole
    one-case regression in either direction. The bound itself now lives with the
    ledgers (``tests/test_verifier_eval.py``, ``tests/test_verifier_heldout.py``);
    the test here only checks that the gate still scores a clean sheet.

Every test asserts behaviour the gate must have; none is written around an
implementation quirk.
"""

from __future__ import annotations

import pytest

from citations import extract_citations, verify_citations
from retrieval import Source

SOURCES = [
    Source(title="Station throughput", url="https://ops.example.test/throughput", snippet="numbers"),
    Source(title="Ergonomics", url="https://safety.example.test/ergo", snippet="bend"),
]

AGRONOMY = [
    Source(
        title="Agronomy",
        url="https://agri.example.test/y",
        snippet="The transplant growth increased sharply.",
    )
]


# --- H4: a decorated paren marker is still a citation -----------------------


@pytest.mark.parametrize(
    "text",
    [
        "Throughput rises (Source: S99).",
        "Throughput rises (S99, page 4).",
        "Throughput rises claim(S99).",
        "Throughput rises (Sources: S1; S99).",
        "Throughput rises (S 99).",
    ],
    ids=["label", "locator", "glued", "label-list", "spaced"],
)
def test_h4_decorated_paren_marker_is_range_checked(text: str):
    """The S99 in every one of these forms points at a source never retrieved."""
    refs = extract_citations(text)
    assert 99 in refs, f"{text!r} was silently dropped (refs={refs})"
    problems = verify_citations(text, SOURCES, require_citation=False)
    assert any("S99" in problem for problem in problems), problems


@pytest.mark.parametrize(
    "text",
    [
        "Throughput rises (S1).",
        "Throughput rises (see S1).",
        "Throughput rises claim(S2).",
        "Throughput rises (Source: S1).",
        "Throughput rises (S1, page 2).",
        "Throughput rises (S1 and S2).",
        "Hardware revision B(S2) shipped [S1].",
    ],
    ids=["plain", "connective", "glued", "label", "locator", "two", "rev-code"],
)
def test_h4_decorated_paren_marker_in_range_stays_clean(text: str):
    assert verify_citations(text, SOURCES, require_citation=False) == []


def test_h4_prose_parenthesis_is_still_prose():
    """Widening the paren scan must not turn every aside into a citation."""
    text = "The throughput held in the (S3 region) and the (new S7 line) [S1]."
    assert extract_citations(text) == {1}
    assert verify_citations(text, SOURCES) == []


# --- H5: a quote grounds on words, not on fragments of words ----------------


@pytest.mark.parametrize(
    "quote",
    ["plant growth increased", "plant growth"],
    ids=["clipped-first-word", "clipped-noun"],
)
def test_h5_quote_does_not_ground_on_a_partial_word(quote: str):
    problems = verify_citations(f'The note says "{quote}" [S1].', AGRONOMY)
    assert problems, f"grounded on a substring of 'transplant growth increased': {quote!r}"


@pytest.mark.parametrize(
    "quote",
    [
        "transplant growth increased",
        "growth increased",
        "increased sharply",
        "the transplant growth increased sharply",
    ],
    ids=["whole", "middle", "tail", "full"],
)
def test_h5_quote_of_real_words_still_grounds(quote: str):
    assert verify_citations(f'The note says "{quote}" [S1].', AGRONOMY) == []


# --- H6: the gate still scores a clean sheet --------------------------------


def test_h6_ledgers_score_no_false_positives_or_negatives():
    from test_verifier_eval import CASES, score
    from test_verifier_heldout import HELD, _stats

    tuned, heldout = score(CASES), _stats(HELD)
    assert (tuned["fp"], tuned["fn"]) == (0, 0), tuned
    assert (heldout["fp"], heldout["fn"]) == (0, 0), heldout
