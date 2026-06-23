---
name: storm-research
version: 0.1.0
description: "STORM research method (Stanford, NAACL 2024) adapted for content creation. Five-phase pipeline: perspective discovery, expert interview (simulated + human), curation/outline, grounded writing, moderator audit. Use for cornerstone content, research pieces, or any task requiring deep multi-perspective research. Works inside the S2BI content pipeline or standalone for general research."
author: Brad Trnavsky
license: MIT
metadata:
  hermes:
    tags: [research, content-creation, storm, methodology, multi-perspective]
---

# STORM Research Method

**Synthesis of Topic Outlines through Retrieval and Multi-perspective Question Asking**

Based on Stanford's STORM (Shao et al., NAACL 2024) and Co-STORM (EMNLP 2024).
Reference: github.com/stanford-oval/storm

## When to Use

**Use this skill when:**
- Creating cornerstone content, major research pieces, or definitive guides
- A task requires deep multi-perspective research beyond a single web search
- The user explicitly asks for "STORM research" or "deep research"
- A content pipeline card requires the research phase

**Do NOT use for:**
- Simple fact-checking or quick lookups
- Time-sensitive or news-driven content (use lightweight variant)
- Tasks where the user just wants a fast answer

## Two Modes

### Full STORM (all 5 phases)
For cornerstone content, major research, definitive guides. Requires human expert availability for Phase 2 and Phase 5 checkpoints.

### Lightweight STORM (Phases 1, 3, 5 only)
For regular posts, time-sensitive pieces, or when no human expert is available. Skips the interview phase.

**Decision criteria:**
- Pillar-level piece? -> Full
- Crosses genuinely distinct domains the expert has NOT connected before? -> Full
- Time-sensitive or news-driven? -> Lightweight
- Human expert available for checkpoints? -> Full. If not -> Lightweight.

## Model Assignment

| Pipeline Stage | Model | Rationale |
|----------------|-------|-----------|
| Phase 1: Perspective Discovery | DeepSeek 4 Flash | Fast, strong at structured research output |
| Phase 2: Simulated Interview | DeepSeek 4 Flash | High-volume token burn; fast and capable |
| Phase 2: Human Expert Interview | Owl Alpha | Needs to synthesize across all interviews and present clearly |
| Phase 3: Curate and Outline | Owl Alpha | Structured output, reliability |
| Phase 4: Grounded Writing | Owl Alpha | Voice matching for human hand-edit pass |
| Phase 5: Moderator/Auditor | Owl Alpha | Highest-leverage role; needs real reasoning strength |
| Final Polish | DeepSeek 4 Flash | Mechanical task (dedup, summary); speed only |

**Fallback:** If Owl Alpha hits a reasoning ceiling on the moderator role, escalate to a stronger model like Sonnet 4.6. Do not escalate as a reflex.

**Model terminology:** Owl Alpha is free on Openrouter and presumed to be a frontier Alpha model. Substitute with the frontier model of your choice, Opus, Sonnet, Gemini Pro or Flash, Deepseek V4 Pro, etc...

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

**Search stack (use all three layers for each interview):**

| Layer | Tool | When to Use |
|-------|------|-------------|
| Web Search | `web_search` | Every interview -- ground answers in real sources |
| RAG | pgvector hybrid search | Surface cross-domain connections from prior knowledge |
| Session Memory | `session_search` | Run BEFORE fresh research to avoid redundancy |

**Process for each perspective:**
1. Run session_search first: "what has the human already written/thought about [concept]"
2. Run web_search for the specific questions from this perspective
3. Run RAG to surface vault connections
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

#### Stage B: Human Expert Interview (Brad Modification)

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

### Inside S2BI Content Pipeline
- This skill replaces/enhances Phases 1-3 of the content pipeline
- Output feeds into the existing Phase 4 (Execution & Publishing)
- Artifacts go to `30 Hermes Pipeline/Active/[card-id]/`
- Follow the content-pipeline skill for artifact naming and gate procedures

### Standalone (Outside Pipeline)
- Run all 5 phases in sequence
- Output a complete research document
- No Kanban or pipeline artifact naming required
- Deliver the final document directly to the user

## Known Failure Modes

1. **Source bias transfer** -- leaning too heavily on a single biased source
2. **Over-association of unrelated facts** -- connecting things that should not be connected

Both are explicitly flagged in the Co-STORM paper and must be named checks in Phase 5.

## Search Stack Detail

### web_search
- Use for: broad internet facts, current data, specific claim verification
- Query formulation: use synthesis-forcing queries ("what does research say about X") not just topic queries ("X")
- Run during every simulated interview to ground answers in real sources

### RAG (pgvector)
- Use for: surfacing vault knowledge, cross-domain connections from prior notes
- Query during interviews: "what has the human already written about [concept]"
- This is the differentiator -- makes output distinctly personal rather than generic AI content
- Supports both hybrid (vector + full-text) and semantic-only search

### session_search
- Use for: checking prior thinking on related topics
- Run BEFORE fresh research to avoid redundancy
- No API cost, often overlooked
