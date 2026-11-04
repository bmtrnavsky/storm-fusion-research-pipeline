"""DuckDuckGo adapter resilience: rate limits are temporary, so a single 429 must not
end the run. Retry with exponential backoff on the failures that mean "try again"
(429, 5xx, a bot wall, an unparseable empty page) and never on a definitive answer
(400, 404) or after the attempt budget is spent -- the adapter still fails closed.
"""

from __future__ import annotations

import urllib.error

import pytest

from retrieval import DuckDuckGoRetriever, RetrievalError

HTML_ONE_RESULT = """
<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fops.example.test%2Fthroughput">Throughput</a>
<a class="result__snippet" href="#">Line speed caps at 40 boxes/hour.</a>
"""


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _SequenceOpener:
    """Serve a scripted sequence of responses/exceptions, one per open() call."""

    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.calls = 0

    def open(self, req, timeout=None):
        item = self.sequence[min(self.calls, len(self.sequence) - 1)]
        self.calls += 1
        if isinstance(item, BaseException):
            raise item
        return _Resp(item)


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://html.duckduckgo.com/html/", code, "err", {}, None)


def _retriever(sequence, sleeps):
    return DuckDuckGoRetriever(
        opener=_SequenceOpener(sequence),
        max_attempts=3,
        backoff=0.5,
        sleep=sleeps.append,
    )


def test_rate_limit_then_success_recovers():
    sleeps: list[float] = []
    r = _retriever([_http_error(429), HTML_ONE_RESULT.encode()], sleeps)

    sources = r.search("packing station", top_k=1)

    assert [s.url for s in sources] == ["https://ops.example.test/throughput"]
    assert r._opener.calls == 2
    assert sleeps == [0.5]


def test_backoff_doubles_between_attempts_and_gives_up_closed():
    sleeps: list[float] = []
    r = _retriever([_http_error(503)], sleeps)

    with pytest.raises(RetrievalError):
        r.search("packing station")

    assert r._opener.calls == 3
    assert sleeps == [0.5, 1.0]


def test_client_error_is_not_retried():
    sleeps: list[float] = []
    r = _retriever([_http_error(400)], sleeps)

    with pytest.raises(RetrievalError):
        r.search("packing station")

    assert r._opener.calls == 1
    assert sleeps == []


def test_empty_page_is_retried_then_fails_closed():
    sleeps: list[float] = []
    r = _retriever([b"<html><body>anomaly</body></html>"], sleeps)

    with pytest.raises(RetrievalError):
        r.search("packing station")

    assert r._opener.calls == 3
    assert sleeps == [0.5, 1.0]


def test_empty_page_then_results_succeeds():
    sleeps: list[float] = []
    r = _retriever([b"<html>rate limited</html>", HTML_ONE_RESULT.encode()], sleeps)

    sources = r.search("packing station", top_k=1)

    assert sources and sources[0].snippet.startswith("Line speed caps")
    assert sleeps == [0.5]


def test_clean_first_attempt_does_not_sleep():
    sleeps: list[float] = []
    r = _retriever([HTML_ONE_RESULT.encode()], sleeps)

    r.search("packing station", top_k=1)

    assert r._opener.calls == 1
    assert sleeps == []


def test_failure_still_reports_a_retrieval_error_not_a_bare_exception():
    sleeps: list[float] = []
    r = _retriever([urllib.error.URLError("timed out")], sleeps)

    with pytest.raises(RetrievalError) as exc:
        r.search("packing station")

    assert exc.value.code == "retrieval_failed"
