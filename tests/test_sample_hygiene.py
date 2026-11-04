"""The shipped sample report must not leak vault internals (gated review finding #3)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "sample-research"

# Identifiers that only make sense inside Brad's private Obsidian vault.
VAULT_TERMS = [
    "Living Wiki",
    "Obsidian vault",
    "Hindsight",
    "Dual-Horizon Memory Model",
    "PKM Knowledge Systems",
    "RAG Architecture notes",
    "triple-based representation",
    "Retain/Recall/Reflect",
    "wiki notes",
    "vault",
]


@pytest.mark.parametrize("path", sorted(SAMPLE_DIR.glob("*.md")), ids=lambda p: p.name)
def test_no_vault_internals_in_samples(path: Path):
    text = path.read_text(encoding="utf-8")
    hits = [term for term in VAULT_TERMS if term.lower() in text.lower()]
    assert not hits, f"{path.name} leaks vault internals: {hits}"


def test_pkm_sample_has_no_vault_section():
    text = (SAMPLE_DIR / "pkm-vs-pcm-2026-06-23.md").read_text(encoding="utf-8")
    assert "Vault Knowledge" not in text
