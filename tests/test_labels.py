"""Docs must describe what the run actually enforces.

The old posture ("experimental, unvalidated, citations unverified") was written before
retrieval and the verifier existed. These tests pin the current contract: docs say the
panel is grounded, and nothing in the install path calls the tool unvalidated.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_readme_leads_with_install():
    text = read("README.md")
    assert "hermes plugins install storm-fusion-research" in text
    assert text.index("## Install") < text.index("## What the verifier enforces")


def test_readme_states_grounding_is_enforced():
    text = read("README.md")
    assert "[S#]" in text
    assert "CitationError" in text
    assert "verifier" in text.lower()
    assert "retrieval" in text.lower()


def test_readme_does_not_undersell_the_verifier():
    text = read("README.md").lower()
    for phrase in ("unvalidated", "not been validated", "citations are unverified"):
        assert phrase not in text, f"README still hedges: {phrase}"


def test_docs_do_not_deny_enforcement():
    for rel in ("SPEC.md", "PANEL-SPEC.md"):
        text = read(rel).lower()
        assert "no citation verifier" not in text, f"{rel} denies the verifier"
        assert "not grounded" not in text, f"{rel} denies grounding"
        assert "grounded writing" not in text, f"{rel} still claims grounded writing"


def test_plugin_description_is_current():
    text = read("plugin.yaml").lower()
    assert "experimental" not in text
    assert "unvalidated" not in text
    assert "unverified" not in text


def test_version_is_consistent_across_install_surface():
    plugin = read("plugin.yaml")
    version = re.search(r"^version:\s*(\S+)$", plugin, re.MULTILINE).group(1)
    assert version in read("README.md"), "README badge is stale"
    assert version in read("PANEL-SPEC.md"), "PANEL-SPEC is stale"
    assert version in read("CHANGELOG.md"), "CHANGELOG has no entry for this version"


def test_use_without_hermes_documents_the_verifier():
    text = read("docs/use-without-hermes.md")
    assert "citations.py" in text
    assert "--retrieval" in text


def test_docs_cite_the_caps_the_code_enforces():
    import run_panel

    seats, slots = run_panel.MAX_SEATS, run_panel.MAX_SLOTS
    expected = f"{seats} seats x {slots} slots"
    for rel in ("README.md", "SPEC.md"):
        flat = re.sub(r"\s+", " ", read(rel))
        assert expected in flat, f"{rel} omits the cap the code enforces"

