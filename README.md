# STORM Content Creator

**Version:** 0.1.0
**License:** MIT

An adaptation of Stanford's STORM method (NAACL 2024) for content creation with three key innovations:

1. **Human Expert Interviews** -- replaces the simulated expert with a real domain practitioner
2. **Three-Layer Search** -- web search + RAG (personal knowledge management) + session memory
3. **Model Tiering** -- fast models for high-volume research, strong models for reasoning stages

Based on:
- [STORM Paper](https://arxiv.org/abs/2402.14207) -- Shao et al., Stanford Oval Lab, NAACL 2024
- [Co-STORM Paper](https://arxiv.org/abs/2408.15232) -- Collaborative extension, EMNLP 2024
- [Reference Implementation](https://github.com/stanford-oval/storm) -- 29.2k stars

---

## Table of Contents

- [Core Insight](#core-insight)
- [The Five-Phase Pipeline](#the-five-phase-pipeline)
- [Model Tiering](#model-tiering)
- [Search Stack Detail](#search-stack-detail)
- [When to Use Full vs Lightweight](#when-to-use-full-vs-lightweight)
- [Evaluation Data](#evaluation-data)
- [Known Failure Modes](#known-failure-modes)
- [Version History](#version-history)

---

## Core Insight

Direct prompting produces shallow, single-perspective questions. STORM solves this by mimicking an investigative journalist: discover multiple perspectives, interview experts, ground every claim in retrievable sources.

---

## The Five-Phase Pipeline

### Phase 1: Perspective Discovery

**Role:** Senior Research Strategist

**Task:** Map 6-8 distinct expert perspectives the topic deserves.

**Output:** For each perspective: persona name, what they care about, sharpest questions they would ask.

**Key mechanism:** Survey related articles to discover diverse viewpoints automatically. Different perspectives produce different questions; generic prompts produce generic questions.

**Human checkpoint:** Present perspectives to the domain expert for approval before proceeding. Expert can reject, add, or modify. This early gate saves hours of wasted work on wrong angles.

---

### Phase 2: Expert Interview (Human-in-the-Loop Modification)

**Role:** Interviewer (AI) + Expert (Human)

**Task:** Multi-turn back-and-forth dialogue for one perspective at a time.

**Search stack (three layers):**

| Layer | Tool | Use Case |
|-------|------|----------|
| Web Search | `web_search` | Broad internet facts, current data, specific claims |
| RAG | Vector + full-text search over personal vault | Cross-domain connections from prior knowledge |
| Session Memory | `session_search` | Prior thinking on related topics (run FIRST to avoid redundancy) |

**Process:**

1. AI researches the perspective using all three search layers
2. AI presents findings as structured interview: "Research says X. From your experience, does this track? What is missing? What is wrong?"
3. Expert responds. AI follows up, sharpens, challenges.
4. Repeat for each perspective.

**Hard rule:** If a claim cannot be backed by a real source AND the expert cannot confirm from experience, output `unverified`. Fabrication is strictly forbidden.

**Why this matters:** No published STORM implementation replaces the simulated expert with a real human practitioner. The human catches framing errors, adds nuance from lived experience, and stress-tests conclusions against reality.

---

### Phase 3: Curate and Outline

**Role:** Meticulous Editor

**Task:** Organize interview logs into a clean, hierarchical outline.

**Output:** Sections grouped by theme, duplicates removed, contradictions between sources explicitly flagged. Every section mapped to specific sources collected during interviews.

**Living outline:** The outline is not static. It evolves as interviews surface new information. Use insert and reorganize operations as research progresses. This mirrors Co-STORM's dynamic mind map concept.

---

### Phase 4: Grounded Writing

**Role:** Technical Writer

**Task:** Write report section by section following the outline exactly.

**Constraint:** Neutral, factual tone. Every claim points back to a collected source.

**Hard rule:** If a section is thin on data, write `needs more research` instead of padding with generic fluff.

---

### Phase 5: Moderator Pass

**Role:** Independent Moderator / Auditor

**Task:** Blind spot sweep for unknown unknowns -- critical questions no one thought to ask.

**Red-team constraints:** Audit for two named failure modes:

1. **Source bias transfer** -- leaning too heavily on a single biased source
2. **Over-association of unrelated facts** -- creating red herrings by connecting facts that are not actually related

**Output:** Flagged errors fixed before final output.

**Human checkpoint:** Present moderator findings to the expert for review. Expert approves fixes or adds direction.

**Why this matters most:** The Co-STORM evaluation found that removing the moderator hurts performance more than reducing the number of experts. Single expert + moderator beats multiple experts without a moderator. The moderator is the highest-leverage role in the system.

---

## Model Tiering

The STORM reference implementation supports different models for different stages. This adaptation applies tiering to manage cost and speed:

| Pipeline Stage | Model | Rationale |
|----------------|-------|-----------|
| Phase 1: Perspective Discovery | DeepSeek 4 Flash | Fast, strong at structured research output |
| Phase 2: Expert Interview | DeepSeek 4 Flash | High-volume token burn; fast and capable |
| Phase 3: Curate and Outline | Owl Alpha (Sonnet 4.6) | Structured output, reliability |
| Phase 4: Grounded Writing | Owl Alpha | Voice matching for human hand-edit pass |
| Phase 5: Moderator/Auditor | Owl Alpha | Highest-leverage role; needs real reasoning strength |
| Final Polish | DeepSeek 4 Flash | Mechanical task (dedup, summary); speed only |

**Fallback:** If the primary model hits a reasoning ceiling on the moderator role for complex cross-domain topics, escalate to a stronger model. Do not escalate as a reflex.

**Note:** The fast model is used for high-volume stages to manage rate limits and cost, not because it is more capable than the primary model.

---

## Search Stack Detail

### Web Search

- Use for: broad internet facts, current data, specific claim verification
- Query formulation: use synthesis-forcing queries (`what does research say about X`) not just topic queries (`X`)
- Run during Phase 2 interviews to ground answers in real sources

### RAG (Personal Knowledge Management)

- Use for: surfacing vault knowledge, cross-domain connections from prior notes
- Query during interviews: `what has the expert already written about [concept]`
- This is the differentiator -- makes output distinctly personal rather than generic AI content
- Supports both hybrid (vector + full-text) and semantic-only search

### Session Memory

- Use for: checking prior thinking on related topics
- Run BEFORE fresh research in Phase 2 to avoid redundancy
- No API cost, often overlooked

---

## When to Use Full vs Lightweight

**Full STORM (all 5 phases):**
- Cornerstone content, major research pieces, definitive guides
- Requires expert time for Phase 2 interviews and Phase 5 review

**Lightweight STORM (Phases 1, 3, 5 only):**
- Regular blog posts, shorter pieces
- Skip the interview phase; use perspective discovery + curation + moderator pass only

**Decision criteria:**

| Criteria | Full | Lightweight |
|----------|------|-------------|
| Pillar-level piece | Yes | No |
| Crosses multiple domains | Yes | No |
| Time-sensitive / news-driven | No | Yes |
| Expert available for checkpoints | Yes | No |

---

## Evaluation Data

Co-STORM evaluation (20 participants, human evaluation) against RAG chatbots:

| Metric | RAG Chatbot | STORM+QA | Co-STORM |
|--------|-------------|----------|----------|
| Report Relevance | 3.57 | 3.61 | **3.78** |
| Report Breadth | 3.50 | 3.61 | **3.79** |
| Report Depth | 3.26 | 3.43 | **3.77** |
| Report Novelty | 2.44 | 2.50 | **3.05** |
| Unique URLs | 2.94 | 2.89 | **6.04** |

Key findings:
- 78% preferred Co-STORM over RAG chatbots overall
- 67% rated it higher in Breadth and Serendipity
- Moderator removal hurts performance more than expert removal
- Single expert + moderator > multiple experts without moderator

---

## Known Failure Modes

From the Co-STORM paper:

1. **Source bias transfer** -- leaning too heavily on a single biased source
2. **Over-association of unrelated facts** -- connecting things that should not be connected

Both should be named checks in any moderator/auditor phase.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-06-23 | Initial release. Five-phase pipeline with human expert interviews, three-layer search, model tiering, Co-STORM evaluation data. |
