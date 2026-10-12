# Changelog

All notable changes to this project. Newest first.

## 0.5.0 (2026-10-12)

**Model-agnostic and usable outside Hermes.**

- The method doc is rewritten without model names. It now explains how to choose a lineup:
  spread lineages, strongest judge, judge different from the seat models, a pre-run checklist.
- Nested fanout is documented. A mode 3 lineup slot can itself be a Fusion or MoA call. The
  cost math is seats x slots x inner models, plus a merge per slot and one judge call.
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
