# STORM Content Creator

A practitioner-built implementation of Stanford's STORM methodology using OpenRouter Fusion to research topics with 4 parallel AI models per perspective.

Based on: Shao et al., NAACL 2024 -- "Assisting in Writing Wikipedia-like Articles from Scratch with Large Language Models"

## What is STORM?

STORM (Synthesis of Topic Outlines through Retrieval and Multi-perspective question asking) is a research pipeline from Stanford's Oval Lab that mimics how investigative journalists work: discover multiple expert perspectives, interview each one, ground every claim in retrievable sources, then synthesize into comprehensive research output.

Instead of asking one LLM to write from a generic prompt, STORM discovers the distinct viewpoints a topic deserves, researches each independently, and reconciles disagreements through a moderator pass. The result is research depth that no single-model prompt can match.

## What Makes This Implementation Different -- Fusion Architecture

Every published STORM implementation uses a single model per perspective. The "perspective diversity" comes from a persona prompt -- you ask one model to roleplay different viewpoints. The model's training biases, knowledge gaps, and reasoning patterns stay constant across every perspective. **Genuine disagreement between viewpoints is largely theatrical.**

This implementation uses **OpenRouter Fusion** to run 4 genuinely different models per perspective:

- **Owl Alpha** -- frontier reasoning
- **Nemotron 3 Ultra 550B** -- NVIDIA MoE architecture, US agentic training
- **gpt-oss-120b** -- OpenAI RLHF, STEM/math strength
- **Gemma 4 31B** -- Google DeepMind, general and multimodal

A **DeepSeek V4 Flash** judge synthesizes all 4 outputs into a single POV report, surfacing consensus, contradictions, gaps, and unique insights. The moderator in the final phase reconciles genuine intellectual diversity across perspectives, not synthetic persona variation.

Per OpenRouter's research, approximately 75% of Fusion's quality lift comes from the synthesis step. The panel supplies raw material. The judge does the intellectual work.

**Result:** Near-frontier research quality at near-zero cost. All 4 analysis models run free tiers. Only the fuser prompt is charged.

## How It Works

### Phase 1: Perspective Discovery
A senior research strategist maps 4-10 distinct expert perspectives the topic deserves. Each persona gets a name, what they care about, and the sharpest questions they would ask. The researcher reviews and approves perspectives before proceeding.

### Phase 2: Expert Interview (Fusion Architecture)
Each POV is researched by 4 models simultaneously, fused into one report by DeepSeek V4 Flash. A single search pass per POV caches retrieved sources (web search, web extraction, Perplexity, RAG). Subagents run in parallel batches of 3.

### Phase 2.5: The Reality Check (Human in the Loop)

Standard STORM relies purely on simulated experts. We added a mandatory practitioner checkpoint. Once the Fusion panel synthesizes the data, the AI interviews a human expert: "Research says X. From your experience in this domain, does this track? What is missing?"

If a claim cannot be backed by a source or the human's lived experience, it gets cut. Reality beats theory.

No published STORM implementation replaces the simulated expert with a real human practitioner. This is the differentiator.

### Phase 3: Curate and Outline
Organize interview logs into a clean hierarchical outline. Sections grouped by theme, duplicates removed, contradictions explicitly flagged. Every section mapped to specific sources.

### Phase 4: Grounded Writing
Write section by section following the outline. Every claim points back to a collected source. Thin sections get "needs more research" instead of padding. Suitable for academic research, market analysis, technical documentation, investigative journalism, and long-form research output.

### Phase 5: Moderator Pass
Independent blind-spot sweep for unknown unknowns. Co-STORM evaluation found that removing the moderator hurts performance more than reducing the number of experts. The researcher reviews moderator findings as the final checkpoint.

## Quick Start

```bash
# Clone
git clone https://github.com/bmtrnavsky/storm-fusion-research-pipeline.git
cd storm-fusion-research-pipeline

# Requires OpenRouter API key with access to:
# - openrouter/owl-alpha
# - nvidia/nemotron-3-ultra-550b-a55b:free
# - openai/gpt-oss-120b:free
# - google/gemma-4-31b-it:free
# - deepseek/deepseek-v4-flash
```

Designed to run via any agent framework supporting OpenRouter's API with tool use and web search enabled. See SKILL.md for the full pipeline implementation.

## Model Configuration

| Pipeline Stage | Model | Rationale |
|----------------|-------|-----------|
| Phase 1: Perspective Discovery | Owl Alpha | Frontier reasoning, structured research output |
| Phase 2: Expert Interview | Fusion: 4 models fused by DeepSeek V4 Flash | 4-model diversity per POV, single fuser cost |
| Phase 3: Curate and Outline | Owl Alpha | Frontier tier, structured output, reliability |
| Phase 4: Grounded Writing | Owl Alpha | Frontier tier, voice consistency for researcher's final review |
| Phase 5: Moderator/Auditor | Owl Alpha | Highest-leverage role; needs frontier reasoning strength |
| Final Polish | Owl Alpha | Final review pass before researcher delivery |

### Model Hierarchy (strongest to weakest)

Owl Alpha (frontier) > DeepSeek V4 Flash > Nemotron 3 Ultra (free MoE) > gpt-oss-120b (free) > Gemma 4 31B (free)

### Fusion Panel per POV

- `openrouter/owl-alpha` -- frontier reasoning
- `nvidia/nemotron-3-ultra-550b-a55b:free` -- frontier MoE reasoning (55B active of 550B)
- `openai/gpt-oss-120b:free` -- STEM, math, coding strength
- `google/gemma-4-31b-it:free` -- general, multimodal, Google-backed
- **Fuser:** `deepseek/deepseek-v4-flash` -- synthesizes all 4 into one report

## Results

Tested against RAG chatbots and STORM+QA across seven metrics (Co-STORM human evaluation, 20 participants):

| Metric | RAG Chatbot | STORM+QA | Co-STORM |
|--------|-------------|----------|----------|
| Report Relevance | 3.57 | 3.61 | **3.78** |
| Report Breadth | 3.50 | 3.61 | **3.79** |
| Report Depth | 3.26 | 3.43 | **3.77** |
| Report Novelty | 2.44 | 2.50 | **3.05** |
| Unique URLs | 2.94 | 2.89 | **6.04** |

Key finding: Removing the moderator hurts performance more than reducing the number of experts.

## Tiers

All tiers use the same Fusion panel. The only variable is how many perspectives the topic deserves.

| Tier | POVs | Sub-agent Calls | When to Use |
|------|------|-----------------|-------------|
| Light | 4-5 | 4-5 | Routine research, time-sensitive, established territory. Light bypasses the Fusion panel -- single model, sequential perspectives. No human checkpoint. |
| Mid | 6-8 | 6-8 | Ambitious research, cross-domain, echo chamber risk. Full Fusion panel per POV. |
| Full | 8-10 | 8-10 | Pillar research, academic depth, definitive reports. Full Fusion panel per POV plus human practitioner checkpoint (Phase 2.5). |

## Implementation Notes

- Reference implementation: [stanford-oval/storm](https://github.com/stanford-oval/storm) (29.2k stars)
- LangGraph port: [braincrew-lab/STORM-Research-Assistant](https://github.com/braincrew-lab/STORM-Research-Assistant)
- This repo: [bmtrnavsky/storm-fusion-research-pipeline](https://github.com/bmtrnavsky/storm-fusion-research-pipeline)
- web_search replaces Tavily/ArXiv as the primary retrieval tool in this implementation

## License

MIT
