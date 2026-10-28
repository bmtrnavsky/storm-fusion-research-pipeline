# Changelog

All notable changes to this project. Newest first.

## Unreleased (fix-key-allowlist)

**Endpoint/key hardening in `run_panel.py` (Opus audit findings).**

- Slot `base_url` overrides are disabled by default; unlock with
  `--allow-slot-endpoints`, optionally narrowed with repeatable
  `--allow-endpoint PREFIX` (or `STORM_ALLOW_ENDPOINTS`).
- Keys are bound to endpoints: a non-empty key is only sent to its bound
  endpoint (default pair plus explicit `--endpoint-key PREFIX=ENV` /
  `STORM_ENDPOINT_KEYS`). A slot pointing at a foreign endpoint without its
  own explicit `api_key_env` is refused, so the default key can never follow
  a slot's `base_url` elsewhere.
- Transport hygiene: `https://` only (plain `http://` to loopback hosts only
  with `--allow-http-loopback`); embedded credentials (userinfo) and
  non-http schemes (`file://` etc.) refused; `Authorization` sent as an
  unredirected header and redirects refused outright instead of followed.
- `--dry-run` now prints the planned model/endpoint/key-var table and
  validates endpoints/keys/caps before printing; caps (12 seats x 4 slots,
  4 MoA refs) are enforced on every path, live runs included.

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
  `provider: moa` slot, which is not yet confirmed on every Hermes version.
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
