"""Labeled evaluation set for the citation verifier (precision/recall, closed ledger).

``citations.verify_citations`` is the merge gate: a report that invents a URL, a
quote, or a marker must fail, and a report that grounds every claim must pass.
This module scores that gate against hand-labeled cases instead of trusting that
the fabrication tests cover the space.

Each case carries a ground-truth label ``should_flag``:

* ``True``  — the report is bad (fabricated URL, absent quote, mismatched or
  missing marker, citation with no retrieval) and the gate MUST reject it.
* ``False`` — the report is a legitimate, fully grounded report and the gate MUST
  accept it.

Treating "reject" as the positive class gives the two numbers that matter for a
merge gate:

* ``precision`` = rejected / (rejected and truly bad) — how often a rejection is
  for a real defect. Low precision means the gate cries wolf and blocks honest
  work.
* ``recall`` = caught bad / all bad, ``false_negative_rate`` = 1 - recall — how
  often fabrication walks through the gate. This is the number that matters most:
  a fabricated citation that passes is worse than no gate, because the panel then
  reports invented grounding as retrieved.

Every case is expected to agree with the verifier: there are no pinned gaps left.
``test_no_case_diverges_from_ground_truth`` fails the moment any case disagrees,
so a regression cannot hide behind an ``xfail`` marker.

This ledger is not independent evidence. The cases, the fixtures and the fixes were
written by the same hand, so agreement here shows self-consistency, not coverage.
``tests/test_verifier_heldout.py`` is the independent check: fresh adversarial cases
from a different domain, labeled from the reporting contract, scored against bounds.

Run ``pytest tests/test_verifier_eval.py -s`` to print the full table.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from citations import verify_citations
from retrieval import Source

# --- fixture sources -------------------------------------------------------

THROUGHPUT = Source(
    title="Station throughput",
    url="https://ops.example.test/throughput",
    snippet="Station throughput rose 12% after the reallocation.",
)
ERGONOMICS = Source(
    title="Ergonomics",
    url="https://safety.example.test/ergo",
    snippet="Operators bend 30% less with the raised bench.",
)
SOURCES = [THROUGHPUT, ERGONOMICS]
# Same source as THROUGHPUT but with the trailing slash the retriever returned.
TRAILING_SLASH = [
    Source(title="Station throughput", url="https://ops.example.test/throughput/", snippet="Station throughput rose 12%.")
]


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    text: str
    sources: list
    should_flag: bool
    require_citation: bool = True
    note: str = ""


CASES: list[Case] = [
    # --- clean reports: the gate must accept -------------------------------
    Case(
        "clean_multi_marker",
        "clean",
        "Throughput rises 12% [S1]. Bending drops [S2].",
        SOURCES,
        should_flag=False,
        note="baseline happy path",
    ),
    Case(
        "clean_verbatim_quote",
        "clean",
        'Throughput rose after the change: "station throughput rose 12%" [S1].',
        SOURCES,
        should_flag=False,
        note="quote is a substring of the cited snippet",
    ),
    Case(
        "clean_curly_quote",
        "clean",
        "The log says \u201cstation throughput rose 12%\u201d [S1].",
        SOURCES,
        should_flag=False,
        note="curly quotes are a normal model output",
    ),
    Case(
        "clean_ellipsis_same_source",
        "clean",
        'It said "station throughput ... 12% after the reallocation" [S1].',
        SOURCES,
        should_flag=False,
        note="ellipsis elides words inside one snippet",
    ),
    Case(
        "clean_title_only_quote",
        "clean",
        'Per "Station throughput" [S1] the change landed.',
        SOURCES,
        should_flag=False,
        note="the checkable surface is the title plus every text field the source carries",
    ),
    Case(
        "clean_retrieved_url_cited",
        "clean",
        "Numbers move (https://ops.example.test/throughput) [S1].",
        SOURCES,
        should_flag=False,
        note="exact retrieved URL",
    ),
    Case(
        "clean_markdown_link",
        "clean",
        "As shown in [the report](https://ops.example.test/throughput) [S1].",
        SOURCES,
        should_flag=False,
        note="markdown link to a retrieved URL is still a retrieved URL",
    ),
    Case(
        "clean_apostrophes",
        "clean",
        "The operator's bench is the plant's best, and throughput didn't fall [S1].",
        SOURCES,
        should_flag=False,
        note="possessives and contractions are not single-quoted citations",
    ),
    Case(
        "clean_dotted_metric_name",
        "clean",
        "The station.throughput series is the one to watch [S1].",
        SOURCES,
        should_flag=False,
        note="a dotted metric name is not a host",
    ),
    Case(
        "clean_schemeless_url_cited",
        "clean",
        "Numbers move (ops.example.test/throughput) [S1].",
        SOURCES,
        should_flag=False,
        note="the retrieved page written without a scheme is still the retrieved page",
    ),
    Case(
        "clean_retrieval_off_prose",
        "clean",
        "Throughput rose about 12% and bending fell.",
        [],
        should_flag=False,
        require_citation=False,
        note="retrieval-off ablation: prose, no markers, nothing to ground",
    ),
    # --- fabricated URLs ---------------------------------------------------
    Case(
        "url_not_retrieved",
        "fabricated_url",
        "Automation cut headcount 40% (https://invented.example.test/report) [S1].",
        SOURCES,
        should_flag=True,
    ),
    Case(
        "url_near_miss_path",
        "fabricated_url",
        "See https://ops.example.test/throughput-v2 [S1].",
        SOURCES,
        should_flag=True,
        note="near-miss path on a real host",
    ),
    Case(
        "url_uppercase_scheme",
        "fabricated_url",
        "See HTTPS://invented.example.test/report [S1].",
        SOURCES,
        should_flag=True,
        note="the scheme match is case-insensitive: the uppercase spelling is extracted and rejected as unretrieved",
    ),
    Case(
        "url_no_scheme",
        "fabricated_url",
        "See invented.example.test/report [S1].",
        SOURCES,
        should_flag=True,
        note="a scheme-less host with a path is read as a host, so the missing retrieval shows",
    ),
    # --- quotes absent from the cited source -------------------------------
    Case(
        "quote_absent",
        "absent_quote",
        'The report says "throughput tripled overnight" [S1].',
        SOURCES,
        should_flag=True,
    ),
    Case(
        "quote_number_swapped",
        "absent_quote",
        'It states "station throughput rose 42%" [S1].',
        SOURCES,
        should_flag=True,
        note="one fabricated digit inside an otherwise real quote",
    ),
    Case(
        "quote_long_fabrication",
        "absent_quote",
        'It states "' + ("invented analysis of station throughput " * 12) + '" [S1].',
        SOURCES,
        should_flag=True,
        note="a ~456-char fabricated quote is still a quote; the 4000-char cap only guards a runaway match",
    ),
    Case(
        "quote_multiline",
        "absent_quote",
        'It states "station throughput\nquadrupled overnight" [S1].',
        SOURCES,
        should_flag=True,
        note="a quote wrapped across a newline is still scanned",
    ),
    Case(
        "quote_single_quoted",
        "absent_quote",
        "It said 'station throughput tripled overnight' [S1].",
        SOURCES,
        should_flag=True,
        note="standalone single quotes are scanned too, so the fabrication cannot hide there",
    ),
    Case(
        "quote_single_curly",
        "absent_quote",
        "It said \u2018station throughput tripled overnight\u2019 [S1].",
        SOURCES,
        should_flag=True,
        note="curly single quotes are unambiguous quote delimiters",
    ),
    # --- marker mismatches -------------------------------------------------
    Case(
        "marker_out_of_range",
        "marker_mismatch",
        "Throughput rises 12% [S9].",
        SOURCES,
        should_flag=True,
    ),
    Case(
        "marker_zero",
        "marker_mismatch",
        "Claim [S0].",
        SOURCES,
        should_flag=True,
    ),
    Case(
        "quote_from_s2_cited_as_s1",
        "marker_mismatch",
        'One seat wrote "operators bend 30% less with the raised bench" [S1].',
        SOURCES,
        should_flag=True,
        note="right words, wrong marker",
    ),
    Case(
        "marker_range_syntax",
        "marker_mismatch",
        "Trends [S1-S2] both support it.",
        SOURCES,
        should_flag=False,
        note="range markers are expanded, so [S1-S2] cites both retrieved sources",
    ),
    Case(
        "cites_with_no_retrieval",
        "marker_mismatch",
        "Claim [S1].",
        [],
        should_flag=True,
    ),
    # --- uncited quotes ----------------------------------------------------
    Case(
        "uncited_quote_straight",
        "uncited_quote",
        'Analysts observed "station throughput rose 47% after automation".',
        SOURCES,
        should_flag=True,
    ),
    Case(
        "uncited_quote_curly",
        "uncited_quote",
        "Analysts said \u201cstation throughput rose 47%\u201d.",
        SOURCES,
        should_flag=True,
    ),
    Case(
        "quote_in_code_fence",
        "uncited_quote",
        "```\n\"station throughput rose 12%\"\n``` [S1]",
        SOURCES,
        should_flag=True,
        note="marker outside the fence, quote inside it",
    ),
    # --- formatting edge cases --------------------------------------------
    Case(
        "marker_after_terminal_period",
        "edge_formatting",
        'The report states "station throughput rose 12%". [S1]',
        SOURCES,
        should_flag=False,
        note="the quote's own sentence, trailing punctuation and a trailing marker all count as its scope",
    ),
    Case(
        "ellipsis_across_two_sources",
        "edge_formatting",
        'Together: "station throughput rose 12% ... operators bend 30% less" [S1, S2].',
        SOURCES,
        should_flag=False,
        note="each fragment may be grounded in a different one of the cited sources",
    ),
    Case(
        "trailing_slash_normalization",
        "edge_formatting",
        "Numbers move (https://ops.example.test/throughput) [S1].",
        TRAILING_SLASH,
        should_flag=False,
        note="normalize_url drops a trailing path slash, so the retriever's spelling is the same source",
    ),
    Case(
        "quote_inside_markdown_link",
        "edge_formatting",
        'See [the doc](https://invented.example.test/x) "invented finding" [S1].',
        SOURCES,
        should_flag=True,
        note="two defects: unretrieved URL and ungrounded quote",
    ),
]


def _flagged(case: Case) -> bool:
    return bool(
        verify_citations(case.text, case.sources, require_citation=case.require_citation)
    )


def score(cases: list[Case]) -> dict:
    tp = sum(1 for c in cases if c.should_flag and _flagged(c))
    fp = sum(1 for c in cases if not c.should_flag and _flagged(c))
    fn = sum(1 for c in cases if c.should_flag and not _flagged(c))
    tn = sum(1 for c in cases if not c.should_flag and not _flagged(c))
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "n": len(cases),
        "precision": tp / (tp + fp) if tp + fp else 1.0,
        "recall": tp / (tp + fn) if tp + fn else 1.0,
        "false_negative_rate": fn / (tp + fn) if tp + fn else 0.0,
    }


def render_table(cases: list[Case]) -> str:
    rows = ["| # | case | category | label | verifier | verdict |", "|---|------|----------|-------|----------|---------|"]
    for i, case in enumerate(cases, start=1):
        flagged = _flagged(case)
        truth = "flag" if case.should_flag else "pass"
        got = "flag" if flagged else "pass"
        if flagged == case.should_flag:
            outcome = "ok"
        elif case.should_flag:
            outcome = "FALSE NEGATIVE"
        else:
            outcome = "FALSE POSITIVE"
        rows.append(
            f"| {i} | `{case.id}` | {case.category} | {truth} | {got} | {outcome} |"
        )
    return "\n".join(rows)


def test_verifier_scores_within_bounds():
    """Hold precision/recall inside bounds instead of pinning an exact count.

    This ledger was written by the same hand that wrote the verifier, so an exact
    ``(18, 0, 0, 15)`` pin would only prove the two agree with each other — and it
    would break every time a case is added or a case id is renamed. What stays is a
    zero-tolerance gate on both error directions: one missed fabrication or one rejected
    honest report fails the suite. A ``<= 1`` bound reads as slack, and slack in a
    verifier test is a hole — it absorbed exactly the single-case regression the suite
    exists to catch. The independent check that
    the cases are not merely self-consistent lives in
    ``tests/test_verifier_heldout.py``, which was written from the reporting
    contract against fresh adversarial cases.
    """
    stats = score(CASES)
    assert stats["n"] >= 30, stats
    assert stats["fp"] == 0, stats
    assert stats["fn"] == 0, stats
    assert stats["precision"] >= 0.94, stats
    assert stats["recall"] >= 0.94, stats
    assert stats["false_negative_rate"] <= 0.06, stats


PARAMS = [pytest.param(case, id=case.id) for case in CASES]


@pytest.mark.parametrize("case", PARAMS)
def test_case_matches_ground_truth(case: Case):
    """Every labeled case must agree with the verifier, in both directions."""
    problems = verify_citations(case.text, case.sources, require_citation=case.require_citation)
    if case.should_flag:
        assert problems, f"{case.id}: fabricated citation passed the gate"
    else:
        assert problems == [], f"{case.id}: honest report was rejected: {problems}"


def test_no_case_diverges_from_ground_truth():
    """The ledger is closed: no labeled case may disagree with the verifier."""
    diverging = {c.id for c in CASES if _flagged(c) != c.should_flag}
    assert diverging == set(), f"verifier diverges from ground truth: {sorted(diverging)}"


if __name__ == "__main__":  # pragma: no cover - manual report
    import sys
    from pathlib import Path

    for path in (Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    print(render_table(CASES))
    print()
    stats = score(CASES)
    print(
        f"n={stats['n']} tp={stats['tp']} fp={stats['fp']} fn={stats['fn']} tn={stats['tn']} "
        f"precision={stats['precision']:.3f} recall={stats['recall']:.3f} "
        f"fnr={stats['false_negative_rate']:.3f}"
    )
