# STORM Method (Stanford, NAACL 2024)

**Paper:** "Assisting in Writing Wikipedia-like Articles from Scratch with Large Language Models" by Shao et al., Stanford Oval Lab.
**Follow-up:** Co-STORM (collaborative extension with human-in-the-loop, EMNLP 2024).
**Reference implementation:** github.com/stanford-oval/storm (29.2k stars)
**LangGraph port:** github.com/braincrew-lab/STORM-Research-Assistant
**Public adaptation:** github.com/bmtrnavsky/storm-content-creator

## Core Insight

Direct prompting produces shallow, single-perspective questions. STORM solves this by mimicking an investigative journalist: discover multiple perspectives, interview experts, ground every claim in retrievable sources.

## The Five-Phase Pipeline

### Phase 1: Perspective Discovery

- **Role:** Senior Research Strategist
- **Task:** Map 6-8 distinct expert perspectives the topic deserves
- **Output:** For each perspective: persona name, what they care about, sharpest questions they would ask
- **Key mechanism:** Survey related articles to discover diverse viewpoints automatically
- **Why it works:** Different perspectives produce different questions; generic prompts produce generic questions
- **Researcher checkpoint:** Present perspectives to the researcher for approval before proceeding. the researcher can reject, add, or modify. This is the first human checkpoint.

### Phase 2: Expert Interview (Researcher Modification -- Fusion Architecture)

All tiers now use OpenRouter Fusion. Each POV gets 4 analysis models fused into a single report by DeepSeek V4 Flash. POV count is the only variable between tiers.

#### Fusion Panel (all tiers, every POV)

Every POV is researched by 4 models simultaneously, fused into one report:

```json
{
  "model": "openrouter/owl-alpha",
  "plugins": [{
    "id": "fusion",
    "analysis_models": [
      "openrouter/owl-alpha",
      "nvidia/nemotron-3-ultra-550b-a55b:free",
      "openai/gpt-oss-120b:free",
      "google/gemma-4-31b-it:free"
    ],
    "model": "deepseek/deepseek-v4-flash"
  }]
}
```

- **Fuser model:** DeepSeek V4 Flash (cos-heavy) -- synthesizes all 4 analysis model outputs into one coherent POV report
- **Analysis models:** Owl Alpha (reasoning), Nemotron 3 Ultra (frontier MoE), gpt-oss-120b (STEM/math), Gemma 4 31B (general/multimodal)
- **Cost:** Only the fuser prompt is charged (DeepSeek V4 Flash). All 4 analysis models run free tiers.
- **Owl Alpha** serves as both an analysis model here AND the Phase 5 moderator -- sequential stages, no conflict.

#### Tier Selection (POV count only)

| Tier | POVs | Sub-agent Calls | When to Use |
|------|-------|-----------------|-------------|
| Light | 4-5 | 4-5 | Routine content, time-sensitive, established territory |
| Mid | 6-8 | 6-8 | Ambitious posts, cross-domain, echo chamber risk |
| Full | 8-10 | 8-10 | Pillar content, academic depth, definitive guides |

#### Process (all tiers)

1. Phase 1 outputs N expert POVs with persona + sharpest questions.
2. **Single search pass per POV** (cost efficiency): For each perspective, run web_search + web_extract (Firecrawl) + Perplexity ONCE. Cache the retrieved sources.
3. Dispatch N independent delegate_task subagents (batches of 3 respecting max_concurrent_children). Each subagent owns ONE POV and includes the full Fusion config in its prompt.
4. Each subagent outputs a structured report with cited sources for its assigned POV. The Fusion plugin returns a single fused report -- no per-model reconciliation needed.
5. Moderator (Owl Alpha) collects all N reports.
6. the researcher interview pass: moderator presents synthesized findings across all reports, highlighting agreements, disagreements, and unique angles. the researcher stress-tests disagreements, gaps, missing angles.
7. Moderator reconciles contradictions, flags unresolved claims as [VERIFY].

**Cost comparison:**

| Tier | Old Method | Old Calls | Fusion Method | Fusion Calls | Fuser Cost |
|------|-----------|-----------|---------------|--------------|------------|
| Light | 1 model x 5 POV | 5 | 4 models x 5 POV | 5 | ~5 prompts DeepSeek |
| Mid | 2 models x 8 POV | 16 | 4 models x 8 POV | 8 | ~8 prompts DeepSeek |
| Full | 2 models x 8 POV | 16 | 4 models x 10 POV | 10 | ~10 prompts DeepSeek |

Fusion delivers 2-4x the model diversity per POV at the same or lower dispatch count. The fuser cost (DeepSeek V4 Flash at $0.14/$0.28 per 1M) is negligible.

- **Hard rule:** If a factual claim cannot be backed by a real source AND the researcher cannot confirm from experience, output "unverified" -- fabrication is strictly forbidden.
- **Researcher modification novelty:** No published work runs 4-model Fusion perspective interviews with cached source sharing + real human practitioner interview. This is a genuine contribution.

#### Parallel Writing Pattern (all tiers)

Draft the full post while subagent interviews run in background. Revise after all batches return. This parallelizes research and writing without blocking output.

### Phase 3: Curate and Outline

- **Role:** Meticulous Editor
- **Task:** Organize interview logs into clean, hierarchical outline
- **Output:** Sections grouped by theme, duplicates removed, contradictions between sources explicitly flagged
- **Key requirement:** Every section mapped to specific sources collected during interviews
- **Living outline:** Outline is not static. It evolves as interviews surface new information. Use insert and reorganize operations. Mirrors Co-STORM's dynamic mind map concept.

### Phase 4: Grounded Writing

- **Role:** Technical Writer
- **Task:** Write post section by section following the outline exactly, plus expert interview insights
- **Constraint:** Every claim points back to a collected source
- **Hard rule:** If a section is thin on data, write "needs more research" instead of padding
- **Banned phrases:** No em-dashes. No hollow adjectives ("groundbreaking," "revolutionary," "game-changing," "transformative"). No "delve," "dive deep," "unpack," "demystify," "journey." No generic openers. No summary closings.
- **Verification flags:** Use [VERIFY] for claims that cannot be backed by a real source AND the researcher cannot confirm

### Phase 5: Co-STORM Moderator Pass

- **Role:** Independent Moderator / Auditor
- **Task:** Blind spot sweep for unknown unknowns -- critical questions no one thought to ask
- **Why this is the highest-leverage role:** Co-STORM evaluation found that removing the moderator hurts performance more than reducing the number of experts. Single expert + moderator > multiple experts without moderator.
- **Red-team constraints:** Audit for two named failure modes:
  1. **Source bias transfer:** Leaning too heavily on a single biased source
  2. **Over-association of unrelated facts:** Creating red herrings by connecting facts that are not actually related
- **Output:** Flagged errors fixed before final output
- **Researcher checkpoint:** Present moderator findings to the researcher. Second human checkpoint.

## Co-STORM Evaluation Data (for calibration)

Tested against RAG chatbots and STORM+QA across seven metrics (human evaluation, 20 participants):

| Metric | RAG Chatbot | STORM+QA | Co-STORM |
|--------|-------------|----------|----------|
| Report Relevance | 3.57 | 3.61 | **3.78** |
| Report Breadth | 3.50 | 3.61 | **3.79** |
| Report Depth | 3.26 | 3.43 | **3.77** |
| Report Novelty | 2.44 | 2.50 | **3.05** |
| Unique URLs | 2.94 | 2.89 | **6.04** |

Key finding: Removing the moderator hurts performance more than reducing the number of experts.
78% of participants preferred Co-STORM over RAG chatbots overall.

## Model Tiering (2026-06-29 -- Fusion Update)

| Pipeline Stage | Model | Rationale |
|----------------|-------|-----------|
| Phase 1: Perspective Discovery | cos-heavy (deepseek-v4-flash) | Strongest fast model, structured research output |
| Phase 2: Expert Interview (all tiers) | Fusion: 4 models (Owl Alpha + Nemotron 3 Ultra + gpt-oss-120b + Gemma 4 31B) fused by DeepSeek V4 Flash | 4-model diversity per POV, single fuser cost |
| Phase 3: Curate and Outline | Owl Alpha | Frontier tier, structured output, reliability |
| Phase 4: Grounded Writing | Owl Alpha | Frontier tier, voice matching for researcher's final review |
| Phase 5: Moderator/Auditor | Owl Alpha | Highest-leverage role; needs frontier reasoning strength |
| Final Polish | cos-fast (gemini-2.5-flash-lite) | Mechanical task; speed only, quality not critical |

**Fusion panel per POV:**
- `openrouter/owl-alpha` -- frontier reasoning
- `nvidia/nemotron-3-ultra-550b-a55b:free` -- frontier MoE reasoning (55B active of 550B)
- `openai/gpt-oss-120b:free` -- STEM, math, coding strength
- `google/gemma-4-31b-it:free` -- general, multimodal, Google-backed
- **Fuser:** `deepseek/deepseek-v4-flash` -- synthesizes all 4 into one report

**Model hierarchy (strongest to weakest):** Owl Alpha (frontier) > cos-heavy (DeepSeek 4 Flash) > Nemotron 3 Ultra (free MoE) > gpt-oss-120b (free) > Gemma 4 31B (free) > cos-deep (Gemini Flash) > cos-fast (Flash Lite)

**Fallback chain (matches config.yaml fallback_chain):**
1. Owl Alpha (primary -- strongest model, no escalation above it)
2. Nemotron 3 Ultra 550B (free -- frontier MoE, second strongest)
3. Nemotron 3 Super 120B (free -- stable, strong tool caller)
4. DeepSeek V4 Flash (paid -- last resort safety net)

If Owl Alpha is unavailable (rate limit, outage), the fallback chain automatically promotes the next model. Do not escalate as a reflex.

**Parallel subagent batching:** max_concurrent_children=3. Dispatch interviews in batches of 3. Draft post in parallel while interviews run.

## Philosophy and Design Rationale

### Why Fusion Changes the Nature of STORM

Standard STORM uses a single model per POV. The "perspective diversity" comes entirely from the persona prompt -- you're asking one model to roleplay different viewpoints. The model's training biases, knowledge gaps, and reasoning patterns are constant across every perspective. Genuine disagreement between POVs is largely theatrical.

With Fusion, each POV is researched by four models with genuinely different architectures, training data, companies, and knowledge biases:

- **Owl Alpha** (OpenRouter/frontier reasoning)
- **Nemotron 3 Ultra 550B** (NVIDIA/US agentic, MoE architecture)
- **gpt-oss-120b** (OpenAI/RLHF, STEM/math strength)
- **Gemma 4 31B** (Google/DeepMind, general/multimodal)

When the DeepSeek Flash judge surfaces disagreements between panel models, those are **real disagreements** rooted in different training, not one model arguing with itself. The moderator in Phase 3 is reconciling genuine intellectual diversity, not synthetic persona variation.

### The Compounding Effect

**Standard STORM pipeline:**
persona diversity -> question diversity -> single-model answers -> moderator synthesizes thin outputs

**Fusion STORM pipeline:**
persona diversity -> question diversity -> 4-model panel answers -> judge pre-synthesizes per POV -> moderator synthesizes already-rich outputs

The moderator receives pre-fused intelligence, not raw single-model takes. It's working with a higher quality input at every step. Each phase compounds the one before it -- the panel feeds the judge, the judge feeds the moderator, the moderator feeds the writer. Quality at the top of the funnel cascades down.

### Why the Judge Matters More Than the Panel

Per OpenRouter's own research, approximately 75% of Fusion's quality lift comes from the synthesis step, not model diversity. The judge's structured output -- consensus, contradictions, gaps, unique insights -- is what makes the POV report richer than any single model could produce.

Panel diversity supplies the raw material. The judge does the actual intellectual work.

This means the architecture is not "more models = better." It's "more models feeding a synthesizer = better." The synthesizer quality is the bottleneck. That's why DeepSeek V4 Flash (cos-heavy, the strongest reasoner in the stack) is the fuser, not a cheaper model.

### Why This Is Novel

No published STORM implementation runs multi-model Fusion at the POV level. The Stanford paper and all known implementations use single models per perspective. This architecture -- 4-model free panel + cheap judge + human moderator across N perspectives -- achieves near-frontier research quality at near-zero cost.

This is This implementation's original contribution to the STORM methodology. Document it as such.

### The Operational Implication

Cost is no longer a reason to limit POV count. The only constraint is how many genuinely distinct perspectives a topic deserves. Choose tier based on topic complexity, not budget.

| Old Constraint | New Constraint |
|----------------|----------------|
| "How many POVs can we afford?" | "How many POVs does this topic deserve?" |
| Budget-driven tier selection | Complexity-driven tier selection |
| 2 models per POV (costly) | 4 models per POV (free) |
| Trade depth for cost | Depth is the default |

The Fusion panel cost is only the fuser prompt (DeepSeek V4 Flash at $0.14/$0.28 per 1M tokens). All four analysis models run free tiers. A Full run with 10 POVs costs approximately 10 fuser prompts -- still under $1.

## Search Stack Detail

**Hierarchy: web search is primary. RAG is context. conversation history search is pre-check. Perplexity is supplementary.**

See `references/search-hierarchy.md` for the full rationale and implementation preference.

### Full Search Stack (2026-06-25)

| Layer | Tool | Status | Best For |
|-------|------|--------|---------|
| Internet facts | web_search (exa) | Active | Current events, specific claims, dates |
| Web extraction | web_extract (firecrawl) | Active | Full page content, PDFs, articles |
| External synthesis | Perplexity (sonar-pro) | Active | Parallel fact-checking, multi-source comparisons |
| Knowledge base context | vector database RAG | Active | researcher's knowledge base, cross-domain connections |
| Prior thinking | conversation history search | Active | What the researcher already said/thought on the topic |
| Internal reasoning | x_search (Grok) | Active | Complex reasoning (not web search) |

### Tool Availability Reality Check

Before starting Phase 2, verify which search tools are actually available. Do not assume any specific tool is configured. Check in this order:

1. `check your agent framework's configuration | grep -i search` -- reveals configured search backends
2. `env | grep -i "PERPLEX\|SEARCH\|API"` -- reveals available API keys in env
3. `check your agent framework's configuration 2>/dev/null | grep -i "perplex"` -- keys may live in config.yaml but not env
4. Default available tools: `web_search`, `web_extract`, `conversation history search`, RAG (vector database)

**Perplexity Discovery Pattern (2026-06-25):** researcher requested Perplexity. Env var was empty. Config.yaml at `web.perplexity.api_key` contained a valid key. Verified live with curl to API endpoint -- returned 200. Lesson: always check config.yaml for backends that may be configured but not exposed via environment variables. API keys can be in config.yaml, .env file (redacted in display), or actual env vars. Check all three locations.

**If the researcher requests a tool that is not configured:**
- Tell him immediately. Do not silently substitute.
- Offer the best available alternative from the configured stack.
- Ask if he wants to configure the missing tool before proceeding.

**Hard rule:** Never claim to have done "full storm research" if you only ran web_search + RAG. Full STORM requires the complete 5-phase pipeline with subagent interviews Plus verified sources.

## When to Use: Tier Selection (POV Count)

All tiers use the same Fusion panel (4 models per POV). The only variable is how many perspectives the topic deserves.

**STORM-Light (4-5 POVs, 4-5 sub-agent calls):** Routine blog posts, time-sensitive pieces, topics within well-established domain knowledge. Fast, cheap, sufficient for most content.

**STORM-Mid (6-8 POVs, 6-8 sub-agent calls):** Ambitious posts, cross-domain topics, or when single-model echo chamber is a risk. Good middle ground for important but not pillar content.

**STORM-Full (8-10 POVs, 8-10 sub-agent calls):** Pillar-level content, deep academic problems, definitive guides, topics where genuine perspective diversity matters more than cost. Requires the researcher's time for Phase 2 interview and Phase 5 review. Reserve for content that justifies the depth.

**Decision criteria:**
- Routine post, established territory -> Light (4-5 POV)
- Important post, some ambiguity -> Mid (6-8 POV)
- Pillar content, academic depth, ambitious claims -> Full (8-10 POV)
- researcher available for interview checkpoints? -> Mid or Full. If not -> Light.
- Budget concern? -> All tiers are nearly free (only fuser prompts cost anything). Scale up POV count without cost anxiety.

**Cost is no longer a tier differentiator.** The Fusion fuser (DeepSeek V4 Flash) costs $0.14/$0.28 per 1M tokens. A Full run with 10 POVs costs ~10 fuser prompts -- still under $1. The analysis models are all free. Choose tier based on how many perspectives the topic deserves, not cost.

## Pipeline Mapping to Pipeline Agent Mapping

| STORM Phase | this implementation Agent | Notes |
|-------------|-----------|-------|
| Phase 1: Perspective Discovery | Provocateur + Forensic Scientist | Formalize persona + questions format |
| Phase 2: Expert Interview | the researcher (human) + Forensic Scientist (research) | Novel modification; model researches, the researcher stress-tests |
| Phase 3: Curate and Outline | Military Planner | Add contradiction-flagging requirement; living outline |
| Phase 4: Grounded Writing | Master Editor | Adopt "needs more research" instead of padding |
| Phase 5: Moderator | Auditor | Formalize the two named failure modes as checks |

## Banned Phrases and Patterns for Blog Posts

These apply specifically to your content:

- Em-dashes (use commas, periods, or line breaks)
- "is the one that landed"
- "the floor" / "on the floor" / "from the floor"
- Supply chain / DC ops / warehouse references (unless the topic is literally logistics)
- Hollow adjectives: "groundbreaking," "revolutionary," "game-changing," "transformative"
- Generic openers: "In today's rapidly evolving landscape..."
- "Delve," "dive deep," "unpack," "demystify," "journey"
- Summary closings ("In conclusion," "The bottom line is...")
- Promotion language ("innovative," "cutting-edge")
- Vague attributions ("experts say," "studies show") -- name the specific source
- Significance inflation ("stands as a testament," "pivotal role")

## Implementation Notes

- Reference implementation: github.com/stanford-oval/storm (4 modules)
- LangGraph port: github.com/braincrew-lab/STORM-Research-Assistant
- Public adaptation: github.com/bmtrnavsky/storm-content-creator (v0.1.0)
- In this implementation, web_search replaces Tavily/ArXiv as the primary retrieval tool
- **Lessons learned from live pipeline runs:** see `references/storm-lessons-learned.md`
