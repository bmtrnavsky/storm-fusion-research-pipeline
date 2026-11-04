"""Typography is not a claim: a hyphen run, an en dash and an em dash spell the same
word. LaTeX ``Bradley--Terry`` quoted against a source that renders ``Bradley-Terry``
(or ``Bradley–Terry``) is one string, and the quote check must not fail it.

The check still has to be word-aligned: folding dashes must not turn "well--known" into
a match for "wellknown", and it must not ground a quote that is simply absent.
"""

from __future__ import annotations

import pytest

from citations import verify_citations
from retrieval import Source

BRADLEY = Source(
    title="Bradley-Terry ranking",
    url="https://stats.example.test/bradley-terry",
    snippet="The Bradley-Terry model ranks item pairs by a single strength parameter.",
)


def problems(text, sources=(BRADLEY,), require_citation=True):
    return verify_citations(text, list(sources), require_citation=require_citation)


def test_latex_hyphen_run_grounds_against_a_single_hyphen_source():
    text = 'The ranking is pairwise. "The Bradley--Terry model ranks item pairs by a single" [S1].'
    assert problems(text) == []


def test_en_dash_and_em_dash_spellings_are_the_same_word():
    en = 'Pairwise at core: "Bradley\u2013Terry model ranks item pairs" [S1].'
    em = 'Pairwise at core: "Bradley\u2014Terry model ranks item pairs" [S1].'
    assert problems(en) == []
    assert problems(em) == []


def test_quote_written_with_one_hyphen_grounds_against_a_hyphen_run_source():
    source = Source(
        title="LaTeX source",
        url="https://stats.example.test/latex",
        snippet="The Bradley--Terry model ranks item pairs by a single strength parameter.",
    )
    text = '"The Bradley-Terry model ranks item pairs" [S1].'
    assert problems(text, sources=(source,)) == []


def test_dash_folding_does_not_glue_two_words_together():
    text = '"The well--known Bradley-Terry model ranks" [S1].'
    assert problems(text) != []


def test_absent_quote_is_still_flagged_after_normalization():
    text = '"The Bradley-Terry model predicts tomorrow\'s weather" [S1].'
    assert problems(text) != []


def test_hyphenated_claim_still_needs_a_marker():
    text = '"The Bradley--Terry model ranks item pairs" without a citation.'
    assert problems(text) != []


def test_plain_hyphen_quote_unchanged():
    text = '"The Bradley-Terry model ranks item pairs" [S1].'
    assert problems(text) == []
