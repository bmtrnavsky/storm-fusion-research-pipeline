# STORM Research Method

**Version:** 0.2.0
**Author:** Brad Trnavsky
**License:** MIT
**Description:** STORM research method (Stanford, NAACL 2024) adapted for content creation. Five-phase pipeline: perspective discovery, expert interview (simulated + human), curation/outline, grounded writing, moderator audit. Includes STORM-Light (single-model) and STORM-Full (multi-model) modes.

# STORM Research Method

**Synthesis of Topic Outlines through Retrieval and Multi-perspective Question Asking**

Based on Stanford's STORM (Shao et al., NAACL 2024) and Co-STORM (EMNLP 2024).
Reference: github.com/stanford-oval/storm
This adaptation: github.com/bmtrnavsky/storm-content-creator

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
For pillar-level content, ambitious claims, cross-domain synthesis, or whenever genuine perspective diversity matters more than speed. Phase 2 runs 8 independent research perspectives in parallel, each anchored to its own model instance. Requires human expert availability for Phase 2 and Phase 5 checkpoints. Higher token cost in Phase 2.

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

**STORM-Light process:** One model simulates all perspectives sequentially. Ground each persona in real web search. Capture sources per claim.

**STORM-Full process:** Dispatch 8 independent research runs in parallel. Each run owns ONE perspective and its own model instance (mix at least 2 different models across the 8 runs -- do not use the same model for all). Each run outputs a structured report with cited sources.

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

## Model Assignment (Recommended)

| Pipeline Stage | Light Mode | Full Mode | Rationale |
|----------------|-----------|-----------|-----------|
| Phase 1: Perspective Discovery | Fast model | Fast model | Structured output, speed |
| Phase 2: Simulated Interview | Fast model (single, sequential) | 8 independent runs, mixed models | Light: speed. Full: diversity |
| Phase 3: Curate and Outline | Strong model | Strong model | Structured, reliable |
| Phase 4: Grounded Writing | Strong model | Strong model | Voice matching for hand-edit |
| Phase 5: Moderator/Auditor | Strong model | Strong model | Highest-leverage role |
| Final Polish | Fast model | Fast model | Mechanical task; speed only |

**Full mode model diversity rule:** In Phase 2, do not assign the same model to all 8 perspectives. Mix at least 2 different models across the 8 runs. Different training data, different biases, different blind spots.

**Fallback:** If the strong model hits a reasoning ceiling on the moderator role, escalate to a stronger model. Do not escalate as a reflex.

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

## Credits

Based on STORM by Shao et al., Stanford Oval Lab, NAACL 2024.
Co-STORM collaborative extension, EMNLP 2024.
Reference implementation: github.com/stanford-oval/storm
