# Changelog

All notable changes to this project. Newest first.

## 0.6.1 (2026-11-04)

Tighter quote grounding in the verifier: dash spelling variants resolve to one word,
markdown-wrapped URLs resolve to their source, and `www.` spellings match bare hosts.
Seat search queries now compose topic-first inside a 120-character budget, and the
keyless adapter retries a quiet page before it reports back. 253 tests green.

## 0.6.0 (2026-11-04)

**Grounded runs: retrieval in the loop, with an AI citation verifier guarding it.**

`citations.py` is the advisor. When retrieval is on, each seat report and judge synthesis
is checked against retrieved sources before you see it: markers, URLs, and quotes,
word-aligned.

- `retrieval.py` searches a real backend per seat -- SearXNG-compatible JSON, Brave, or
  DuckDuckGo -- with top-k per seat and an on-disk cache, so the same query costs one
  search. Standard library only. Configuration is environment-only
  (`STORM_SEARCH_PROVIDER`, `STORM_SEARCH_URL`, `STORM_SEARCH_API_KEY`, `STORM_CACHE_DIR`).
- Citation markers are read the way models actually write them: varied spacing, page
  locators, labels and `and`/`or` connectives all parse as citations and are then
  range-checked.
- URL extraction covers the forms models emit, including schemeless hosts, IDN spellings
  and protocol-relative paths; punctuation and filenames are not mistaken for hosts.
- Quote grounding is word-aligned: a quote must appear in the text a retrieved source
  carries, on word boundaries, so a partial-word coincidence does not count as support.
- Verifier evaluation is a closed labeled ledger plus an independent held-out set labeled
  from a different domain. Result: precision and recall 1.0.
- Endpoint and key hardening in `run_panel.py` (Opus audit). Slot `base_url` overrides are
  opt-in (`--allow-slot-endpoints`, narrowable with `--allow-endpoint PREFIX` or
  `STORM_ALLOW_ENDPOINTS`). Keys stay bound to their endpoints, `https://` only
  (loopback `http://` needs `--allow-http-loopback`), and `--dry-run` prints
  the planned model/endpoint/key-var table before any live run. Caps
  (12 seats x 4 slots, 4 MoA refs) apply on every path, live runs included.
- Suite: 199 tests, green.

## 0.5.0 (2026-10-12)

**Model-agnostic and usable outside Hermes.**

- The method doc is rewritten without model names. It now explains how to choose a lineup:
  spread lineages, strongest judge, judge different from the seat models, a pre-run checklist.
- Nested fanout is documented. A mode 3 lineup slot can itself be a Fusion or MoA call. The
  cost math is seats x slots x inner models, plus a merge per slot and one judge call.
- Cost docs carry a cap (12 seats x 4 slots per run) and a dry-run gate: count calls first.
- MoA judge documented as opt-in for pillar calls only; the default stays one strongest
  reasoner. MoA wording unified: presets under the top-level `moa` key, used as
  `provider: moa` with the preset name as `model`.
- `references/storm-operational-improvements.md` is marked PARKED.
- `run_panel.py` is new: a standard-library script that runs mode 3 against any
  OpenAI-compatible endpoint. Flags include `--dry-run` (prints prompts and the call count),
  `--model`, and `--out`.
- `run_panel.py` supports a mini-MoA slot (`reference_models` plus an `aggregator`, one level).
- The Hermes plugin gives clearer error hints: consent, MoA preset, or unreachable model.
  It never swaps in a different model on failure.
- Setup docs add the optional `allowed_providers` / `allowed_models` limits and the
  `provider: moa` slot.
- New guides: `docs/use-without-hermes.md` (chat paste, script, own agent) and
  `docs/use-in-other-tools.md` (Claude Code, Codex, OpenCode, OpenWork, Pi).
- Removed the LinkedIn post. Removed hardcoded model names from the sample research notes and
  the operational-improvements doc. Fixed stale status text and made `hindsight_recall` and
  `llm-wiki` optional or removed.

## 0.4.0 (2026-09-23)

**Panel v2.**

- Vocabulary changed: POV is now seat, tier is now mode, fuser is now judge.
- Added the `storm_run_panel` tool and the Hermes plugin scaffold.
- Added diagrams and a social preview card, plus an attribution fix.

## 0.3 and earlier

- A fixed four-model panel with a separate fusing model. The sample research reports in
  `sample-research/` were produced with this version.
