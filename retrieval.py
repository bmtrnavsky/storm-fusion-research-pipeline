"""Pluggable web retrieval for the panel.

Design constraints:
- stdlib only, like the rest of the repo;
- a real search backend, not a memorized list: SearXNG-compatible JSON or Brave;
- top-k and an on-disk cache (same query twice does not spend two searches);
- fail closed: a configured-but-broken retriever raises instead of silently
  producing an ungrounded run.

Configuration is environment-only so a panel input file can never point the
retriever at an arbitrary host:

    STORM_SEARCH_PROVIDER=searx|brave
    STORM_SEARCH_URL=https://search.example.test   (SearXNG base or Brave endpoint)
    STORM_SEARCH_API_KEY=...                        (Brave only)
    STORM_CACHE_DIR=.storm-cache                    (default)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


class RetrievalError(RuntimeError):
    code = "retrieval_failed"


@dataclass(frozen=True)
class Source:
    title: str
    url: str
    snippet: str = ""
    # Optional longer text when a retriever returns page content rather than a
    # snippet. The citation verifier grounds quotes against it when present.
    content: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Source":
        content = str(data.get("content") or "")
        return cls(
            title=str(data.get("title", "")),
            url=str(data.get("url", "")),
            snippet=str(data.get("snippet") or content),
            content=content,
        )


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[Source]: ...


def normalize_url(url: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


class CachedRetriever:
    """Deterministic disk cache in front of any retriever (TTL, query+top_k key)."""

    def __init__(self, inner: Retriever, cache_dir, ttl_seconds: int = 86400, clock=time.time):
        self.inner = inner
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, query: str, top_k: int) -> Path:
        material = f"{type(self.inner).__name__}|{query}|{top_k}"
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def search(self, query: str, top_k: int = 5) -> list[Source]:
        path = self._path(query, top_k)
        now = self.clock()
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if now - float(payload.get("created", 0)) < self.ttl_seconds:
                    return [Source.from_dict(item) for item in payload.get("sources", [])]
            except (OSError, ValueError, TypeError):
                pass  # corrupt cache entry: refetch
        sources = self.inner.search(query, top_k=top_k)
        payload = {"created": now, "sources": [s.to_dict() for s in sources]}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return sources


def _loopback(host: str) -> bool:
    return host in {"localhost", "127.0.0.1", "::1"} or host.startswith("127.")


class HttpSearchRetriever:
    """SearXNG-compatible JSON search, or Brave's web-search API."""

    def __init__(self, url: str, provider: str = "searx", api_key: str = "", opener=None, timeout: float = 20.0):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in {"https", "http"}:
            raise RetrievalError(f"refusing search URL scheme {parts.scheme!r}")
        if parts.scheme == "http" and not _loopback(parts.hostname or ""):
            raise RetrievalError("plain http search is only allowed for loopback hosts")
        self.url = url
        self.provider = provider
        self.api_key = api_key
        self.timeout = timeout
        self._opener = opener

    def _build_url(self, query: str, top_k: int) -> str:
        params = {"q": query}
        if self.provider == "brave":
            params["count"] = str(max(1, min(top_k, 20)))
        else:
            params["format"] = "json"
        sep = "&" if urllib.parse.urlsplit(self.url).query else "?"
        return f"{self.url}{sep}{urllib.parse.urlencode(params)}"

    def search(self, query: str, top_k: int = 5) -> list[Source]:
        req = urllib.request.Request(self._build_url(query, top_k), method="GET")
        if self.api_key:
            header = "X-Subscription-Token" if self.provider == "brave" else "Authorization"
            req.add_header(header, self.api_key if self.provider == "brave" else f"Bearer {self.api_key}")
        opener = self._opener or urllib.request.build_opener()
        try:
            with opener.open(req, timeout=self.timeout) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as exc:
            raise RetrievalError(f"search HTTP {exc.code} from {self.url}") from None
        except urllib.error.URLError as exc:
            raise RetrievalError(f"search unreachable: {exc.reason}") from None
        except ValueError as exc:
            raise RetrievalError(f"search returned non-JSON: {exc}") from None

        if isinstance(data.get("web"), dict):
            raw = data["web"].get("results") or []
        else:
            raw = data.get("results") or []
        sources = []
        for item in raw[:top_k]:
            url = item.get("url") or ""
            if not url:
                continue
            sources.append(
                Source(
                    title=str(item.get("title") or url),
                    url=url,
                    snippet=str(item.get("content") or item.get("description") or ""),
                )
            )
        if not sources:
            raise RetrievalError(f"search returned no usable results for: {query}")
        return sources


class DuckDuckGoRetriever:
    """Keyless HTML search (duckduckgo.com/html). Real results, no API key.

    Last-resort adapter: the HTML endpoint is rate-limited and can change shape,
    so it is not the default. It fails closed like every other adapter.
    """

    def __init__(self, opener=None, timeout: float = 20.0, endpoint: str = "https://html.duckduckgo.com/html/"):
        self.endpoint = endpoint
        self.timeout = timeout
        self._opener = opener

    def search(self, query: str, top_k: int = 5) -> list[Source]:
        body = urllib.parse.urlencode({"q": query}).encode()
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "storm-panel/0.5"},
            method="POST",
        )
        opener = self._opener or urllib.request.build_opener()
        try:
            with opener.open(req, timeout=self.timeout) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise RetrievalError(f"search HTTP {exc.code} from duckduckgo") from None
        except urllib.error.URLError as exc:
            raise RetrievalError(f"search unreachable: {exc.reason}") from None

        results = []
        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S
        )
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S)
        for i, (href, title) in enumerate(pattern.findall(html)):
            url = self._unwrap(href)
            if not url:
                continue
            results.append(
                Source(
                    title=re.sub(r"<[^>]+>", "", title).strip() or url,
                    url=url,
                    snippet=re.sub(r"<[^>]+>", "", snippets[i]).strip() if i < len(snippets) else "",
                )
            )
            if len(results) >= top_k:
                break
        if not results:
            raise RetrievalError(f"search returned no usable results for: {query}")
        return results

    @staticmethod
    def _unwrap(href: str) -> str:
        href = href.strip()
        if href.startswith("//"):
            href = "https:" + href
        if "duckduckgo.com/l/" in href:
            query = urllib.parse.urlsplit(href).query
            target = urllib.parse.parse_qs(query).get("uddg")
            if target:
                return target[0]
            return ""
        return href if href.startswith("http") else ""


def make_retriever(
    provider: str | None = None,
    url: str | None = None,
    api_key: str | None = None,
    cache_dir=None,
    ttl_seconds: int = 86400,
) -> Retriever | None:
    """Build the configured retriever, or None when retrieval is off."""
    provider = (provider or os.environ.get("STORM_SEARCH_PROVIDER") or "none").lower()
    if provider in {"", "none", "off"}:
        return None
    if provider not in {"searx", "brave", "generic", "ddg"}:
        raise RetrievalError(f"unknown search provider {provider!r} (searx|brave|ddg)")
    api_key = api_key if api_key is not None else os.environ.get("STORM_SEARCH_API_KEY", "")
    if provider == "ddg":
        inner = DuckDuckGoRetriever()
    else:
        url = url or os.environ.get("STORM_SEARCH_URL")
        if not url:
            raise RetrievalError("retrieval is on but STORM_SEARCH_URL is not set")
        inner = HttpSearchRetriever(url, provider="brave" if provider == "brave" else "searx", api_key=api_key)
    if cache_dir in {None, ""}:
        cache_dir = os.environ.get("STORM_CACHE_DIR", ".storm-cache")
    if str(cache_dir).lower() in {"none", "off"}:
        return inner
    return CachedRetriever(inner, cache_dir=cache_dir, ttl_seconds=ttl_seconds)
