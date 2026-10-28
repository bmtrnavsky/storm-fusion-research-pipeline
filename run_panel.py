#!/usr/bin/env python3
"""Run a storm panel without Hermes, against any OpenAI-compatible chat endpoint.

Same input shape as the ``storm_run_panel`` tool (topic, seats, lineup, judge) and the same
seat and judge prompts, imported from panel.py so the two never drift apart. Standard
library only.

There is no "active model" outside Hermes, so every model is named explicitly: either in
the input file (``lineup`` and ``judge``) or with ``--model`` for one model everywhere.
This script never picks a model for you.

Examples:
    python run_panel.py panel.json --base-url https://openrouter.ai/api/v1
    python run_panel.py panel.json --base-url http://localhost:11434/v1 --model <local-model>
    python run_panel.py panel.json --dry-run     # print the prompts, call nothing

A lineup slot can also be a mini mixture-of-agents (nested fanout). Instead of one model,
give it reference models and an aggregator, mirroring Hermes MoA naming:

    {"moa": {"reference_models": [{"model": "<a>"}, {"model": "<b>"}],
             "aggregator": {"model": "<merge-model>"}}}

The script asks every reference model the seat's question, then the aggregator merges
their answers into one seat view. One level only, like Hermes MoA. This is a local
stand-in: it does not call Hermes presets (run the Hermes plugin for those).

Endpoint and key come from --base-url / STORM_BASE_URL and the env var named by
--api-key-env (default STORM_API_KEY). The env var name must start with STORM_
(anything else is rejected) so a panel file can never name an unrelated secret
like OPENAI_API_KEY or AWS_SECRET_ACCESS_KEY and have its value sent to a
third-party endpoint.

A lineup slot can override either with its own "base_url" and "api_key_env"
(same STORM_ rule), which lets one panel span several providers -- but slot
endpoints are DISABLED by default and must be unlocked by the operator with
--allow-slot-endpoints (optionally narrowed with repeatable --allow-endpoint
prefixes). A non-empty key is only ever sent to an endpoint it is bound to:
the default pair (default endpoint <-> default key env) plus explicit
--endpoint-key PREFIX=ENV bindings. In particular a slot that points at a
different endpoint without its own explicit api_key_env is refused, so the
default key can never silently follow a slot's base_url somewhere unexpected.

> [!WARNING]
> A slot's `base_url` receives that slot's key as a Bearer token. Only run
> panel files you trust, and only point slots at endpoints you trust.

Transport hygiene: only https:// endpoints are accepted, except plain http://
to loopback hosts (localhost / 127.x / ::1) with --allow-http-loopback.
URLs with embedded credentials (userinfo) and non-http schemes (file:// and
friends) are refused. Authorization is sent as an unredirected header and the
client refuses redirects instead of replaying the request elsewhere, so a key
is never forwarded to a redirect target.

Runs are capped at 12 seats x 4 slots (4 reference models per MoA slot).
--dry-run prints every prompt plus the planned model/endpoint/key-var table
and calls nothing.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from panel import SEAT_SCHEMA, _judge_prompt, _seat_prompt

JSON_HINT = (
    "\n\nReturn ONLY one JSON object, with no prose and no code fences, matching this "
    "schema:\n" + json.dumps(SEAT_SCHEMA)
)

KEY_ENV_PREFIX = "STORM_"


def resolve_key_env(name):
    """Validate an api_key_env name and return the key value."""
    if not isinstance(name, str) or not name.startswith(KEY_ENV_PREFIX):
        raise ValueError(
            f"Refusing api_key_env {name!r}: the env var name must start with "
            f"{KEY_ENV_PREFIX!r} (e.g. STORM_API_KEY). Rename your key and retry."
        )
    return os.environ.get(name, "")


MAX_SEATS = 12
MAX_SLOTS = 4
MAX_REFS = 4


def is_loopback_host(host):
    """True for localhost / 127.x / ::1 (anything else counts as remote)."""
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_endpoint(url, *, allow_http_loopback=False):
    """Endpoint hygiene for panel-file-supplied URLs. Returns normalized URL.

    Only https:// is accepted, except plain http:// to a loopback host when
    the operator passed --allow-http-loopback. Embedded credentials
    (userinfo) and non-http schemes (file:// etc.) are always refused.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("No endpoint. Pass --base-url or set STORM_BASE_URL.")
    url = url.strip()
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ("https", "http"):
        raise ValueError(
            f"Refusing endpoint {url!r}: scheme {parts.scheme!r} is not allowed. "
            "Only https:// endpoints are accepted"
            + ("" if parts.scheme != "http" else " (http:// needs a loopback host plus --allow-http-loopback)")
            + "."
        )
    if parts.username or parts.password or "@" in parts.netloc:
        raise ValueError(
            f"Refusing endpoint {url!r}: credentials embedded in the URL "
            "(userinfo) are not allowed."
        )
    host = parts.hostname
    if not host:
        raise ValueError(f"Refusing endpoint {url!r}: no hostname.")
    if parts.scheme == "http" and not (allow_http_loopback and is_loopback_host(host)):
        raise ValueError(
            f"Refusing endpoint {url!r}: plain http is only allowed for loopback "
            "hosts (localhost / 127.x / ::1) with --allow-http-loopback; "
            "everything else must be https://."
        )
    return url.rstrip("/")


def parse_endpoint_key(spec):
    """Parse one --endpoint-key PREFIX=ENV binding (operator config, trusted)."""
    prefix, sep, env = spec.partition("=")
    prefix, env = prefix.strip().rstrip("/"), env.strip()
    if not sep or not prefix or not env:
        raise ValueError(
            f"Bad --endpoint-key {spec!r}: expected PREFIX=ENV, e.g. "
            "--endpoint-key https://openrouter.ai/=STORM_OR_KEY."
        )
    if not env.startswith(KEY_ENV_PREFIX):
        raise ValueError(
            f"Refusing --endpoint-key {spec!r}: the env var name must start with "
            f"{KEY_ENV_PREFIX!r}."
        )
    return prefix, env


def build_bindings(defaults, extra):
    """Key env name -> endpoint prefixes it may be sent to.

    Starts with the default pair (default endpoint <-> default key env);
    explicit --endpoint-key entries add more. A slot's own pairing is NOT
    implicit: it must be declared here to receive a non-empty key.
    """
    table = {}
    if defaults.get("base_url") and defaults.get("api_key_env"):
        table.setdefault(defaults["api_key_env"], []).append(defaults["base_url"])
    for prefix, env in extra:
        table.setdefault(env, []).append(prefix)
    return table


def check_key_binding(base_url, key_env, key_value, bindings):
    """A non-empty key is only sent to an endpoint it is bound to."""
    if not key_value:
        return  # no key, no Authorization header, nothing to leak
    for prefix in bindings.get(key_env, []):
        norm = prefix.rstrip("/")
        if base_url == norm or base_url.startswith(norm + "/"):
            return
    raise ValueError(
        f"Refusing to send key {key_env} to {base_url!r}: not bound. Declare it "
        f"with --endpoint-key {base_url}={key_env} (or fix the slot's api_key_env)."
    )


def check_slot(slot, defaults, bindings, args, *, require_endpoint=True):
    """Fail-fast gate for one slot (or judge, ref, aggregator) dict.

    Enforces endpoint hygiene, the --allow-slot-endpoints flag gate plus the
    --allow-endpoint allowlist, explicit key pairing for foreign endpoints,
    and the key<->endpoint binding. Returns (base_url, key_env).
    """
    raw = (slot.get("base_url") or defaults["base_url"] or "").strip()
    if not raw:
        if require_endpoint:
            raise ValueError("No endpoint. Pass --base-url or set STORM_BASE_URL.")
        base_url = ""
    else:
        base_url = validate_endpoint(raw, allow_http_loopback=args.allow_http_loopback)
    slot_base = (slot.get("base_url") or "").strip().rstrip("/")
    default_base = (defaults["base_url"] or "").strip().rstrip("/")
    if slot_base and slot_base != default_base:
        if not args.allow_slot_endpoints:
            raise ValueError(
                f"Slot base_url {slot_base!r} differs from the default endpoint: "
                "slot endpoints are disabled by default. Re-run with "
                "--allow-slot-endpoints (and only point slots at endpoints you "
                "trust; each slot's key is sent there as a Bearer token)."
            )
        if args.allow_endpoint and not any(
            slot_base == p or slot_base.startswith(p.rstrip("/") + "/")
            for p in args.allow_endpoint
        ):
            raise ValueError(
                f"Slot base_url {slot_base!r} is not in the --allow-endpoint "
                "allowlist. Add it explicitly or remove the override."
            )
        if not slot.get("api_key_env"):
            raise ValueError(
                f"Slot base_url {slot_base!r} has no explicit api_key_env: "
                f"refusing to send the default key ({defaults['api_key_env']}) "
                "to a different endpoint. Set an explicit \"api_key_env\" on "
                "this slot and bind it with --endpoint-key PREFIX=ENV."
            )
    key_env = slot.get("api_key_env") or defaults["api_key_env"]
    if key_env and not key_env.startswith(KEY_ENV_PREFIX):
        raise ValueError(
            f"Refusing api_key_env {key_env!r}: the env var name must start with "
            f"{KEY_ENV_PREFIX!r} (e.g. STORM_API_KEY). Rename your key and retry."
        )
    key_value = os.environ.get(key_env, "") if key_env else ""
    if base_url:
        check_key_binding(base_url, key_env, key_value, bindings)
    return base_url, key_env


def iter_slot_dicts(lineup, judge):
    """Every slot-like dict that can carry base_url/api_key_env/model."""
    for slot in lineup:
        yield slot
        moa = slot.get("moa") or {}
        for ref in moa.get("reference_models") or []:
            yield ref
        if moa.get("aggregator"):
            yield moa["aggregator"]
    yield judge


def check_caps(seats, lineup):
    """Enforce the 12 seats x 4 slots (+4 refs) cap before spending anything."""
    if len(seats) > MAX_SEATS:
        raise ValueError(
            f"Too many seats: {len(seats)} > cap of {MAX_SEATS}. Split the panel."
        )
    if len(lineup) > MAX_SLOTS:
        raise ValueError(
            f"Too many lineup slots: {len(lineup)} > cap of {MAX_SLOTS}."
        )
    for slot in lineup:
        moa = slot.get("moa") or {}
        if not slot.get("moa"):
            continue
        refs = moa.get("reference_models") or []
        if not refs or not moa.get("aggregator"):
            raise ValueError(
                "A moa slot needs reference_models and an aggregator, each with a model. "
                "This script never picks a model for you."
            )
        if len(refs) > MAX_REFS:
            raise ValueError(
                f"Too many MoA reference models: {len(refs)} > cap of {MAX_REFS}."
            )


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects instead of replaying the request (and its key) elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            newurl,
            code,
            f"Refusing redirect ({code}) to {newurl}: the endpoint redirected; "
            "update --base-url / the slot base_url instead of following.",
            headers,
            fp,
        )


def complete(messages, slot, defaults, temperature, max_tokens, timeout, args, bindings):
    """One chat completion. Returns (text, model, total_tokens_or_None)."""
    model = slot.get("model") or defaults["model"]
    base_url, key_env = check_slot(slot, defaults, bindings, args)
    if not model:
        raise ValueError(
            "No model given. Set a model on each lineup slot and on judge, or pass --model. "
            "This script never picks a model for you."
        )

    key = resolve_key_env(key_env) if key_env else ""
    body = {"model": model, "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    headers = {"Content-Type": "application/json"}
    if key:  # local servers often need no key, so the header is optional
        headers["Authorization"] = f"Bearer {key}"

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if key:  # local servers often need no key, so the header is optional
        # Unredirected: sent on the first request, never forwarded elsewhere.
        # Belt and braces with NoRedirect below, which refuses redirects outright.
        req.add_unredirected_header("Authorization", f"Bearer {key}")
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        # Our own NoRedirect refusal carries the explanation in the message
        # (there is no response body to read); surface it, don't bury it.
        detail = (exc.read().decode(errors="replace")[:300] if exc.fp else "") or exc.msg or ""
        raise RuntimeError(f"{model} at {base_url}: HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{model} at {base_url}: {exc.reason}") from None

    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"{model}: unexpected response shape") from None
    tokens = (data.get("usage") or {}).get("total_tokens")
    return text, model, tokens


MERGE_PROMPT = (
    "You are the aggregator for one seat on a perspective panel. Several advisor models "
    "answered the same question from the same seat. Merge their answers into one seat view.\n"
    "Keep every source an advisor cited. Where advisors disagree, say so and name who said "
    "what; never average a disagreement away. Keep anything an advisor marked unverified "
    "marked unverified. End with 3-5 key findings."
)


def run_slot(messages, slot, defaults, temperature, max_tokens, timeout, args, bindings):
    """Run one lineup slot. Returns (text, label, tokens).

    A plain slot is one model call. A slot with a "moa" block fans out again: every
    reference model answers, then the aggregator merges them (nested fanout).
    """
    moa = slot.get("moa")
    if not moa:
        return complete(messages, slot, defaults, temperature, max_tokens, timeout, args, bindings)

    refs = moa.get("reference_models") or []
    agg = moa.get("aggregator")
    if not refs or not agg:
        raise ValueError(
            "A moa slot needs reference_models and an aggregator, each with a model. "
            "This script never picks a model for you."
        )
    answers, labels, total = [], [], 0
    for ref in refs:
        text, model, tokens = complete(messages, ref, defaults, temperature, max_tokens, timeout, args, bindings)
        answers.append((model, text))
        labels.append(model)
        total += tokens or 0
    question = messages[0]["content"]
    advisors = "\n\n".join(f"--- advisor {m} ---\n{t}" for m, t in answers)
    merged, agg_model, tokens = complete(
        [{"role": "user", "content": f"{MERGE_PROMPT}\n\nQuestion:\n{question}\n\n{advisors}"}],
        agg, defaults, temperature, max_tokens, timeout, args, bindings,
    )
    total += tokens or 0
    return merged, f"moa({'+'.join(labels)} -> {agg_model})", total or None


def parse_json(text):
    """Parse the judge's JSON, tolerating a code fence. Falls back to raw text."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw": text}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("input", help="JSON file: topic, seats, optional lineup and judge")
    ap.add_argument("--base-url", default=os.environ.get("STORM_BASE_URL"))
    ap.add_argument("--api-key-env", default="STORM_API_KEY")
    ap.add_argument("--model", help="one model for every seat and the judge")
    ap.add_argument("--temperature", type=float)
    ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--out", help="write the JSON result here instead of stdout")
    ap.add_argument("--dry-run", action="store_true", help="print prompts, call nothing")
    ap.add_argument(
        "--allow-slot-endpoints",
        action="store_true",
        default=os.environ.get("STORM_ALLOW_SLOT_ENDPOINTS") == "1",
        help="allow lineup slots to override base_url (off by default; each "
        "slot's key is sent to its endpoint as a Bearer token)",
    )
    ap.add_argument(
        "--allow-endpoint",
        action="append",
        default=None,
        metavar="PREFIX",
        help="allowlist prefix for slot base_url overrides; repeatable "
        "(also STORM_ALLOW_ENDPOINTS, comma-separated)",
    )
    ap.add_argument(
        "--endpoint-key",
        action="append",
        default=None,
        metavar="PREFIX=ENV",
        help="bind a STORM_* key env to an endpoint prefix so it may be sent "
        "there; repeatable (also STORM_ENDPOINT_KEYS, comma-separated)",
    )
    ap.add_argument(
        "--allow-http-loopback",
        action="store_true",
        default=os.environ.get("STORM_ALLOW_HTTP_LOOPBACK") == "1",
        help="allow plain http:// only for loopback hosts "
        "(localhost / 127.x / ::1); everything else must be https://",
    )
    args = ap.parse_args(argv)

    with open(args.input, encoding="utf-8") as fh:
        spec = json.load(fh)
    try:
        topic, seats = spec["topic"], spec["seats"]
    except KeyError as exc:
        sys.exit(f"Input is missing {exc}. Expected topic and seats.")

    defaults = {
        "model": args.model,
        "base_url": args.base_url,
        "api_key_env": args.api_key_env,
    }
    lineup = spec.get("lineup") or [{}]
    judge = spec.get("judge") or {}

    # Operator config (trusted): allowlist + key bindings, CLI or env.
    allow_endpoints = list(args.allow_endpoint or [])
    for chunk in os.environ.get("STORM_ALLOW_ENDPOINTS", "").split(","):
        if chunk.strip():
            allow_endpoints.append(chunk.strip())
    args.allow_endpoint = [p.rstrip("/") for p in allow_endpoints]
    if defaults["base_url"]:
        try:
            defaults["base_url"] = validate_endpoint(
                defaults["base_url"], allow_http_loopback=args.allow_http_loopback
            )
        except ValueError as exc:
            sys.exit(f"error: {exc}")
    try:
        extra_keys = [parse_endpoint_key(s) for s in (args.endpoint_key or [])]
        for chunk in os.environ.get("STORM_ENDPOINT_KEYS", "").split(","):
            if chunk.strip():
                extra_keys.append(parse_endpoint_key(chunk.strip()))
        check_caps(seats, lineup)
        bindings = build_bindings(defaults, extra_keys)
        for slot in iter_slot_dicts(lineup, judge):
            check_slot(
                slot, defaults, bindings, args,
                require_endpoint=not args.dry_run,
            )
    except ValueError as exc:
        if args.dry_run:
            sys.exit(f"error: {exc}")
        print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        return 1

    if args.dry_run:
        for seat in seats:
            print(f"=== seat: {seat['name']} ===")
            print(_seat_prompt(topic, seat)[0]["content"], end="\n\n")
        print("=== judge (reports are filled in at run time) ===")
        print(_judge_prompt(topic, []) + JSON_HINT)
        print("=== planned calls (models, endpoints, key vars -- keys are never printed) ===")
        calls = []
        for seat in seats:
            for slot in lineup:
                moa = slot.get("moa") or {}
                if not moa:
                    calls.append((
                        seat["name"],
                        slot.get("model") or defaults["model"],
                        (slot.get("base_url") or defaults["base_url"] or "").strip().rstrip("/") or "(unset)",
                        slot.get("api_key_env") or defaults["api_key_env"],
                    ))
                else:
                    for ref in moa.get("reference_models") or []:
                        calls.append((
                            seat["name"] + " [ref]",
                            ref.get("model") or defaults["model"],
                            (ref.get("base_url") or defaults["base_url"] or "").strip().rstrip("/") or "(unset)",
                            ref.get("api_key_env") or defaults["api_key_env"],
                        ))
                    agg = moa.get("aggregator") or {}
                    calls.append((
                        seat["name"] + " [merge]",
                        agg.get("model") or defaults["model"],
                        (agg.get("base_url") or defaults["base_url"] or "").strip().rstrip("/") or "(unset)",
                        agg.get("api_key_env") or defaults["api_key_env"],
                    ))
        calls.append((
            "judge",
            judge.get("model") or defaults["model"],
            (judge.get("base_url") or defaults["base_url"] or "").strip().rstrip("/") or "(unset)",
            judge.get("api_key_env") or defaults["api_key_env"],
        ))
        for name, model, endpoint, key_env in calls:
            print(f"- {name}: model={model or '(none)'} endpoint={endpoint} key_env={key_env or '(none)'}")
        print(f"\nCalls this run: {len(seats)} seats x lineup = {len(calls) - 1} "
              f"seat-side calls, plus 1 judge call.")
        return 0

    reports, usage = [], []
    try:
        for seat in seats:
            for slot in lineup:
                text, model, tokens = run_slot(
                    _seat_prompt(topic, seat), slot, defaults,
                    args.temperature, args.max_tokens, args.timeout,
                    args, bindings,
                )
                reports.append({"seat": seat["name"], "model": model, "findings": text})
                usage.append({"seat": seat["name"], "model": model, "tokens": tokens})
        text, _, _ = complete(
            [{"role": "user", "content": _judge_prompt(topic, reports) + JSON_HINT}],
            judge, defaults, args.temperature, args.max_tokens, args.timeout,
            args, bindings,
        )
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        return 1

    result = {
        "success": True,
        "panel": parse_json(text),
        "seat_reports": reports,  # raw reports, so you can validate before trusting the verdict
        "usage": usage,
    }
    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(output + "\n")
        print(f"Wrote {args.out}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
