"""Ablation scoring: the OFF condition must score lower, or the harness fails."""

from __future__ import annotations

import json

import ablation
import run_panel


def on_result():
    return {
        "success": True,
        "panel": {"seat_reports": [{"seat": "a", "model": "m", "findings": "f"}], "synthesis": "ok [S1]"},
        "seat_reports": [{"seat": "a", "model": "m", "findings": "Claim [S1]."}],
        "retrieval": {
            "mode": "on",
            "sources": [
                {"title": "T", "url": "https://example.test/a", "snippet": "s"}
            ],
        },
    }


def off_result():
    return {
        "success": True,
        "panel": {"seat_reports": [{"seat": "a", "model": "m", "findings": "f"}], "synthesis": "ok"},
        "seat_reports": [{"seat": "a", "model": "m", "findings": "Claim, no source."}],
        "retrieval": {"mode": "off", "sources": []},
    }


def test_score_rewards_verified_citations():
    assert ablation.score(on_result())["grounded"] is True
    assert ablation.score(off_result())["grounded"] is False


def test_score_flags_fabricated_citation():
    bad = on_result()
    bad["seat_reports"][0]["findings"] = "Claim [S4]."
    scored = ablation.score(bad)
    assert scored["grounded"] is False
    assert scored["citation_problems"]


def test_verdict_is_degraded_and_exit_zero(tmp_path, monkeypatch, capsys):
    def fake_main(argv):
        and_off = argv[-1] == "off"
        print(json.dumps(off_result() if and_off else on_result()))
        return 0

    monkeypatch.setattr(run_panel, "main", fake_main)
    out = tmp_path / "ablation.json"
    code = ablation.main(["panel.json", "--runs", "1", "--out", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))

    assert code == 0
    assert report["verdict"].startswith("degraded")
    assert report["on"]["grounded_rate"] == 1.0
    assert report["off"]["grounded_rate"] == 0.0
