---
name: storm-fusion-research
description: Research hard questions with human-gated perspective panels.
version: 0.4.0
author: Brad Trnavsky
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, perspectives, panel, judge, reports, content]
    category: research
    related_skills: [grounded-citations, arxiv, llm-wiki]
---

# Storm Panel Skill

One question, several seats, one judge, one human. A DC issue seats the associate, the
supervisor, safety, and the customer. Same question, four truths. The judge synthesizes,
the human decides. Stanford STORM (Shao et al., NAACL 2024) asks how to write the article.
This asks how to make the call. No model names appear in this method: the human picks the
engine every run.

## When to Use

Use when a question deserves more than one angle: pillar content, ambitious claims,
cross-domain synthesis, operational calls, or anything where single-model bias is the risk.
Use when the user says "storm", "panel", "deep research", or "second opinions".

Do NOT use for quick lookups, single facts, or fast answers. Do NOT use when no human is
available for checkpoints: without the human this is just roleplay, run mode 1 only.

Prefer native skills when the job is narrower: `grounded-citations` for citation mechanics,
`arxiv` for papers, `llm-wiki` for the knowledge base, one-shot deep answers from a
research tool. This skill orchestrates; those skills execute.

## Prerequisites

Modes 1 and 2 need nothing beyond the standard toolset: `web_search`, `web_extract`,
`hindsight_recall`, `delegate_task`, `skill_view`.

Mode 3 needs one fanout engine, human's choice: OpenRouter Fusion (key required) or Hermes
MoA (a `moa` preset with reference models plus an aggregator). The human supplies the exact
model lineup per run. Never invent a default lineup.

One-time operator setup for per-call model picks (consent-gated, fail-closed without it):

```yaml
plugins:
  entries:
    storm-fusion-research:
      llm:
        allow_provider_override: true
        allow_model_override: true
```

Without these flags the tool runs on the active model only and says so in its error.

## How to Run

Pick the mode with the human, cast the seats, run the procedure below. In Hermes the skill
loads namespaced as `storm-fusion-research:storm-fusion-research` when installed as a plugin.

## Quick Reference

| Mode | Seats | Brains | Diversity | Keys |
|------|-------|--------|-----------|------|
| 1 Solo | 2-4 | One model, sequential roleplay | POV only | None |
| 2 Native panel | 2-12 via `delegate_task`, one seat each | One model family, human's pick | POV only | None |
| 3 Full panel | 2-12, each seat its own fanout | Many models per seat | POV times models | Engine key |

Past ~4 seats prefer mode 2 or 3. One brain playing twelve experts reintroduces the echo chamber.

## Procedure

### 1. Cast (human gate 1)

The orchestrator proposes seats and count from problem complexity: societal issue, up to a
dozen; broken deploy, two (design and engineering). Every cast includes one skeptic and one
practitioner. Present the cast as: seat name, what they care about, their sharpest 3-5
questions, why the seat matters. The human approves, amends, or adds seats nobody proposed.
GREENLIGHT shortcut: "greenlight" or "go" runs the cast as written.

### 2. Interview (per mode)

Mode 1: one model interviews each seat sequentially. Mode 2: one `delegate_task` subagent
per seat, parallel, each briefed with its seat card only. Mode 3: call `storm_run_panel`
with the topic, the seat cards, and the human-chosen lineup; each seat fans out across
the lineup and the tool returns seat reports plus the judge synthesis in one round trip.
Resolve a named MoA preset to its reference models plus aggregator first (read the preset
from config, pass provider/model pairs inline); lineups may differ per seat only by
separate tool calls per seat group.

Search stack per seat, in order: `hindsight_recall` first (prior thinking, zero cost), then
`web_search` and `web_extract` to ground answers, vault or RAG for cross-domain connections.
Synthesis-forcing queries ("what does research say about X"), not topic queries.

Per seat output: Q/A turns with sources, 3-5 key findings, source list. Hard rule: any
factual claim without a real source is marked `unverified`. Fabrication ends the run.

### 3. Human validation (human gate 2)

Present fused seat reports pre-curation: "the panel concluded X, does this track, what is
missing, what is wrong." Only validated findings proceed. Claims neither sourced nor
human-confirmed stay `unverified`.

### 4. Outline

Group findings by theme, dedupe, flag contradictions explicitly (never smooth them), map
every section to its sources. Living document, evolves as gaps close.

### 5. Write, then moderate (human gate 3)

Write section by section from the outline. Neutral tone. Thin sections say
`needs more research`, never padding. No new facts beyond Phase 2.

Moderator audits at the end: source-bias transfer, red-herring connections, missing seats,
unresolved contradictions. Findings go to the human for fixes or direction. Then final polish.

### Judge rules

The judge recommends, the human decides. Contradictions ship with weights (which seats,
what evidence), never averaged away. Ties and value calls route to the human with the
trade stated plainly.

## Pitfalls

- Skipping gates turns the panel into theater. No human, no modes 2 or 3.
- Fixed seat counts. Size the panel to the problem every run.
- Seats debating each other. Seats report; only the judge synthesizes.
- Reimplementing citations. Load `grounded-citations` for the ledger, `arxiv` for papers.
- Hardcoding models. Lineups age fast; the human casts engines and models per run.
- Mode 3 for small questions. Seats times models is the most expensive shape here.

## Verification

A complete run delivers: approved cast list, per-seat interview logs with sources, human
validation notes, outline with flagged contradictions, report with `unverified` marks where
earned, moderator findings with human signoff. Missing any artifact, the run is incomplete.

## Credits

Based on STORM by Shao et al., Stanford Oval Lab, NAACL 2024, and Co-STORM, EMNLP 2024.
Reference implementation: github.com/stanford-oval/storm. Method background (v0.3 era, model
tables superseded): `references/storm-method.md`. Design spec: repo root `PANEL-SPEC.md`. MIT.
