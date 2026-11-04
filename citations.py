"""Source formatting and citation verification.

The prompt asks each seat to cite retrieved sources as ``[S1]``. This module makes
that instruction checkable: every marker must point at a retrieved source, every
bare URL must be one of the retrieved URLs, and (when retrieval is on) the report
must carry at least one citation. Anything else fails the run.

Two rules keep the verifier honest in both directions:

* **Never fail open on a broken marker.** A marker that is misspelled or carries a
  locator (``[S99, p.4]``, ``[S 99]``, ``(S9)``) is still a citation attempt. It is
  parsed leniently, then range-checked; a token that cannot be read at all is
  reported. Silently discarding the whole marker would let a fabricated ``S99``
  read as "no citation" and pass.
* **Never cry wolf on honest prose.** Dotted type names (``System.Web.UI.Page``),
  filenames (``report.pdf``), versions (``3.1.2``) and bare numbers are not URLs.

Documented limit: quote grounding compares against the text a source object
carries — every string field present (``title``, ``snippet``, ``content``,
``text``, ``body``, ``description``). Retrieval stores a title and a snippet, so a
quote that only exists deep inside a page cannot be confirmed and is rejected.
The check is a lower bound on grounding, never an upper bound.
"""

from __future__ import annotations

import re

BRACKET_RE = re.compile(r"\[([^\]]{1,120})\]")
# A parenthesised marker, `(S9)`. The lookbehind keeps `](S2)` out of the scan, so a
# group already counted beside its bracket marker is not read twice. A word-glued
# group *is* scanned on purpose: `claim(S99)` is a citation attempt, and the old
# `\w` guard dropped it before any range check could see the fabricated S99.
PAREN_GROUP_RE = re.compile(r"(?<![\])])(\([^()\n]{1,60}\))")
URL_RE = re.compile(r"(?:https?|ftps?)://[^\s<>\"'`]+", re.IGNORECASE)
# A host the model wrote without a scheme ("reports.example.test/x"). Models drop
# "https://" often enough that an unextracted host is a free pass for fabrication.
# Labels are Unicode-aware so IDN hosts are seen at all; the suffix may be a
# punycode label ("xn--mnchen-3ya").
_LABEL = r"[^\W_](?:[^\W_-]*[^\W_])?"
_TLD = r"(?:xn--[a-z0-9]+(?:-[a-z0-9]+)*|[^\W\d_]{2,63})"
HOST_RE = re.compile(
    r"(?<![\w.@/:\-])"
    rf"((?:{_LABEL}\.)+{_TLD})"
    r"(:\d{1,5})?"
    r"(/[^\s<>\"'`]*)?",
    re.IGNORECASE,
)
# Protocol-relative "//host/path": HOST_RE's lookbehind rejects a host that follows
# a slash, so the double-slash form needs its own scan.
PROTO_REL_RE = re.compile(
    r"(?<![\w:/.])//"
    rf"((?:{_LABEL}\.)+{_TLD})"
    r"(:\d{1,5})?"
    r"(/[^\s<>\"'`]*)?",
    re.IGNORECASE,
)
# "report.pdf" and "data.csv" are filenames, not cited hosts: a one-dot token whose
# last label is a document extension is prose, not a URL (unless it has a path).
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


_TRAILING_PUNCT = ".,;:!?'\""


def _idna_netloc(netloc: str) -> str:
    """ASCII (punycode) spelling of a netloc, so IDN and xn-- forms compare equal."""
    from urllib.parse import urlsplit

    try:
        host = urlsplit(f"//{netloc}").hostname or ""
    except ValueError:
        return netloc
    if not host or all(ord(ch) < 128 for ch in host):
        return netloc
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return netloc
    # Netloc is lowercased by the caller; replace the host substring only.
    start = netloc.lower().find(host)
    if start < 0:
        return netloc
    return netloc[:start] + ascii_host + netloc[start + len(host) :]


def normalize_url(url: str) -> str:
    """Lowercase scheme and host, drop the fragment, ignore a trailing path slash.

    ``/throughput`` and ``/throughput/`` are the same page, and retrievers return
    both spellings; a trailing slash must not read as a fabricated citation.
    IDN hosts are folded to punycode so ``münchen.de`` and ``xn--mnchen-3ya.de``
    are one source.
    """
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url.strip())
    netloc = _idna_netloc(parts.netloc.lower())
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
# Words that join markers without being defects: (S1 and S2), (see S3).
_CONNECTIVES = frozenset({"and", "or", "also", "see", "cf", "e.g", "i.e"})
# Locator tokens that legitimately ride inside a marker: [S1, p. 4], [S2, ch. 3].
LOCATOR_RE = re.compile(
    r"(?i)(?:p{1,2}|pg|page|pages|ch|chap|chapter|sec|sect|section|\u00a7{1,2}"
    r"|\u00b6{1,2}|para|paragraph|fig|figure|tab|table|col|column|n|note|fn|vol"
    r"|l|line)\.?\s*\d{1,4}(?:\s*[-\u2013\u2014]\s*\d{1,4})?"
)


def _marker_like(content: str) -> bool:
    """True when bracket content is a citation attempt, not prose in brackets.

    The prompt mandates the ``S`` prefix, so a bare number in brackets (``[12]``, a
    footnote; ``[2024]``, a year) is not one — treating it as a source number would
    reject honest reports that use footnote or year brackets.
    """
    stripped = content.strip()
    if not stripped or len(stripped) > 100:
        return False
    if re.fullmatch(r"[Ss]{1,3}", stripped):
        return True
    return bool(re.search(r"[Ss]\s?\d", stripped))


def _parse_marker_content(content: str) -> tuple[set[int], list[str]]:
    """Leniently read one marker body into references plus unreadable tokens."""
    refs: set[int] = set()
    issues: list[str] = []
    stripped = LOCATOR_RE.sub(" ", content)
    stripped = re.sub(r"([Ss])\s+(\d)", r"\1\2", stripped)  # "S 99" -> "S99"
    stripped = re.sub(r"(\d)\s*([-\u2013\u2014])\s*([Ss]?\d)", r"\1\2\3", stripped)
    # "and"/"or"/"&" join markers: (S1 and S2). They are not odd tokens.
    stripped = re.sub(r"(?i)\b(?:and|or|also|see|cf)\b|&", " ", stripped)
    for token in re.split(r"[,;\s]+", stripped):
        token = token.strip(".,;:*_~`")
        if not token:
            continue
        span = RANGE_RE.fullmatch(token)
        if span:
            low, high = int(span.group(1)), int(span.group(2))
            if low > high or high - low > MAX_RANGE:
                issues.append(f"unrecognized citation marker token '{token}'")
                continue
            refs.update(range(low, high + 1))
            continue
        simple = re.fullmatch(r"[Ss]?(\d{1,3})", token)
        if simple:
            refs.add(int(simple.group(1)))
            continue
        issues.append(f"unrecognized citation marker token '{token}'")
    return refs, issues


# A label that rides inside a paren marker: "(Source: S9)", "(Sources: S1; S2)".
# The label names what the number is, so it is decoration, not prose.
_MARKER_LABEL_RE = re.compile(
    r"(?i)^\s*(?:sources?|citations?|cite[ds]?|references?|refs?)\s*:\s*"
)


def _prose_words(content: str) -> list[str]:
    """Plain words left in a paren body once locators and connectives are removed.

    ``"S99, page 4"`` is a citation whose locator is noise; ``"the S3 region"`` is
    prose that happens to name a source. The difference is these words.
    """
    stripped = LOCATOR_RE.sub(" ", content)
    words = []
    for token in re.split(r"[,;:\s]+", stripped):
        token = token.strip(".")
        if token and re.fullmatch(r"[A-Za-z]{2,}", token) and token.lower() not in _CONNECTIVES:
            words.append(token)
    return words


def _strip_decoration(content: str) -> str:
    """Drop a ``Source:``-style label so what is left is the marker body itself.

    ``(Source: S99)`` is a citation with a label attached, not prose: the label says
    what the number is, so the number still has to be range-checked.
    """
    return _MARKER_LABEL_RE.sub("", content)


def _scan_markers(text: str) -> tuple[set[int], list[str]]:
    """Every citation attempt in ``text``: parsed references and reported defects."""
    refs: set[int] = set()
    issues: list[str] = []
    for match in BRACKET_RE.finditer(text or ""):
        if not _marker_like(match.group(1)):
            continue
        found, bad = _parse_marker_content(match.group(1))
        refs |= found
        issues.extend(bad)
    for match in PAREN_GROUP_RE.finditer(text or ""):
        body = match.group(1)[1:-1]
        if not _marker_like(body):
            continue
        # Parentheses also hold ordinary prose ("(the S3 region)", "(new S7 line)"), so
        # a group counts as a citation only when its body parses as one. The decoration
        # a report hangs on a real marker — a locator ("(S99, page 4)") or a label
        # ("(Source: S99)") — is stripped *before* that test. Testing the raw body was
        # how a decorated group fell through as prose and a fabricated S99 passed.
        cleaned = _strip_decoration(body)
        if _prose_words(cleaned):
            continue
        found, bad = _parse_marker_content(cleaned)
        refs |= found
        issues.extend(bad)
    return refs, issues


def extract_citations(text: str) -> set[int]:
    """Collect numbers from markers like [S1], [S2, S3], [S4;S5], [S1-S2], (S3)."""
    return _scan_markers(text)[0]


# A two-label token is only a host when its suffix is a real one ("ops.example.test"
# and "station.throughput" look alike otherwise, and the second is a metric name).
COMMON_TLDS = frozenset(
    """
    ac ad ae af ag ai al am ao aq ar as at au aw ax az ba bb bd be bf bg bh bi bj
    bm bn bo br bs bt bw by bz ca cc cd cf cg ch ci ck cl cm cn co cr cu cv cw cx
    cy cz de dj dk dm do dz ec ee eg er es et eu fi fj fk fm fo fr ga gb gd ge gf
    gg gh gi gl gm gn gp gq gr gs gt gu gw gy hk hm hn hr ht hu id ie il im in io
    iq ir is it je jm jo jp ke kg kh ki km kn kp kr kw ky kz la lb lc li lk lr ls
    lt lu lv ly ma mc md me mg mh mk ml mm mn mo mp mq mr ms mt mu mv mw mx my mz
    na nc ne nf ng ni nl no np nr nu nz om pa pe pf pg ph pk pl pm pn pr ps pt pw
    py qa re ro rs ru rw sa sb sc sd se sg sh si sk sl sm sn so sr ss st su sv sx
    sy sz tc td tf tg th tj tk tl tm tn to tr tt tv tw tz ua ug uk us uy uz va vc
    ve vg vi vn vu wf ws ye yt za zm zw
    aero app art asia biz blog cat cloud club coop design dev email example fun
    gov gdn group guru host icu info int jobs link live local love media mil mobi
    museum name network news ngo onion online ong org page pics photo press pro
    review shop site social software space store studio tech tel test today top
    travel tv ventures video wiki win works world xyz zone
    """.split()
)  # fmt: skip


_PASCAL_LABEL = re.compile(r"[A-Z][a-z0-9]*")


def _host_like(host: str, path: str = "", port: str = "") -> bool:
    """True for a plausible web host, False for prose, filenames, versions, emails."""
    labels = host.rstrip(".").split(".")
    if len(labels) < 2 or any(not label for label in labels):
        return False
    # A namespaced type name ("System.Web.UI.Page", "java.lang.StringBuilder") is a
    # dotted identifier: several capitalised labels in a row. Hosts are lowercase.
    if len(labels) >= 3 and sum(1 for label in labels if _PASCAL_LABEL.fullmatch(label)) >= 2:
        return False
    tld = labels[-1].lower()
    if tld.startswith("xn--"):
        if not re.fullmatch(r"xn--[a-z0-9]+(?:-[a-z0-9]+)*", tld):
            return False
        known = True
    else:
        if not (2 <= len(tld) <= 63) or not tld.isalpha():
            return False
        known = tld in COMMON_TLDS
        # "report.pdf", "build.sh": a document/script extension with no path is a
        # filename, even when the same string is also a country TLD. `evil.sh/x`
        # keeps its host reading because the path is present.
        if tld in FILE_EXT and not (path or port):
            return False
        if not known and not (path or port):
            return False  # "station.throughput" is a metric, not a host
    if not known and not all(label == label.lower() for label in labels):
        return False
    return True


def _strip_url_tail(url: str) -> str:
    """Trim sentence punctuation, then only *unbalanced* closing parentheses.

    ``.../Throughput_(operations)`` keeps its last paren (the pair balances);
    ``(https://host/x)`` loses it (the outer paren belongs to the sentence).
    """
    url = url.strip().rstrip(_TRAILING_PUNCT)
    while url.endswith(")") and url.count("(") < url.count(")"):
        url = url[:-1].rstrip(_TRAILING_PUNCT)
    return url


def extract_urls(text: str) -> set[str]:
    """Bare URLs, with or without a scheme, trailing sentence punctuation stripped."""
    text = text or ""
    urls = {normalize_url(_strip_url_tail(u)) for u in URL_RE.findall(text)}
    for regex in (HOST_RE, PROTO_REL_RE):
        for match in regex.finditer(text):
            host, port, path = match.group(1), match.group(2) or "", match.group(3) or ""
            if not _host_like(host, path, port):
                continue
            scheme = "https:" if regex is HOST_RE else ""
            urls.add(normalize_url(_strip_url_tail(f"{scheme}//{host}{port}{path}")))
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


def _source_text(source) -> str:
    """Every string field the source carries, so full-content retrievers ground quotes.

    Retrieval returns a title and a snippet; a richer retriever may also return
    ``content``/``text``/``body``. Whatever is present is the checkable surface.
    """
    parts = []
    for name in ("title", "snippet", "content", "text", "body", "description"):
        value = getattr(source, name, "")
        if isinstance(value, str) and value.strip():
            parts.append(value)
    return _normalize_quote(" ".join(parts))


def _phrase_in(fragment: str, haystack: str) -> bool:
    """Whole-word containment: a quote may not ground on part of a word.

    ``"plant growth increased"`` is not a quote of ``"the transplant growth
    increased"`` — the substring test said it was, so a paraphrase that clipped a word
    counted as grounded. Boundary guards go on the edges that are word characters; a
    fragment ending in a period needs none, because punctuation is not a word.
    """
    pattern = re.escape(fragment)
    if fragment[:1].isalnum() or fragment[:1] == "_":
        pattern = rf"(?<!\w){pattern}"
    if fragment[-1:].isalnum() or fragment[-1:] == "_":
        pattern = rf"{pattern}(?!\w)"
    return re.search(pattern, haystack) is not None


def _fragment_in(fragment: str, source) -> bool:
    haystack = _source_text(source)
    if not haystack:
        return False
    if _phrase_in(fragment, haystack):
        return True
    # A quote often ends a sentence that the snippet continues: "…1,204 patients."
    # where the source reads "…1,204 patients across nine sites." The closing period
    # is punctuation, not a claim, so retry without trailing sentence punctuation.
    trimmed = fragment.rstrip(".,;:!? ")
    return len(trimmed) >= 4 and _phrase_in(trimmed, haystack)


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
        if text[right] == "(":
            group = PAREN_GROUP_RE.match(text, right)
            if group and _marker_like(group.group(1)[1:-1]):
                right = group.end()
                continue
        break
    return text[left:right]


def _previous_sentence(text: str, start: int) -> str:
    """The sentence immediately before ``start`` (empty when there is none)."""
    breaks = [match for match in BREAK_RE.finditer(text, 0, start)]
    if not breaks:
        return ""
    begin = breaks[-2].end() if len(breaks) > 1 else 0
    return text[begin : breaks[-1].start()]


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
    """A quoted claim must be checkable against the source its marker points at.

    Scope of a quote's marker: its own sentence, or the sentence immediately before
    it (a report may write `Numbers moved [S1]. The log says "..."`). Never wider.
    """
    problems: list[str] = []
    if not sources:
        return problems  # ungrounded citations are already reported
    for match in QUOTE_RE.finditer(text or ""):
        span = _quote_span(match)
        quote = _normalize_quote(span)
        if not quote:
            continue
        cited = sorted(
            r
            for r in extract_citations(_sentence(text, match.start(), match.end()))
            if 1 <= r <= len(sources)
        )
        if not cited:
            prior = _previous_sentence(text, match.start())
            if prior:
                cited = sorted(r for r in extract_citations(prior) if 1 <= r <= len(sources))
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
    refs, marker_issues = _scan_markers(text or "")
    urls = extract_urls(text or "")
    allowed = {normalize_url(s.url) for s in sources}
    allowed_keys = {url_key(u) for u in allowed}

    if refs or urls:
        if not sources:
            problems.append("cites sources but retrieval returned none")

    problems.extend(marker_issues)

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
