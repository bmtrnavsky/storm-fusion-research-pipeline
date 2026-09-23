# Storm Panel Spec v2: Human-in-the-Loop Perspective Panel

**Status:** spec, not built. **Parent:** Stanford STORM (Shao et al., NAACL 2024) and Co-STORM (EMNLP 2024).
**Repo:** `bmtrnavsky/storm-fusion-research-pipeline`. **Version target:** 0.4.0.

## Identity

Stanford asks how to write the article. This asks how to make the call.

One question, several seats, one judge, one human. A DC issue seats the associate, the
supervisor, safety, and the customer. Same question, four truths. The judge synthesizes,
the human decides. Nothing native in Hermes does this chain: native tools give one answer
from one angle, cited. This gives several angles from one or many brains, then a verdict.

## The two improvements on Stanford

1. **Human in the loop at four gates** (Stanford has none in STORM; Co-STORM interleaves
   the human mid-discourse instead of gating). The human casts, validates, decides.
2. **Per-seat multi-model fanout** (Stanford runs one model everywhere). Mode 3 gives every
   seat its own panel of models. Neither existed in usable form when v0.3.0 was written.

## Modes

| Mode | Seats | Brains | Diversity source | Cost | Keys |
|------|-------|--------|------------------|------|------|
| 1 Solo | 2-4, simple problems | One model role-plays every seat, sequential | POV only | Cheapest | None |
| 2 Native panel | 2-12, parallel `delegate_task` subagents, one seat each | One model family, any model the human likes | POV only | Moderate | None |
| 3 Full panel | 2-12, each seat its own MoA/Fusion fanout | Many models per seat | POV times models | Highest | Full-mode engine key |

Rule of thumb: one brain role-playing twelve experts reintroduces the echo chamber.
Past ~4 seats, use mode 2 or 3.

## Engines (mode 3, human picks the lineup)

- **OpenRouter Fusion.** Buys training-lineage diversity. Exists today.
- **Hermes MoA** (`moa` toolset, `/moa` command, presets with `reference_models` plus
  `aggregator`). Buys home field: own keys, own bill, no round trip. Exists today.
- Method is engine-agnostic. A future native MoE slots in without rewriting the method.

Per-seat fanout mapping: MoA reference models are the seat's brain trust (lineups may differ
per seat: shop-floor models for the associate, systems models for engineering). The MoA
aggregator synthesizes the seat view. The panel judge synthesizes across seats.

## Cast rule (dynamic sizing)

Fixed seat counts are Stanford thinking; Wikipedia articles always need the same shape.
Operational questions do not. The orchestrator proposes seats and count from problem
complexity: societal issue, a dozen seats; broken deploy, two (design and engineering).
The human approves or amends at the cast checkpoint, adding seats the orchestrator missed
("3 proposed plus 2 I thought of" is the checkpoint working, not failing). GREENLIGHT
shortcut ("greenlight", "go") proceeds as proposed.

## The five phases (unchanged skeleton, new casting)

1. **Perspective discovery.** Orchestrator maps seats, human approves/amends the cast.
2. **Interviews.** Per mode above. Search stack per seat: `hindsight_recall` first (prior
   thinking, no cost), then `web_search` / `web_extract` for grounding, vault/RAG for
   cross-domain connections. Hard rule: unsourced factual claims are marked `unverified`.
3. **Post-synthesis human validation.** Fused seat reports go to the human pre-curation:
   "the panel concluded X, does this track, what is missing, what is wrong." Only validated
   findings proceed. (No published STORM variant gates here.)
4. **Curate and outline.** Living outline; contradictions flagged explicitly, not smoothed.
5. **Grounded writing, then moderator audit.** Moderator runs at the end as auditor
   (Stanford's moderator prompts mid-discourse; different job): source-bias transfer check,
   red-herring check, missing-seat check, unresolved-contradiction check. Findings go to
   the human. Then final polish.

## Judge rules (the piece Stanford lacks)

- The judge **recommends, the human decides.** The judge never closes a contested call.
- Contradictions are reported with weights (which seats, what evidence), never averaged away.
- Anything neither sourced nor human-confirmed stays `unverified` in the final document.
- Ties and value judgments route to the human with the trade stated plainly.
- Thin sections say `needs more research`, never padding.

## Native cross-references (defer, do not reimplement)

- Citation mechanics and `unverified` ledger: `grounded-citations` skill.
- Conference papers and BibTeX: `arxiv` skill.
- Persistent knowledge base layer: `llm-wiki` skill.
- Multi-model fanout mechanics: MoA docs (`docs/user-guide/features/mixture-of-agents`).
- Parallel seats: `delegate_task`. Prior thinking: `hindsight_recall`.

## Cost guidance (mode picker)

- Pillar piece or ambitious claim where shared blind spots are the risk: mode 3.
- Cross-domain synthesis the expert has not connected before: mode 2 minimum.
- Time-sensitive, news-driven, established territory: mode 1.
- No human available for checkpoints: mode 1 only. Modes 2 and 3 require the human.

## Packaging (when spec is approved)

- Plugin scaffold: `plugin.yaml` (no `requires_env`; Full-engine keys stay skill-level
  prerequisites so Light/Native install clean), `__init__.py` with `ctx.register_skill`,
  skill at `skills/storm-fusion-research/SKILL.md`, method docs folded to references.
- SKILL.md to Hermes HARDLINE: short description, human-first author, native tool names
  in backticks, no hardcoded model picks, no personal names in checkpoints.
- Validate with `hermes plugins validate`, tag, release, catalog PR. Category: tools.

## Credits

Based on STORM by Shao et al., Stanford Oval Lab, NAACL 2024. Co-STORM, EMNLP 2024.
Reference implementation: `github.com/stanford-oval/storm` (31.5k stars). This adaptation:
`github.com/bmtrnavsky/storm-fusion-research-pipeline`. MIT.
