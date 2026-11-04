"""Round-2 verifier hardening: each test names the hole it closes.

Holes (from the external review of citations.py):

H1  markers are never silently dropped — odd tokens such as ``[S99,p.4]``,
    ``[S 99]`` and ``(S9)`` are range-checked or flagged, never reset to nothing.
H2  URL blind spots: ``ftp://``, protocol-relative ``//host``, real-TLD paths that
    collide with document extensions (``evil.sh/x``), short uncommon TLDs
    (``bit.ly``) and IDN / punycode hosts.
H3a honest reports: ASP.NET-style dotted names are not hosts.
H3b honest reports: quotes are checked against every text field a source carries
    (snippet-only retrieval is a documented lower bound).
H3c honest reports: parenthesised URLs are not truncated at the first ``)``.
H3d honest reports: a marker in the immediately preceding sentence may ground the
    quote that follows it.

Every test asserts behaviour the gate must have; none is written around an
implementation quirk.
"""

from __future__ import annotations

import pytest

from citations import extract_citations, extract_urls, verify_citations
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
ONE = SOURCES[:1]


# --- H1: no marker is silently dropped ------------------------------------


def test_h1_out_of_range_marker_with_locator_is_flagged():
    """`[S99, p.4]` must be read as a citation of S99, not thrown away."""
    problems = verify_citations("Throughput rose 12% [S99, p.4].", SOURCES)
    assert any("S99" in p for p in problems), problems


def test_h1_space_inside_marker_is_flagged_when_out_of_range():
    """`[S 99]` is a malformed marker, not absence of a marker."""
    problems = verify_citations("Throughput rose 12% [S 99].", SOURCES)
    assert any("99" in p for p in problems), problems


def test_h1_paren_marker_is_range_checked():
    """`(S9)` is a citation attempt and must be range-checked."""
    problems = verify_citations("Throughput rose 12% (S9).", SOURCES)
    assert any("S9" in p or "S9" in p.replace(" ", "") for p in problems), problems


def test_h1_wide_range_is_flagged_not_dropped():
    """`[S1-S9000]` is a broken marker; dropping it hides a bad citation."""
    problems = verify_citations("Trends [S1-S9000] support it.", SOURCES)
    assert problems, "wide range marker was silently dropped"


def test_h1_unparseable_token_inside_marker_is_flagged():
    """A marker with a junk token must not silently vanish."""
    problems = verify_citations("Throughput rose 12% [S1, footnote] .", SOURCES)
    assert any("footnote" in p for p in problems), problems


def test_h1_locator_inside_marker_is_accepted():
    """`[S1, p. 4]` is a normal citation with a page locator, not a defect."""
    assert verify_citations("Throughput rose 12% [S1, p. 4].", ONE) == []


def test_h1_paren_marker_in_range_passes():
    assert verify_citations("Throughput rose 12% (S1).", ONE) == []


def test_h1_spaced_marker_in_range_passes():
    """`[S 1]` is checked leniently: in range, so it grounds the claim."""
    assert extract_citations("Throughput rose 12% [S 1].") == {1}
    assert verify_citations("Throughput rose 12% [S 1].", ONE) == []


def test_h1_bare_number_bracket_is_not_a_marker():
    """`[2024]`/`[12]` are prose or footnotes in brackets, not citations of S2024."""
    assert extract_citations("The audit [2024] found no drift.") == set()
    assert extract_citations("As shown before [12].") == set()
    assert verify_citations("As shown before [12], throughput rose [S1].", ONE) == []


def test_h1_connective_inside_paren_marker_is_accepted():
    """`(S1 and S2)` is a normal way to cite two sources."""
    assert verify_citations("Throughput rose 12% (S1 and S2).", SOURCES) == []


def test_h1_prose_parenthesis_is_not_a_citation():
    """A parenthesised phrase that merely contains an S-number is prose.

    Parentheses are ambiguous (hardware revisions, regions, product codes), so a
    paren group only counts as a citation when its whole body parses as one.
    """
    text = "The throughput held in the (S3 region) and the (new S7 line) [S1]."
    assert extract_citations(text) == {1}
    assert verify_citations(text, ONE) == []


# --- H2: URL blind spots ---------------------------------------------------


def test_h2_ftp_url_is_checked():
    problems = verify_citations("See ftp://invented.example.test/report [S1].", SOURCES)
    assert any("invented.example.test" in p for p in problems), problems


def test_h2_protocol_relative_url_is_checked():
    problems = verify_citations("See //invented.example.test/report [S1].", SOURCES)
    assert any("invented.example.test" in p for p in problems), problems


def test_h2_real_tld_colliding_with_file_extension_is_a_host():
    """`evil.sh/x` is a host with a path; `.sh` is a country TLD, not a script file."""
    assert "https://evil.sh/x" in extract_urls("See evil.sh/x [S1].")


def test_h2_script_filename_is_not_a_host():
    """`build.sh` without a path is a script in prose, not a cited `.sh` host."""
    assert extract_urls("Run build.sh and read report.pdf before the audit [S1].") == set()
    assert verify_citations("Run build.sh and read report.pdf before the audit [S1].", SOURCES) == []


def test_h2_short_uncommon_tld_bare_host_is_checked():
    """`bit.ly` is a real host even with no path."""
    assert extract_urls("Shortener bit.ly [S1].") == {"https://bit.ly"}
    assert verify_citations("Shortener bit.ly [S1].", SOURCES)


def test_h2_idn_host_is_checked():
    problems = verify_citations("See https://f\u00e4lschung.example.test/x [S1].", SOURCES)
    assert any("f\u00e4lschung" in p or "xn--" in p for p in problems), problems


def test_h2_punycode_and_idn_spellings_are_one_source():
    source = [Source(title="M", url="https://m\u00fcnchen.example.test/x", snippet="s")]
    assert verify_citations("See https://xn--mnchen-3ya.example.test/x [S1].", source) == []


def test_h2_protocol_relative_to_retrieved_host_passes():
    seen = extract_urls("As shown //ops.example.test/throughput [S1].")
    assert "//ops.example.test/throughput" in seen
    assert verify_citations("As shown //ops.example.test/throughput [S1].", SOURCES) == []


# --- H3a: dotted names are not hosts --------------------------------------


@pytest.mark.parametrize(
    "dotted",
    [
        "System.Web.UI.Page",
        "Microsoft.AspNetCore.Mvc.Controller",
        "java.lang.StringBuilder",
        "station.throughput.avg",
    ],
)
def test_h3a_dotted_type_names_are_not_hosts(dotted):
    assert extract_urls(f"The type {dotted} is involved [S1].") == set()
    assert verify_citations(f"The type {dotted} is involved [S1].", SOURCES) == []


def test_h3a_fabricated_lowercase_host_still_flagged():
    assert verify_citations("See invented.example.test/report [S1].", SOURCES)


# --- H3b: quotes beyond title + snippet -----------------------------------


def test_h3b_quote_grounded_in_source_content_passes():
    """A retriever that returns full text can ground a quote outside the snippet."""
    source = [
        Source(
            title="Station throughput",
            url="https://ops.example.test/throughput",
            snippet="Summary only.",
            content="Full text: station throughput rose 12% after the reallocation.",
        )
    ]
    assert verify_citations('The report says "station throughput rose 12%" [S1].', source) == []


def test_h3b_quote_outside_every_field_is_flagged():
    source = [Source(title="T", url="https://ops.example.test/throughput", snippet="Summary only.", content="Nothing about it.")]
    problems = verify_citations('The report says "station throughput rose 40%" [S1].', source)
    assert problems, "quote absent from all fields passed"


# --- H3c: parenthesised URLs are not truncated -----------------------------


def test_h3c_parenthesised_url_kept_whole():
    text = "See https://en.wikipedia.org/wiki/Throughput_(operations)."
    assert extract_urls(text) == {"https://en.wikipedia.org/wiki/Throughput_(operations)"}


def test_h3c_parenthesised_url_cited_cleanly():
    source = [Source(title="T", url="https://ops.example.test/throughput_(station)", snippet="s")]
    assert verify_citations("Numbers (https://ops.example.test/throughput_(station)) [S1].", source) == []


def test_h3c_markdown_link_trailing_paren_still_stripped():
    assert extract_urls("See [the doc](https://ops.example.test/throughput) [S1].") == {
        "https://ops.example.test/throughput"
    }


# --- H3d: previous-sentence markers ---------------------------------------


def test_h3d_marker_in_previous_sentence_grounds_quote():
    text = 'Numbers moved [S1]. The log says "station throughput rose 12%".'
    assert verify_citations(text, SOURCES) == []


def test_h3d_previous_sentence_marker_still_has_to_match():
    """Borrowing the previous marker does not let a quote escape its source."""
    text = 'Bending fell [S2]. The log says "station throughput rose 12%".'
    problems = verify_citations(text, SOURCES)
    assert any("quote not found" in p for p in problems), problems
