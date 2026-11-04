"""run_panel.py retrieval wiring: citations checked before anything is returned."""

from __future__ import annotations

import json
import urllib.request

from helpers import RecordingOpener
from retrieval import Source

import run_panel

SOURCES = [
    Source(title="Throughput", url="https://ops.example.test/throughput", snippet="n"),
    Source(title="Ergo", url="https://safety.example.test/ergo", snippet="b"),
]


class FakeRetriever:
    def __init__(self, sources=SOURCES):
        self.sources = sources
        self.calls = []

    def search(self, query, top_k=5):
        self.calls.append((query, top_k))
        return self.sources[:top_k]


def payload(content, finish="stop"):
    return {
        "choices": [{"message": {"content": content}, "finish_reason": finish}],
        "usage": {"total_tokens": 5},
        "model": "fake-model",
    }


def setup(tmp_path, monkeypatch, seat_text, judge_text, extra_argv=()):
    spec = {
        "topic": "Add a packing station?",
        "seats": [{"name": "associate", "brief": "You pack boxes."}],
        "lineup": [{"model": "fake-model"}],
        "judge": {"model": "judge-model"},
    }
    path = tmp_path / "panel.json"
    path.write_text(json.dumps(spec), encoding="utf-8")

    calls = {"n": 0}

    def factory(body):
        i = calls["n"]
        calls["n"] += 1
        return payload(seat_text if i == 0 else judge_text)

    opener = RecordingOpener(factory)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **kw: opener)
    retriever = FakeRetriever()
    monkeypatch.setattr(run_panel, "make_retriever", lambda **kw: retriever)
    argv = [
        str(path),
        "--base-url", "https://api.example.test",
        "--model", "fake-model",
        "--max-tokens", "300",
        "--retrieval", "on",
        "--search-provider", "searx",
        "--search-url", "https://search.example.test",
        "--cache-dir", "none",
        *extra_argv,
    ]
    return argv, opener, retriever


JUDGE_OK = json.dumps(
    {"seat_reports": [{"seat": "associate", "model": "m", "findings": "f"}], "synthesis": "ok"}
)


def test_retrieval_on_passes_sources_and_verifies(tmp_path, monkeypatch, capsys):
    argv, opener, retriever = setup(tmp_path, monkeypatch, "Throughput up [S1].", JUDGE_OK)
    assert run_panel.main(argv) == 0
    out = json.loads(capsys.readouterr().out)

    assert out["success"] is True
    assert out["retrieval"]["mode"] == "on"
    assert [s["url"] for s in out["retrieval"]["sources"]] == [s.url for s in SOURCES]
    prompt = opener.bodies[0]["messages"][0]["content"]
    assert "[S1]" in prompt and SOURCES[0].url in prompt
    assert retriever.calls and retriever.calls[0][1] == 5


def test_fabricated_citation_blocks_run(tmp_path, monkeypatch, capsys):
    argv, opener, _ = setup(tmp_path, monkeypatch, "Throughput triples [S9].", JUDGE_OK)
    assert run_panel.main(argv) == 1
    out = json.loads(capsys.readouterr().out)

    assert out["success"] is False
    assert out["code"] == "citation_mismatch"
    assert len(opener.bodies) == 1  # judge never called


def test_retrieval_off_disables_search(tmp_path, monkeypatch, capsys):
    argv, opener, retriever = setup(tmp_path, monkeypatch, "No refs.", JUDGE_OK)
    argv[argv.index("on")] = "off"

    def boom(**kw):
        raise AssertionError("retriever built while retrieval is off")

    monkeypatch.setattr(run_panel, "make_retriever", boom)
    assert run_panel.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    assert out["retrieval"]["mode"] == "off"
    assert "unverified" in opener.bodies[0]["messages"][0]["content"]


def test_judge_fabricated_citation_blocks_run(tmp_path, monkeypatch, capsys):
    judge = json.dumps(
        {"seat_reports": [{"seat": "associate", "model": "m", "findings": "f"}], "synthesis": "cited [S9]"}
    )
    argv, _, _ = setup(tmp_path, monkeypatch, "Fine [S1].", judge)
    assert run_panel.main(argv) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["code"] == "citation_mismatch"
