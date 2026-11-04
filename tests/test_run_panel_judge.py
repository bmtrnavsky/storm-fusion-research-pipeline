"""Regression tests for run_panel.py's judge path (gated review finding #1)."""

from __future__ import annotations

import json
import urllib.request

import pytest
from helpers import RecordingOpener

import run_panel
import panel


def payload(content: str, finish_reason: str = "stop"):
    return {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {"total_tokens": 5},
        "model": "fake-model",
    }


def install_opener(monkeypatch, opener):
    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **kw: opener)
    return opener


def test_complete_raises_on_length(monkeypatch):
    opener = install_opener(monkeypatch, RecordingOpener(lambda body: payload("cut", "length")))
    with pytest.raises(panel.PanelError) as exc:
        run_panel.complete(
            [{"role": "user", "content": "hi"}],
            {"model": "fake-model"},
            {"model": "fake-model", "base_url": "https://api.example.test", "api_key_env": "STORM_TEST_KEY"},
            None,
            128,
            5,
            type("A", (), {"allow_http_loopback": False})(),
            {},
        )
    assert exc.value.code == "truncated"
    assert "max_tokens" in str(exc.value)
    assert opener.bodies[0]["max_tokens"] == 128


def write_spec(tmp_path, **extra):
    spec = {
        "topic": "Should the DC add a second packing station?",
        "seats": [{"name": "associate", "brief": "You pack boxes."}],
        "lineup": [{"model": "fake-model"}],
        "judge": {"model": "judge-model"},
        **extra,
    }
    path = tmp_path / "panel.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return str(path)


def run_main(monkeypatch, tmp_path, contents, **body_extra):
    """contents: list of judge/seat response contents, in call order."""
    calls = {"n": 0}

    def factory(body):
        i = calls["n"]
        calls["n"] += 1
        finish = body_extra.get("finish_reason", "stop")
        return payload(contents[i], finish)

    opener = install_opener(monkeypatch, RecordingOpener(factory))
    argv = [
        write_spec(tmp_path),
        "--base-url",
        "https://api.example.test",
        "--model",
        "fake-model",
        "--max-tokens",
        "300",
        "--allow-endpoint",
        "https://api.example.test",
    ]
    code = run_panel.main(argv)
    return code, opener.bodies


def test_empty_judge_returns_failure(monkeypatch, tmp_path, capsys):
    code, bodies = run_main(monkeypatch, tmp_path, ["seat finding", ""])
    out = json.loads(capsys.readouterr().out)

    assert code == 1
    assert out["success"] is False
    assert out["code"] == "empty_judge"
    assert "panel" not in out


def test_unparsed_judge_returns_failure(monkeypatch, tmp_path, capsys):
    code, _ = run_main(monkeypatch, tmp_path, ["seat finding", "I would pick option B."])
    out = json.loads(capsys.readouterr().out)

    assert code == 1
    assert out["success"] is False
    assert out["code"] == "invalid_judge_json"


def test_judge_length_returns_failure(monkeypatch, tmp_path, capsys):
    code, _ = run_main(
        monkeypatch, tmp_path, ["seat finding", '{"seat_reports": [], "synthesis": "x"}'],
        finish_reason="length",
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["code"] == "truncated"


def test_judge_gets_separate_budget(monkeypatch, tmp_path, capsys):
    judge_body = {
        "seat_reports": [{"seat": "associate", "model": "m", "findings": "f"}],
        "synthesis": "ok",
    }
    code, bodies = run_main(
        monkeypatch, tmp_path, ["seat finding", json.dumps(judge_body)]
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["success"] is True, out

    # 1 seat call + 1 judge call
    assert [b["model"] for b in bodies] == ["fake-model", "judge-model"]
    assert bodies[0]["max_tokens"] == 300
    assert bodies[1]["max_tokens"] == panel.JUDGE_DEFAULT_MAX_TOKENS
    assert out["budgets"] == {"generation": 300, "judge": panel.JUDGE_DEFAULT_MAX_TOKENS}


def test_cli_judge_budget_flag(monkeypatch, tmp_path, capsys):
    judge_body = {"seat_reports": [{"seat": "a", "model": "m", "findings": "f"}], "synthesis": "ok"}
    opener = install_opener(
        monkeypatch,
        RecordingOpener(lambda body: payload("seat" if len(opener.bodies) == 0 else json.dumps(judge_body))),
    )
    argv = [
        write_spec(tmp_path),
        "--base-url", "https://api.example.test",
        "--model", "fake-model",
        "--max-tokens", "300",
        "--judge-max-tokens", "5000",
        "--allow-endpoint", "https://api.example.test",
    ]
    assert run_panel.main(argv) == 0
    assert opener.bodies[1]["max_tokens"] == 5000


def test_judge_failure_preserves_seat_reports(monkeypatch, tmp_path, capsys):
    code, _ = run_main(monkeypatch, tmp_path, ["seat finding", ""])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["seat_reports"][0]["findings"] == "seat finding"
