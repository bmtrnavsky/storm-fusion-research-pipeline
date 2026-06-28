# STORM Content Creator -- Quick Reference

**This is a methodology reference and skill specification, not runnable code.**

An adaptation of Stanford's STORM method (NAACL 2024) for content creation.

## Pipeline

Phase 1: Perspective Discovery (AI maps 6-8 expert viewpoints, human approves)
Phase 2: Expert Interview (AI researches via multi-layer search, human stress-tests)
Phase 3: Curate and Outline (living, evolving structure)
Phase 4: Grounded Writing (every claim sourced, "needs more research" over padding)
Phase 5: Moderator Pass (audit for source bias and false connections -- highest-leverage role)

## Two Modes

**STORM-Full (Multi-Model):** 8 independent research perspectives in parallel, each anchored to its own model instance. For pillar-level content, ambitious claims, cross-domain synthesis. Higher token cost.

**STORM-Light (Single-Model):** One model role-plays all perspectives sequentially. For routine posts, time-sensitive pieces. Faster, cheaper.

## Model Assignment

Fast model: perspective discovery, interviews (Light mode), polish
Strong model: outline, writing, moderator
Mixed models (2+): interviews (Full mode) -- diversity is the point

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
Adaptation: github.com/bmtrnavsky/storm-content-creator
