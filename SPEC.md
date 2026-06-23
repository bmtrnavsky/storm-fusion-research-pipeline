# STORM Content Creator

An adaptation of Stanford's STORM method (NAACL 2024) for content creation with three key innovations:

1. **Human Expert Interviews** -- replaces the simulated expert with a real domain practitioner
2. **Three-Layer Search** -- web search + RAG (personal knowledge management) + session memory
3. **Model Tiering** -- fast models for high-volume research, strong models for reasoning stages

## Pipeline

Phase 1: Perspective Discovery
Phase 2: Human Expert Interview (AI researches, human stress-tests)
Phase 3: Curate and Outline (living, evolving structure)
Phase 4: Grounded Writing (every claim sourced, no padding)
Phase 5: Moderator Pass (audit for source bias and false connections)

## Model Map

Fast model (DeepSeek 4 Flash): interviews, perspective discovery, polish
Strong model (Owl Alpha / Sonnet 4.6): outline, writing, moderator

## Search Stack

web_search: internet facts and current data
RAG: personal vault knowledge and cross-domain connections
session_search: prior thinking (run first to avoid redundancy)

## Usage

This is a methodology reference. Load it when creating cornerstone content or major research pieces. For regular posts, use the lightweight variant (Phases 1, 3, 5 only).

## License

MIT

## Credits

Based on STORM by Shao et al., Stanford Oval Lab, NAACL 2024.
Co-STORM collaborative extension, EMNLP 2024.
Reference implementation: github.com/stanford-oval/storm
