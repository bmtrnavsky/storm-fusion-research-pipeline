# STORM Fusion Research Pipeline -- Quick Reference

**This is a methodology reference and skill specification, not runnable code.**

An adaptation of Stanford's STORM method (NAACL 2024) for content creation, using OpenRouter Fusion for multi-model diversity.

## Pipeline

Phase 1: Perspective Discovery (Nemotron 3 Ultra maps 6-8 expert viewpoints, human approves)
Phase 2: Expert Interview (Fusion panel: Nemotron Ultra + GPT-OSS 120B + Gemma 4 31B + MiniMax M2.5, fused by DeepSeek V4 Flash)
Phase 2.5: Human Validation Checkpoint (Brad validates post-synthesis, pre-curation)
Phase 3: Curate and Outline (Nemotron 3 Ultra, living, evolving structure)
Phase 4: Grounded Writing (Nemotron 3 Ultra, every claim sourced, "needs more research" over padding)
Phase 5: Moderator Pass (Nemotron 3 Ultra, audit for source bias and false connections -- highest-leverage role)
Final Polish (cos-heavy DeepSeek V4 Flash, temperature zero)

## Two Modes

**STORM-Full (Multi-Model):** Perspectives in parallel, each processed by the OpenRouter Fusion panel. For pillar-level content, ambitious claims, cross-domain synthesis.

**STORM-Light (Single-Model):** Nemotron 3 Ultra role-plays all perspectives sequentially. For routine posts, time-sensitive pieces. Faster, cheaper.

## Model Assignment

| Phase | Model |
|-------|-------|
| Phase 1: Perspective Discovery | Nemotron 3 Ultra |
| Phase 2: Expert Interview (Full) | Fusion panel (4 models) |
| Phase 2: Expert Interview (Light) | Nemotron 3 Ultra (sequential) |
| Phase 2.5: Human Validation | Brad (no model) |
| Phase 3: Curate and Outline | Nemotron 3 Ultra |
| Phase 4: Grounded Writing | Nemotron 3 Ultra |
| Phase 5: Moderator/Auditor | Nemotron 3 Ultra |
| Final Polish | cos-heavy (DeepSeek V4 Flash) |

**Fusion panel per POV:**
- Nemotron 3 Ultra 550B (NVIDIA, US-origin, agentic RL, Mamba-Transformer hybrid)
- GPT-OSS 120B (OpenAI, RLHF-heavy, STEM/math, Western training)
- Gemma 4 31B (Google DeepMind, factual grounding, math, multimodal)
- MiniMax M2.5 (MiniMax Shanghai, distinct Chinese lab lineage)
- Fuser: DeepSeek V4 Flash

**Fallback chain:** Nemotron Ultra → Nemotron Super 120B → DeepSeek V4 Flash

## Search Stack

Web search: internet facts and current data
RAG / Knowledge store: prior knowledge and cross-domain connections
Session / Memory search: prior thinking (run first to avoid redundancy)

## When to Use

STORM-Full: pillar-level content, major research pieces, cross-domain synthesis
STORM-Light: regular posts, time-sensitive pieces, established domain knowledge

## License

MIT

## Credits

Based on STORM by Shao et al., Stanford Oval Lab, NAACL 2024.
Co-STORM collaborative extension, EMNLP 2024.
Reference implementation: github.com/stanford-oval/storm
Adaptation: github.com/bmtrnavsky/storm-fusion-research-pipeline