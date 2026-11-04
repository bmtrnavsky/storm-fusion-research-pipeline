"""Labels must match evidence: experimental until grounding is proven (finding #4)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_readme_marks_status_experimental():
    text = read("README.md").lower()
    assert "experimental" in text
    assert "not been validated" in text or "unvalidated" in text


def test_readme_retracts_grounding_claims():
    text = read("README.md")
    forbidden = [
        "ground every claim in retrievable sources",
        "grounded writing",
        "adaptation of Stanford's STORM methodology",
    ]
    for phrase in forbidden:
        assert phrase not in text, f"README still claims: {phrase}"


def test_readme_states_citations_unverified():
    text = read("README.md").lower()
    assert "citation" in text
    assert "not verified" in text or "unverified" in text


@pytest.mark.parametrize("rel", ["PANEL-SPEC.md", "SPEC.md", "docs/use-without-hermes.md"])
def test_docs_retract_grounded_writing(rel):
    text = read(rel).lower()
    assert "grounded writing" not in text, f"{rel} still claims grounded writing"


def test_docs_point_at_permission_boundary():
    text = read("docs/use-without-hermes.md").lower()
    assert "unverified" in text


def test_plugin_description_is_experimental():
    text = read("plugin.yaml").lower()
    assert "experimental" in text
