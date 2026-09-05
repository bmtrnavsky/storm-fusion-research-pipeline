---
name: storm-fusion-research
description: Run STORM-style multi-perspective research using OpenRouter Fusion for genuine multi-model diversity per perspective. Use when the user asks for deep research, multi-perspective analysis, source-backed reports, definitive guides, or complex topic research where single-model bias is a risk.
license: MIT
metadata:
  author: Brad Trnavsky
  version: "0.3.0"
  category: research
  compatible_with:
    - Hermes
    - OpenClaw
    - Agent Skills-compatible agents
---

# STORM Research Method

**Version:** 0.3.0
**Author:** Brad Trnavsky
**License:** MIT
**Description:** STORM research method (Stanford, NAACL 2024) adapted for content creation. Five-phase pipeline: perspective discovery, expert interview (simulated + human), curation/outline, grounded writing, moderator audit. Includes STORM-Light (single-model) and STORM-Full (multi-model) modes.

# STORM Research Method

**Synthesis of Topic Outlines through Retrieval and Multi-perspective Question Asking**

Based on Stanford's STORM (Shao et al., NAACL 2024) and Co-STORM (EMNLP 2024).
Reference: github.com/stanford-oval/storm
This adaptation: github.com/bmtrnavsky/storm-fusion-research-pipeline

## When to Use

**Use this skill when:**
- Creating cornerstone content, major research pieces, or definitive guides
- A task requires deep multi-perspective research beyond a single web search
- The user explicitly asks for "STORM research" or "deep research"
- A content pipeline card requires the research phase

**Do NOT use for:**
- Simple fact-checking or quick lookups
- Time-sensitive or news-driven content (use STORM-Light)
- Tasks where the user just wants a fast answer

## Two Modes

### STORM-Full (Multi-Model Research)
For pillar-level content, ambitious claims, cross-domain synthesis, or whenever genuine perspective diversity matters more than speed. Phase 2 runs the approved perspectives in parallel (typically 6-8), each processed by the Fusion panel. Requires human expert availability for Phase 2 and Phase 5 checkpoints. Higher token cost in Phase 2.

### STORM-Light (Single-Model Research)
For routine blog posts, time-sensitive pieces, or topics within well-established domain knowledge. One model role-plays all perspectives sequentially. Faster, cheaper, sufficient for most content.

**Decision criteria:**
- Pillar-level piece? -> Full
- Crosses genuinely distinct domains the expert has NOT connected before? -> Full
- Time-sensitive or news-driven? -> Light
- Human expert available for checkpoints? -> Full. If not -> Light.
- Is the claim ambitious enough that single-model echo chamber is a real risk? -> Light for established territory. Full for unexplored ground.

## The Five-Phase Pipeline

### Phase 1: Perspective Discovery

**Role:** Senior Research Strategist

**Task:** Given a topic, map 6-8 distinct expert perspectives.

**Output format (for each perspective):**
```
Perspective [N]: [Persona Name]
- What they care about: [2-3 sentences]
- Sharpest questions: [3-5 specific questions]
- Why this perspective matters: [1 sentence]
```

**Process:**
1. Survey related articles and existing knowledge to discover diverse viewpoints
2. Ensure perspectives are genuinely distinct (not just rephrasings of the same angle)
3. Include at least one skeptical/contrarian perspective
4. Include at least one practitioner/operational perspective

**Human checkpoint:** Present the perspective list to the human expert for approval. They can reject, add, or modify. Do not proceed until approved.

**GREENLIGHT shortcut:** If the human says "greenlight" or "go", proceed immediately with the perspectives as written.

### Phase 2: Expert Interview (Two Stages)

#### Stage A: Simulated Interviews (Original STORM Method)

**Role:** Dual roles -- interviewer and expert practitioner

**Task:** Run a multi-turn dialogue for each perspective (6-8 total).

**Search stack (three layers for each interview):**

| Layer | Tool | When to Use |
|-------|------|-------------|
| Web Search | Any web search tool | Every interview -- ground answers in real sources |
| RAG / Knowledge Store | Vector + full-text search | Surface cross-domain connections from prior knowledge |
| Session / Memory Search | Prior conversation search | Run BEFORE fresh research to avoid redundancy |

**STORM-Light process:** Nemotron 3 Ultra simulates all perspectives sequentially. Ground each persona in real web search. Capture sources per claim.

**STORM-Full process:** Dispatch 8 independent research runs in parallel. Each run owns ONE perspective. Query the OpenRouter Fusion endpoint for each perspective. The Fusion API will automatically fan the prompt out to the 4-model panel and return the DeepSeek synthesized report. Do not attempt to manually route to individual models in Phase 2.

**Process for each perspective:**
1. Search prior knowledge first: "what has the human already written/thought about [concept]"
2. Run web search for the specific questions from this perspective
3. Run knowledge store search to surface cross-domain connections
4. Conduct a multi-turn interview (3-5 turns per perspective):
   - Interviewer asks a sharp question from the perspective
   - Expert answers using real sources found via search
   - Interviewer follows up based on the answer
   - Repeat

**Hard rule:** If a factual claim cannot be backed by a real source, the expert must output `unverified`. Fabrication is strictly forbidden.

**Output format per interview:**
```
Interview: [Persona Name]
Q1: [question]
A1: [answer with source citation]
Q2: [follow-up based on A1]
A2: [answer with source citation]
...
Key findings: [3-5 bullet points]
Sources: [list of URLs/references]
```

#### Stage B: Human Expert Interview (Key Adaptation)

**Role:** Interviewer (AI) + Expert (Human)

**Task:** After all simulated interviews are complete, present synthesized findings to the human expert for stress-testing.

**Process:**
1. Synthesize findings across all simulated interviews into a structured brief
2. Present to the human expert: "Research says X. From your experience in [domain], does this track? What is missing? What is wrong?"
3. Human responds. AI follows up, sharpens, challenges.
4. Human can add entirely new angles the simulated interviews missed.
5. Repeat for each perspective where the human has relevant domain experience.

**Hard rule:** If the human cannot confirm a claim from experience AND it cannot be backed by a real source, mark it `unverified`.

**Why this matters:** No published STORM implementation replaces the simulated expert with a real human practitioner. The human catches framing errors, adds nuance from lived experience, and stress-tests conclusions against reality.

### Phase 2.5: Human Validation Checkpoint

**Role:** Interviewer (AI) + Expert (Human)

**Task:** Post-synthesis, pre-curation reality check. The AI presents the fused POV reports to the human practitioner for validation before curation begins.

**Process:**
1. Present each fused POV report: "The Fusion panel concluded X. From your experience, does this track? What's missing? What's wrong?"
2. Human validates, corrects, or adds angles the panel missed.
3. Claims that cannot be backed by sources OR human experience are flagged `unverified`.
4. Only validated findings proceed to Phase 3.

**Hard rule:** If the human cannot confirm a claim from experience AND it cannot be backed by a real source, mark it `unverified`.

**Novelty claim:** Co-STORM (EMNLP 2024) places the human *during* the interview/discourse phase. This pipeline places the human *after synthesis and before curation*. Different stage, different job. No published STORM variant we are aware of includes a post-synthesis, pre-curation human validation checkpoint.

### Phase 3: Curate and Outline

**Role:** Meticulous Editor

**Task:** Organize all interview logs into a clean, hierarchical outline.

**Process:**
1. Group findings by theme across all interviews
2. Remove duplicate information
3. Flag contradictions between sources explicitly
4. Map every section to specific sources collected during interviews
5. Build a living outline -- it should evolve as new information surfaces

**Output format:**
```
# [Topic] -- Research Outline

## Section 1: [Theme]
- Key finding 1 (Source: [interview/source])
- Key finding 2 (Source: [interview/source])
- Contradiction noted: [description]

## Section 2: [Theme]
...

## Open Questions
- [questions that emerged but were not resolved]

## Sources
- [complete list of all sources collected]
```

### Phase 4: Grounded Writing

**Role:** Technical Writer

**Task:** Write the report section by section following the outline exactly.

**Constraints:**
- Neutral, factual tone
- Every claim points back to a collected source
- If a section is thin on data, write `needs more research` instead of padding with generic fluff
- Do not introduce new information not collected during Phase 2

### Phase 5: Moderator Pass

**Role:** Independent Moderator / Auditor

**Task:** Blind spot sweep for unknown unknowns.

**Why this is the highest-leverage role:** The Co-STORM evaluation found that removing the moderator hurts performance more than reducing the number of experts. Single expert + moderator beats multiple experts without a moderator.

**Audit checklist:**
1. **Source bias transfer** -- Is the report leaning too heavily on a single biased source? Flag and rebalance.
2. **Over-association of unrelated facts** -- Are there red herrings where facts are connected but should not be? Flag and remove or reframe.
3. **Missing perspectives** -- What questions did no one think to ask?
4. **Contradictions unresolved** -- Are there flagged contradictions that were not addressed?

**Human checkpoint:** Present moderator findings to the human expert. They approve fixes or add direction.

## Pipeline Integration

### Inside a Content Pipeline
- This skill replaces/enhances the research phases of a content pipeline
- Output feeds into the writing and publishing phases
- Follow your pipeline skill for artifact naming and gate procedures

### Standalone (Outside Pipeline)
- Run all 5 phases in sequence
- Output a complete research document
- Deliver the final document directly to the user

## Known Failure Modes

1. **Source bias transfer** -- leaning too heavily on a single biased source
2. **Over-association of unrelated facts** -- connecting things that should not be connected

Both are explicitly flagged in the Co-STORM paper and must be named checks in Phase 5.

## Model Assignment

| Pipeline Stage | Light Mode | Full Mode | Rationale |
|----------------|-----------|-----------|-----------|
| Phase 1: Perspective Discovery | Nemotron 3 Ultra | Nemotron 3 Ultra | Strongest orchestrator, purpose-built for agentic workflows |
| Phase 2: Simulated Interview | Nemotron 3 Ultra (single, sequential) | OpenRouter Fusion panel | Light: speed. Full: 4-model diversity per POV |
| Phase 2.5: Human Validation | Brad (no model) | Brad (no model) | Post-synthesis, pre-curation practitioner checkpoint |
| Phase 3: Curate and Outline | Nemotron 3 Ultra | Nemotron 3 Ultra | Main chain, structured output, reliability |
| Phase 4: Grounded Writing | Nemotron 3 Ultra | Nemotron 3 Ultra | Main chain, voice matching for hand-edit |
| Phase 5: Moderator/Auditor | Nemotron 3 Ultra | Nemotron 3 Ultra | Highest-leverage role, needs strongest reasoner |
| Final Polish | cos-heavy (DeepSeek V4 Flash) | cos-heavy (DeepSeek V4 Flash) | Fast, precise cleanup, temperature zero, won't go rogue on prose |

**Full mode panel config (Phase 2 Fusion only):**
```json
{
  "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
  "plugins": [{
    "id": "fusion",
    "analysis_models": [
      "nvidia/nemotron-3-ultra-550b-a55b:free",
      "openai/gpt-oss-120b:free",
      "google/gemma-4-31b-it:free",
      "minimax/minimax-m2.5:free"
    ],
    "model": "deepseek/deepseek-v4-flash"
  }]
}
```

**Fallback chain:** Nemotron Ultra → Nemotron Super 120B → DeepSeek V4 Flash

**Panel diversity rationale:** Four distinct training lineages, four different blind spots:
- Nemotron Ultra (NVIDIA) — US-origin, agentic RL, Mamba-Transformer hybrid
- GPT-OSS 120B (OpenAI) — RLHF-heavy, STEM/math strength, Western training
- Gemma 4 31B (Google DeepMind) — factual grounding, math, multimodal
- MiniMax M2.5 (MiniMax, Shanghai) — distinct Chinese lab lineage, different pretraining philosophy

**Thesis:** Frontier-quality research coverage through combining genuinely different small free-tier models — four distinct training lineages, four different blind spots, one judge to arbitrate. The diversity is the intelligence.

**Fallback:** If Nemotron 3 Ultra hits a reasoning ceiling on the moderator role, escalate per fallback chain. Do not escalate as a reflex.

## Search Stack Detail

### Web Search
- Use for: broad internet facts, current data, specific claim verification
- Query formulation: use synthesis-forcing queries ("what does research say about X") not just topic queries ("X")
- Run during every simulated interview to ground answers in real sources

### RAG / Knowledge Store
- Use for: surfacing prior knowledge, cross-domain connections from existing notes
- Query during interviews: "what has the human already written about [concept]"
- This is the differentiator -- makes output distinctly personal rather than generic AI content

### Session / Memory Search
- Use for: checking prior thinking on related topics
- Run BEFORE fresh research to avoid redundancy
- No API cost, often overlooked

## License

MIT

## Safety and Scope

This skill is limited to research, synthesis, source tracking, and report writing. It does not execute shell commands, modify files outside its own output, request credentials, or access private systems without explicit user authorization. Treat all source-backed claims as requiring verification, never fabricate citations, and do not skip human checkpoints when Full mode is selected.

## Credits

Based on STORM by Shao et al., Stanford Oval Lab, NAACL 2024.
Co-STORM collaborative extension, EMNLP 2024.
Reference implementation: github.com/stanford-oval/storm