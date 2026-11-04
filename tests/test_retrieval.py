"""Retriever contract: real search adapter, cache, top-k, fail-closed config."""

from __future__ import annotations

import json

import pytest

from retrieval import (
    CachedRetriever,
    HttpSearchRetriever,
    RetrievalError,
    Source,
    make_retriever,
    normalize_url,
)


class CountingRetriever:
    def __init__(self, sources=None):
        self.sources = sources or [
            Source(title="A", url="https://example.test/a", snippet="alpha"),
            Source(title="B", url="https://example.test/b", snippet="beta"),
        ]
        self.calls = []

    def search(self, query, top_k=5):
        self.calls.append((query, top_k))
        return self.sources[:top_k]


def test_cached_retriever_serves_repeat_from_cache(tmp_path):
    inner = CountingRetriever()
    cached = CachedRetriever(inner, cache_dir=tmp_path, ttl_seconds=3600)
    first = cached.search("packing station", top_k=2)
    second = cached.search("packing station", top_k=2)

    assert [s.url for s in first] == [s.url for s in second]
    assert len(inner.calls) == 1
    assert list(tmp_path.glob("*.json"))


def test_cache_is_keyed_by_query_and_top_k(tmp_path):
    inner = CountingRetriever()
    cached = CachedRetriever(inner, cache_dir=tmp_path, ttl_seconds=3600)
    cached.search("a", top_k=1)
    cached.search("b", top_k=1)
    cached.search("a", top_k=2)
    assert len(inner.calls) == 3


def test_expired_cache_refetches(tmp_path):
    now = [1000.0]
    inner = CountingRetriever()
    cached = CachedRetriever(
        inner, cache_dir=tmp_path, ttl_seconds=10, clock=lambda: now[0]
    )
    cached.search("q")
    now[0] += 11
    cached.search("q")
    assert len(inner.calls) == 2


def test_top_k_is_passed_through(tmp_path):
    inner = CountingRetriever()
    cached = CachedRetriever(inner, cache_dir=tmp_path)
    out = cached.search("q", top_k=1)
    assert len(out) == 1
    assert inner.calls == [("q", 1)]


def test_http_retriever_parses_searx_shape(monkeypatch):
    payload = {
        "results": [
            {"title": "T1", "url": "https://example.test/1", "content": "snippet 1"},
            {"title": "T2", "url": "https://example.test/2", "content": "snippet 2"},
        ]
    }
    captured = {}

    class Resp:
        def read(self):
            return json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Opener:
        def open(self, req, timeout=None):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.headers)
            return Resp()

    r = HttpSearchRetriever("https://search.example.test", opener=Opener())
    sources = r.search("two words", top_k=2)

    assert [s.title for s in sources] == ["T1", "T2"]
    assert "q=two+words" in captured["url"] or "q=two%20words" in captured["url"]


def test_http_retriever_parses_brave_shape():
    payload = {"web": {"results": [{"title": "B", "url": "https://b.test/x", "description": "d"}]}}

    class Resp:
        def read(self):
            return json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Opener:
        def open(self, req, timeout=None):
            return Resp()

    r = HttpSearchRetriever("https://api.search.brave.com/res/v1/web/search", provider="brave", api_key="k", opener=Opener())
    assert [s.url for s in r.search("q")] == ["https://b.test/x"]


def test_ddg_html_parser_unwraps_redirects():
    from retrieval import DuckDuckGoRetriever
    html = """
    <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fops.example.test%2Fthroughput&rut=x">Throughput <b>data</b></a>
    <a class="result__snippet" href="#">Line speed caps at 40 boxes/hour.</a>
    <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fsafety.example.test%2Fergo">Ergonomics</a>
    <a class="result__snippet" href="#">Bending risk.</a>
    """

    class Resp:
        def read(self):
            return html.encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Opener:
        def open(self, req, timeout=None):
            return Resp()

    r = DuckDuckGoRetriever(opener=Opener())
    sources = r.search("q", top_k=2)
    assert [s.url for s in sources] == [
        "https://ops.example.test/throughput",
        "https://safety.example.test/ergo",
    ]
    assert "40 boxes" in sources[0].snippet


def test_make_retriever_supports_ddg_without_url():
    from retrieval import DuckDuckGoRetriever, make_retriever as build
    assert isinstance(build(provider="ddg", cache_dir="none"), DuckDuckGoRetriever)


def test_plain_http_is_refused_outside_loopback():
    with pytest.raises(RetrievalError):
        HttpSearchRetriever("http://search.example.test")


def test_make_retriever_off_by_default():
    assert make_retriever() is None


def test_make_retriever_rejects_unknown_provider():
    with pytest.raises(RetrievalError):
        make_retriever(provider="mystery", url="https://search.example.test")


def test_make_retriever_requires_url():
    with pytest.raises(RetrievalError):
        make_retriever(provider="searx")


def test_normalize_url():
    assert normalize_url("HTTPS://Example.Test/a/?b=1#frag") == "https://example.test/a/?b=1"
