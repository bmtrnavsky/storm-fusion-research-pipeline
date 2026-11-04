"""Source formatting and citation verification.

The prompt asks each seat to cite retrieved sources as ``[S1]``. This module makes
that instruction checkable: every marker must point at a retrieved source, every
bare URL must be one of the retrieved URLs, and (when retrieval is on) the report
must carry at least one citation. Anything else fails the run.
"""

from __future__ import annotations

import re

BRACKET_RE = re.compile(r"\[([^\]]{1,80})\]")
URL_RE = re.compile(r"https?://[^\s<>\)\]\"']+")
QUOTE_RE = re.compile(r'"([^"\n]{4,400})"|“([^”\n]{4,400})”')
BREAK_RE = re.compile(r"[.!?;]\s+|\n+")


class CitationError(RuntimeError):
    """A report cited something the retriever never returned."""

    code = "citation_mismatch"

    def __init__(self, message: str):
        super().__init__(message)


def normalize_url(url: str) -> str:
    """Lowercase scheme and host, drop the fragment, keep query and path."""
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url.strip())
    netloc = parts.netloc.lower()
    return urlunsplit((parts.scheme.lower(), netloc, parts.path, parts.query, ""))


def format_sources(sources) -> str:
    """Numbered source block, stable order, one line per source plus snippet."""
    lines = ["Available sources (cite as [S1], [S2], ...):"]
    for i, source in enumerate(sources, start=1):
        lines.append(f"- [S{i}] {source.title} — {source.url}")
        if getattr(source, "snippet", ""):
            lines.append(f"    {source.snippet}")
    return "\n".join(lines)


def extract_citations(text: str) -> set[int]:
    """Collect the numbers from markers like [S1], [S2, S3], [S4;S5]."""
    refs: set[int] = set()
    for match in BRACKET_RE.finditer(text or ""):
        parts = [p for p in re.split(r"[,;\s]+", match.group(1).strip()) if p]
        if not parts or not any(p.upper().startswith("S") for p in parts):
            continue
        numbers = []
        for part in parts:
            if not re.fullmatch(r"[Ss]?\d+", part):
                numbers = []
                break
            numbers.append(int(part.lstrip("Ss")))
        refs.update(numbers)
    return refs


def extract_urls(text: str) -> set[str]:
    """Bare URLs, with trailing sentence punctuation stripped."""
    return {
        normalize_url(m.rstrip(".,;:!?'\""))
        for m in URL_RE.findall(text or "")
    }


def _normalize_quote(text: str) -> str:
    """Lowercase, collapse whitespace, strip wrapping punctuation."""
    cleaned = re.sub(r"\s+", " ", (text or "").replace("\u2019", "'")).strip()
    return cleaned.strip("\"'“”‘’[]").lower()


def _quote_grounded(quote: str, source) -> bool:
    """True when the quoted text (or every ellipsis fragment) appears in the source."""
    haystack = _normalize_quote(f"{getattr(source, 'title', '')} {getattr(source, 'snippet', '')}")
    if not haystack:
        return False
    for fragment in re.split(r"\.\.\.|\u2026", quote):
        fragment = fragment.strip()
        if len(fragment) >= 4 and fragment not in haystack:
            return False
    return True


def _sentence(text: str, start: int, end: int) -> str:
    left = 0
    for match in BREAK_RE.finditer(text, 0, start):
        left = match.end()
    match = BREAK_RE.search(text, end)
    right = match.start() if match else len(text)
    return text[left:right]


def extract_quotes(text: str) -> list[str]:
    """Quoted spans (straight or curly double quotes) long enough to be a claim."""
    quotes = []
    for match in QUOTE_RE.finditer(text or ""):
        span = match.group(1) or match.group(2) or ""
        if _normalize_quote(span):
            quotes.append(span)
    return quotes


def _quote_problems(text: str, sources) -> list[str]:
    """A quoted claim must be checkable against the source its marker points at."""
    problems: list[str] = []
    if not sources:
        return problems  # ungrounded citations are already reported
    for match in QUOTE_RE.finditer(text or ""):
        span = match.group(1) or match.group(2) or ""
        quote = _normalize_quote(span)
        if not quote:
            continue
        cited = sorted(r for r in extract_citations(_sentence(text, match.start(), match.end())) if 1 <= r <= len(sources))
        label = f'"{quote}"'
        if not cited:
            problems.append(f"quote has no citation marker, cannot be checked against a source: {label}")
            continue
        if not any(_quote_grounded(quote, sources[r - 1]) for r in cited):
            markers = ", ".join(f"[S{r}]" for r in cited)
            problems.append(f"quote not found in cited source {markers}: {label}")
    return problems


def verify_citations(text: str, sources, require_citation: bool = True) -> list[str]:
    """Return human-readable problems. An empty list means the report is clean."""
    problems: list[str] = []
    refs = extract_citations(text or "")
    urls = extract_urls(text or "")
    allowed = {normalize_url(s.url) for s in sources}

    if refs or urls:
        if not sources:
            problems.append("cites sources but retrieval returned none")

    for ref in sorted(refs):
        if not 1 <= ref <= len(sources):
            problems.append(f"cites [S{ref}] but only {len(sources)} sources were retrieved")

    for url in sorted(urls):
        if url not in allowed:
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
