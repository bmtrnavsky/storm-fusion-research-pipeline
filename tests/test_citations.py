"""Citation verifier: prompts make citations mandatory; mismatches block the run."""

from __future__ import annotations

import pytest

from citations import (
    CitationError,
    extract_citations,
    extract_urls,
    format_sources,
    require_clean,
    verify_citations,
)
from retrieval import Source

SOURCES = [
    Source(title="Station throughput", url="https://ops.example.test/throughput", snippet="numbers"),
    Source(title="Ergonomics", url="https://safety.example.test/ergo", snippet="bend"),
]


def test_format_sources_numbers_and_urls():
    text = format_sources(SOURCES)
    assert "[S1]" in text and SOURCES[0].url in text
    assert "[S2]" in text and SOURCES[1].url in text


def test_extract_citations_forms():
    assert extract_citations("a [S1] b [S2, S3] c [S4;S5]") == {1, 2, 3, 4, 5}
    assert extract_citations("no markers here") == set()


def test_extract_urls_strips_trailing_punctuation():
    assert extract_urls("see https://ops.example.test/throughput.") == {
        "https://ops.example.test/throughput"
    }


def test_clean_report_passes():
    text = "Throughput rises 12% [S1]. Bending drops [S2]."
    assert verify_citations(text, SOURCES) == []


def test_out_of_range_marker_is_a_problem():
    problems = verify_citations("Throughput rises [S9].", SOURCES)
    assert any("S9" in p for p in problems)


def test_fabricated_url_is_a_problem():
    problems = verify_citations("See https://made-up.example.test/claim [S1].", SOURCES)
    assert any("made-up" in p for p in problems)


def test_missing_citation_is_a_problem_when_required():
    problems = verify_citations("Throughput rises 12%.", SOURCES, require_citation=True)
    assert any("no citation" in p.lower() for p in problems)


def test_no_citation_requirement_when_retrieval_off():
    assert verify_citations("Throughput rises 12%.", [], require_citation=False) == []


def test_citing_without_sources_is_a_problem():
    problems = verify_citations("Claim [S1].", [])
    assert problems


def test_require_clean_raises_with_code():
    with pytest.raises(CitationError) as exc:
        require_clean("Claim [S7].", SOURCES, seat="associate")
    assert exc.value.code == "citation_mismatch"
    assert "associate" in str(exc.value)


def test_same_url_with_different_case_and_fragment_passes():
    text = "Numbers [S1] (HTTPS://OPS.EXAMPLE.TEST/throughput#top)."
    assert verify_citations(text, SOURCES) == []
