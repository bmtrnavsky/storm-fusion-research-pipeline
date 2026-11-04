"""Held-out adversarial evaluation for the citation verifier.

This set is deliberately independent of ``tests/test_verifier_eval.py``: a
different reviewer, a different domain (clinical trial + freight sources), and
cases invented from *how a report can fabricate* rather than from the current
implementation. It exists because a single ledger that was written and tuned
alongside the code proves nothing about generalization — the same hand picked the
cases, the fixtures, and the fixes.

Rules for this file:

* no case is copied from the tuned ledger or from ``test_verifier_round2.py``;
* labels are decided from the reporting contract (a marker must name a retrieved
  source, a URL must be a retrieved URL, a quote must be checkable), not from what
  the verifier happens to do today;
* scoring is bounds-based: the gate must be near-perfect, not exactly this count,
  so adding a case does not require rewriting an exact pin.

Reject is the positive class: precision = a rejection is for a real defect,
recall = no fabricated citation walks through.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from citations import verify_citations
from retrieval import Source

TRIAL = Source(
    title="Trial 402 report",
    url="https://trials.example.test/402?site=oslo",
    snippet="The trial enrolled 1,204 patients across nine sites.",
)
FREIGHT = Source(
    title="Freight cost index",
    url="https://freight.example.test/index",
    snippet="Line-haul rates fell 8.4% in the third quarter.",
)
REGISTRY = Source(
    title="Trial registry entry",
    url="https://trials.example.test:8443/402",
    snippet="Enrollment target was 1,200 patients.",
)
SOURCES = [TRIAL, FREIGHT, REGISTRY]
DEPOT = Source(
    title="Depot note",
    url="https://depot.example.test/notes",
    snippet="Cold-chain excursions were logged twice.",
    content=(
        "Cold-chain excursions were logged twice. The audit found no temperature "
        "breach above 8 C."
    ),
)


@dataclass(frozen=True)
class HeldCase:
    id: str
    text: str
    should_flag: bool
    sources: list
    require_citation: bool = True
    why: str = ""


HELD: list[HeldCase] = [
    # --- honest reports the gate must accept -------------------------------
    HeldCase(
        "held_clean_table_row",
        "| metric | value | source |\n| enrollment | 1,204 | [S1] |",
        False,
        SOURCES,
        why="a table cell marker is a normal citation form",
    ),
    HeldCase(
        "held_clean_query_string_url",
        "Enrollment numbers (https://trials.example.test/402?site=oslo) [S1].",
        False,
        SOURCES,
        why="the retrieved URL carries a query string; citing it verbatim is honest",
    ),
    HeldCase(
        "held_clean_url_with_port",
        "Targets (https://trials.example.test:8443/402) [S3].",
        False,
        SOURCES,
        why="port is part of the retrieved URL",
    ),
    HeldCase(
        "held_clean_email_address",
        "Write to jane.doe@trials.example.test for the raw data [S1].",
        False,
        SOURCES,
        why="an email address is not a cited URL",
    ),
    HeldCase(
        "held_clean_version_number",
        "We ran pandas 2.1.4 for the export [S2].",
        False,
        SOURCES,
        why="a version number is not a host",
    ),
    HeldCase(
        "held_clean_attached_filename",
        "See the attached report.pdf for the counts [S1].",
        False,
        SOURCES,
        why="a filename is not a cited URL",
    ),
    HeldCase(
        "held_clean_marker_leading_zero",
        "Enrollment held at 1,204 [S01].",
        False,
        SOURCES,
        why="a zero-padded marker still names source 1",
    ),
    HeldCase(
        "held_clean_pages_locator",
        "Enrollment held at 1,204 [S1, pp. 12-13].",
        False,
        SOURCES,
        why="page locators are part of normal citation style",
    ),
    HeldCase(
        "held_clean_marker_inner_spaces",
        "Enrollment held at 1,204 [ S1 ].",
        False,
        SOURCES,
        why="inner whitespace in a marker is a formatting quirk, not a defect",
    ),
    HeldCase(
        "held_clean_quote_with_period",
        'The abstract reads "The trial enrolled 1,204 patients." [S1].',
        False,
        SOURCES,
        why="quote is verbatim including the sentence period",
    ),
    HeldCase(
        "held_clean_marker_previous_sentence",
        'Line-haul rates moved [S2]. The index says "line-haul rates fell 8.4%".',
        False,
        SOURCES,
        why="a marker ending the prior sentence still grounds the quote",
    ),
    HeldCase(
        "held_clean_adjacent_markers",
        "Enrollment rose [S1][S2].",
        False,
        SOURCES,
        why="adjacent markers are two citations",
    ),
    HeldCase(
        "held_clean_full_content_source",
        'The audit says "no temperature breach above 8 C" [S1].',
        False,
        [DEPOT],
        why="a retriever that returns page content grounds quotes outside the snippet",
    ),
    HeldCase(
        "held_clean_schemeless_cited_host",
        "Numbers move (depot.example.test/notes) [S1].",
        False,
        [DEPOT],
        why="host without a scheme is still the retrieved page",
    ),
    # --- fabricated URLs ---------------------------------------------------
    HeldCase(
        "held_flag_url_query_string",
        "See https://invented.example.test/402?id=7&x=1 [S1].",
        True,
        SOURCES,
        why="unretrieved host with a query string",
    ),
    HeldCase(
        "held_flag_url_with_port",
        "See https://invented.example.test:8443/report [S1].",
        True,
        SOURCES,
        why="port does not make an unretrieved host retrieved",
    ),
    HeldCase(
        "held_flag_www_schemeless",
        "See www.invented.example.test/report [S1].",
        True,
        SOURCES,
        why="www-prefixed host without a scheme",
    ),
    HeldCase(
        "held_flag_angle_bracket_url",
        "See <https://invented.example.test/x> [S1].",
        True,
        SOURCES,
        why="angle brackets around a URL are prose delimiters",
    ),
    HeldCase(
        "held_flag_ftp_url_with_parens",
        "Mirror: ftp://invented.example.test/pub/data_(2024) [S1].",
        True,
        SOURCES,
        why="ftp is a retrievable URL scheme and this host was never retrieved",
    ),
    HeldCase(
        "held_flag_idn_host",
        "See https://\u4f8b\u3048.example.test/x [S1].",
        True,
        SOURCES,
        why="an IDN host is a host; unretrieved is fabricated",
    ),
    HeldCase(
        "held_flag_suffix_spoof",
        "See https://trials.example.test.evil.example/report [S1].",
        True,
        SOURCES,
        why="a retrieved host used as a prefix of an attacker host is not retrieved",
    ),
    # --- markers -----------------------------------------------------------
    HeldCase(
        "held_flag_paren_marker_out_of_range",
        "Enrollment held at 1,204 (S7).",
        True,
        SOURCES,
        why="parenthesised marker naming a source that does not exist",
    ),
    HeldCase(
        "held_flag_marker_with_chapter",
        "Enrollment held at 1,204 [S12, ch. 3].",
        True,
        SOURCES,
        why="locator must not hide an out-of-range source number",
    ),
    HeldCase(
        "held_flag_marker_junk_token",
        "Enrollment held at 1,204 [S1, footnote 3].",
        True,
        SOURCES,
        why="an unreadable token inside a marker must be reported, not skipped",
    ),
    HeldCase(
        "held_flag_prose_in_brackets",
        "Enrollment held at 1,204 [see source one].",
        True,
        SOURCES,
        why="a bracketed phrase is not a checkable citation",
    ),
    # --- quotes ------------------------------------------------------------
    HeldCase(
        "held_flag_quote_digit_swap",
        'The abstract says "the trial enrolled 1,304 patients" [S1].',
        True,
        SOURCES,
        why="one fabricated digit inside a real quote",
    ),
    HeldCase(
        "held_flag_quote_curly_single",
        "It said \u2018line-haul rates fell 3%\u2019 [S2].",
        True,
        SOURCES,
        why="curly single quotes are quote delimiters",
    ),
    HeldCase(
        "held_flag_quote_wrong_source",
        'The index says "the trial enrolled 1,204 patients" [S2].',
        True,
        SOURCES,
        why="real words, wrong source",
    ),
    HeldCase(
        "held_flag_quote_blockquote_uncited",
        '> "line-haul rates fell 8.4% in the third quarter"',
        True,
        SOURCES,
        why="a blockquoted claim with no marker is uncheckable",
    ),
    HeldCase(
        "held_flag_two_claims_one_fake_url",
        "Rates fell 8.4% [S2] and margins rose (https://invented.example.test/m) [S1].",
        True,
        SOURCES,
        why="one real citation does not launder a fabricated URL beside it",
    ),
]


def _flagged(case: HeldCase) -> bool:
    return bool(
        verify_citations(case.text, case.sources, require_citation=case.require_citation)
    )


def _stats(cases: list[HeldCase]) -> dict:
    tp = sum(1 for c in cases if c.should_flag and _flagged(c))
    fp = sum(1 for c in cases if not c.should_flag and _flagged(c))
    fn = sum(1 for c in cases if c.should_flag and not _flagged(c))
    tn = sum(1 for c in cases if not c.should_flag and not _flagged(c))
    return {
        "n": len(cases),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else 1.0,
        "recall": tp / (tp + fn) if tp + fn else 1.0,
    }


def test_heldout_set_is_not_the_tuned_ledger():
    """This set must stay independent: overlapping ids would mean a copy, not a test."""
    from test_verifier_eval import CASES

    tuned_ids = {case.id for case in CASES}
    assert not ({case.id for case in HELD} & tuned_ids)


def test_heldout_scores_within_bounds():
    stats = _stats(HELD)
    assert stats["n"] >= 28, stats
    assert stats["fp"] == 0, stats
    assert stats["fn"] == 0, stats
    assert stats["precision"] >= 0.95, stats
    assert stats["recall"] >= 0.95, stats


HELD_PARAMS = [pytest.param(case, id=case.id) for case in HELD]


@pytest.mark.parametrize("case", HELD_PARAMS)
def test_heldout_case_matches_contract(case: HeldCase):
    problems = verify_citations(case.text, case.sources, require_citation=case.require_citation)
    if case.should_flag:
        assert problems, f"{case.id}: fabricated citation passed the gate ({case.why})"
    else:
        assert problems == [], f"{case.id}: honest report rejected ({case.why}): {problems}"
