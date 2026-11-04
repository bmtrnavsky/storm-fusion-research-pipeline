"""Fabrication gate: a report that invents a URL, a quote, or an attribution must fail.

Every case here is a *fabricated* citation. The verifier has to fail closed:
``verify_citations`` returns problems and ``require_clean`` raises
``CitationError`` (code ``citation_mismatch``). A fabricated citation that
passes the verifier is worse than no verifier at all, because the panel then
reports invented grounding as if it were retrieved.
"""

from __future__ import annotations

import pytest

from citations import CitationError, require_clean, verify_citations
from retrieval import Source

SOURCES = [
    Source(
        title="Station throughput",
        url="https://ops.example.test/throughput",
        snippet="Station throughput rose 12% after the reallocation.",
    ),
    Source(
        title="Ergonomics",
        url="https://safety.example.test/ergo",
        snippet="Operators bend 30% less with the raised bench.",
    ),
]


# --- fabricated URL -------------------------------------------------------

def test_nonexistent_url_is_rejected():
    """A URL the retriever never returned cannot be cited as grounding."""
    text = "Automation cut headcount 40% (https://invented.example.test/report) [S1]."
    problems = verify_citations(text, SOURCES)
    assert problems, "fabricated URL passed the verifier"
    assert any("invented.example.test" in p for p in problems)


def test_nonexistent_url_raises_from_require_clean():
    text = "See https://invented.example.test/report [S1]."
    with pytest.raises(CitationError) as exc:
        require_clean(text, SOURCES, seat="associate")
    assert exc.value.code == "citation_mismatch"
    assert "associate" in str(exc.value)


# --- quote absent from the source ----------------------------------------

def test_quote_absent_from_source_is_rejected():
    """Quoted text that appears in no retrieved snippet is fabricated."""
    text = 'The report says "throughput tripled overnight" [S1].'
    problems = verify_citations(text, SOURCES)
    assert problems, "fabricated quote passed the verifier"
    assert any("quote" in p.lower() for p in problems)


def test_quote_absent_from_source_raises_from_require_clean():
    text = 'Our source claims "operators bend 90% less" [S2].'
    with pytest.raises(CitationError) as exc:
        require_clean(text, SOURCES, seat="associate")
    assert exc.value.code == "citation_mismatch"
    assert "quote" in str(exc.value).lower()


def test_quote_matching_source_still_passes():
    """Control: a real quote from a cited snippet must not be flagged."""
    text = 'Throughput rose after the change: "station throughput rose 12%" [S1].'
    assert verify_citations(text, SOURCES) == []


# --- mismatched marker numbering -----------------------------------------

def test_quote_attributed_to_wrong_marker_is_rejected():
    """Text that lives in S2 but is cited as [S1] is a numbering mismatch."""
    text = 'One seat wrote "operators bend 30% less with the raised bench" [S1].'
    problems = verify_citations(text, SOURCES)
    assert problems, "misattributed quote (S2 content cited as S1) passed"
    assert any("S1" in p for p in problems)


def test_quote_without_any_marker_is_rejected():
    """An uncited quotation is grounding the reader cannot check."""
    text = 'Analysts observed "station throughput rose 47% after automation".'
    problems = verify_citations(text, SOURCES)
    assert problems, "uncited quote passed the verifier"


def test_mismatched_marker_number_raises_from_require_clean():
    text = 'It states "operators bend 30% less" [S1].'
    with pytest.raises(CitationError) as exc:
        require_clean(text, SOURCES, seat="judge")
    assert exc.value.code == "citation_mismatch"
    assert "judge" in str(exc.value)


# --- fail-closed on empty / missing retrieval ----------------------------

def test_fabricated_citation_with_no_sources_raises():
    with pytest.raises(CitationError) as exc:
        require_clean('Claim "invented finding" [S1].', [])
    assert exc.value.code == "citation_mismatch"
