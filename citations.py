"""Source formatting and citation verification.

The prompt asks each seat to cite retrieved sources as ``[S1]``. This module makes
that instruction checkable: every marker must point at a retrieved source, every
bare URL must be one of the retrieved URLs, and (when retrieval is on) the report
must carry at least one citation. Anything else fails the run.
"""

from __future__ import annotations

import re

BRACKET_RE = re.compile(r"\[([^\]]{1,80})\]")
URL_RE = re.compile(r"https?://[^\s<>\)\]\"'`]+", re.IGNORECASE)
# A host the model wrote without a scheme ("reports.example.test/x"). Models drop
# "https://" often enough that an unextracted host is a free pass for fabrication.
HOST_RE = re.compile(
    r"(?<![\w.@/:\-])"
    r"((?:[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?\.)+[a-z]{2,24})"
    r"(:\d{1,5})?"
    r"(/[^\s<>\)\]\"'`]*)?",
    re.IGNORECASE,
)
# "report.pdf" and "data.csv" are filenames, not cited hosts: a one-dot token whose
# last label is a document extension is prose, not a URL.
FILE_EXT = frozenset(
    "txt pdf md markdown rst csv tsv json yaml yml xml html htm png jpg jpeg gif"
    " svg webp zip tar gz py js ts sh docx xlsx pptx doc xls ppt".split()
)  # fmt: skip
# No practical length cap: a fabricated quote must not escape the gate by being long.
# 4000 chars only guards against a runaway match on pathological output. Wrapped
# quotes (newline inside the span) are normal in model output, so newlines are allowed.
QUOTE_RE = re.compile(
    r'"([^"]{4,4000})"'
    r"|“([^”]{4,4000})”"
    # Single quotes only when the delimiters stand alone: without the word-boundary
    # guard, possessives ("the plant's best") pair up and fabricate a quote.
    r"|(?<![\w'])'(?![\s'])([^'\n]{4,2000})'(?![\w'])"
    # Curly single quotes are never apostrophes, so they need no boundary guard.
    r"|‘([^’]{4,2000})’"
)
BREAK_RE = re.compile(r"[.!?;]\s+|\n+")


class CitationError(RuntimeError):
    """A report cited something the retriever never returned."""

    code = "citation_mismatch"

    def __init__(self, message: str):
        super().__init__(message)


def normalize_url(url: str) -> str:
    """Lowercase scheme and host, drop the fragment, ignore a trailing path slash.

    ``/throughput`` and ``/throughput/`` are the same page, and retrievers return
    both spellings; a trailing slash must not read as a fabricated citation.
    """
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url.strip())
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, parts.query, ""))


def format_sources(sources) -> str:
    """Numbered source block, stable order, one line per source plus snippet."""
    lines = ["Available sources (cite as [S1], [S2], ...):"]
    for i, source in enumerate(sources, start=1):
        lines.append(f"- [S{i}] {source.title} — {source.url}")
        if getattr(source, "snippet", ""):
            lines.append(f"    {source.snippet}")
    return "\n".join(lines)


RANGE_RE = re.compile(r"[Ss]?(\d{1,3})\s*[-\u2013\u2014]\s*[Ss]?(\d{1,3})")
MAX_RANGE = 50  # [S1-S2] is a citation; [S1-S9000] is a typo, not a scan target


def extract_citations(text: str) -> set[int]:
    """Collect numbers from markers like [S1], [S2, S3], [S4;S5], [S1-S2]."""
    refs: set[int] = set()
    for match in BRACKET_RE.finditer(text or ""):
        parts = [p for p in re.split(r"[,;\s]+", match.group(1).strip()) if p]
        if not parts or not any(p.upper().startswith("S") for p in parts):
            continue
        numbers = []
        for part in parts:
            span = RANGE_RE.fullmatch(part)
            if span:
                low, high = int(span.group(1)), int(span.group(2))
                if low > high or high - low > MAX_RANGE:
                    numbers = []
                    break
                numbers.extend(range(low, high + 1))
                continue
            if not re.fullmatch(r"[Ss]?\d+", part):
                numbers = []
                break
            numbers.append(int(part.lstrip("Ss")))
        refs.update(numbers)
    return refs


# A two-label token is only a host when its suffix is a real one ("ops.example.test"
# and "station.throughput" look alike otherwise, and the second is a metric name).
COMMON_TLDS = frozenset(
    "com org net edu gov mil int io co ai dev app info biz news xyz tech site online"
    " cloud page blog wiki shop art design plus us uk de ca au jp in br fr nl se no es"
    " it ch ru cn eu test example local".split()
)  # fmt: skip


def _host_like(host: str, path: str = "", port: str = "") -> bool:
    """True for a plausible web host, False for prose, filenames, versions, emails."""
    labels = host.rstrip(".").split(".")
    if len(labels) < 2:
        return False
    tld = labels[-1].lower()
    if not (2 <= len(tld) and tld.isalpha()) or tld in FILE_EXT:
        return False
    return bool(path or port) or len(labels) >= 3 or tld in COMMON_TLDS


def extract_urls(text: str) -> set[str]:
    """Bare URLs, with or without a scheme, trailing sentence punctuation stripped."""
    text = text or ""
    urls = {normalize_url(m.rstrip(".,;:!?'\"")) for m in URL_RE.findall(text)}
    for match in HOST_RE.finditer(text):
        host, port, path = match.group(1), match.group(2) or "", match.group(3) or ""
        if not _host_like(host, path, port):
            continue
        urls.add(normalize_url(f"https://{host}{port}{path.rstrip('.,;:!?')}"))
    return urls


def url_key(url: str) -> str:
    """Scheme-agnostic identity: a bare host and its http(s) spelling are one source."""
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    return f"{parts.netloc}{parts.path}" + (f"?{parts.query}" if parts.query else "")


def _normalize_quote(text: str) -> str:
    """Lowercase, collapse whitespace, strip wrapping punctuation."""
    cleaned = re.sub(r"\s+", " ", (text or "").replace("\u2019", "'")).strip()
    return cleaned.strip("\"'“”‘’[]").lower()


def _quote_fragments(quote: str) -> list[str]:
    """Split an ellipsis quote into the fragments that each have to be grounded."""
    return [f.strip() for f in re.split(r"\.\.\.|\u2026", quote) if len(f.strip()) >= 4]


def _fragment_in(fragment: str, source) -> bool:
    haystack = _normalize_quote(f"{getattr(source, 'title', '')} {getattr(source, 'snippet', '')}")
    return bool(haystack) and fragment in haystack


def _quote_grounded(quote: str, sources) -> bool:
    """True when every ellipsis fragment appears in at least one of the cited sources.

    A seat that stitches two retrieved sources with "..." is citing both of them, so
    each fragment is checked against the cited set rather than one single source.
    """
    fragments = _quote_fragments(quote)
    if not fragments:
        return True
    return all(any(_fragment_in(f, source) for source in sources) for f in fragments)


# Punctuation that can sit between a quote and the marker that grounds it. Backticks
# and code fences are deliberately absent: a marker outside a fence does not ground a
# quote inside it.
_SENTENCE_TAIL = frozenset(" \t\r\n.,;:!?)]}\"'‘’”")


def _sentence(text: str, start: int, end: int) -> str:
    """The sentence holding text[start:end], including a marker that trails the quote.

    A report may write `"quote". [S1]` — the period ends the sentence but not the
    citation, so punctuation and markers are consumed before the span is cut.
    """
    left = 0
    for match in BREAK_RE.finditer(text, 0, start):
        left = match.end()
    right = end
    while right < len(text):
        if text[right] in _SENTENCE_TAIL:
            right += 1
            continue
        if text[right] == "[":
            marker = BRACKET_RE.match(text, right)
            if marker:
                right = marker.end()
                continue
        break
    return text[left:right]


def _quote_span(match: re.Match) -> str:
    """The quoted text from whichever quote style matched."""
    for group in match.groups():
        if group is not None:
            return group
    return ""


def extract_quotes(text: str) -> list[str]:
    """Quoted spans long enough to be a claim: straight, curly, or standalone single."""
    quotes = []
    for match in QUOTE_RE.finditer(text or ""):
        span = _quote_span(match)
        if _normalize_quote(span):
            quotes.append(span)
    return quotes


def _quote_problems(text: str, sources) -> list[str]:
    """A quoted claim must be checkable against the source its marker points at."""
    problems: list[str] = []
    if not sources:
        return problems  # ungrounded citations are already reported
    for match in QUOTE_RE.finditer(text or ""):
        span = _quote_span(match)
        quote = _normalize_quote(span)
        if not quote:
            continue
        cited = sorted(r for r in extract_citations(_sentence(text, match.start(), match.end())) if 1 <= r <= len(sources))
        label = f'"{quote}"'
        if not cited:
            problems.append(f"quote has no citation marker, cannot be checked against a source: {label}")
            continue
        if not _quote_grounded(quote, [sources[r - 1] for r in cited]):
            markers = ", ".join(f"[S{r}]" for r in cited)
            problems.append(f"quote not found in cited source {markers}: {label}")
    return problems


def verify_citations(text: str, sources, require_citation: bool = True) -> list[str]:
    """Return human-readable problems. An empty list means the report is clean."""
    problems: list[str] = []
    refs = extract_citations(text or "")
    urls = extract_urls(text or "")
    allowed = {normalize_url(s.url) for s in sources}
    allowed_keys = {url_key(u) for u in allowed}

    if refs or urls:
        if not sources:
            problems.append("cites sources but retrieval returned none")

    for ref in sorted(refs):
        if not 1 <= ref <= len(sources):
            problems.append(f"cites [S{ref}] but only {len(sources)} sources were retrieved")

    for url in sorted(urls):
        if url not in allowed and url_key(url) not in allowed_keys:
            problems.append(f"cites URL not in the retrieved set: {url}")

    problems.extend(_quote_problems(text or "", sources))

    if require_citation and not refs:
        problems.append("report has no citation markers [S#]")

    return problems


def require_clean(text: str, sources, seat: str = "", require_citation: bool = True) -> None:
    """Raise CitationError listing every mismatch, never partially accept."""
    problems = verify_citations(text, sources, require_citation=require_citation)
    if problems:
        who = f"{seat}: " if seat else ""
        raise CitationError(who + "; ".join(problems))
