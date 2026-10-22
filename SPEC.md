# Storm Panel -- Quick Reference (v0.5.0)

**Methodology reference, not runnable code. No model names appear here by design:
the human picks engines and lineups every run.**

Human-gated perspective panel. One question, several seats, one judge, one human.
Stanford STORM asks how to write the article; this asks how to make the call.

## Modes

**Mode 1 Solo:** 2-4 seats, one model role-plays sequentially. Diversity from POV only.
No keys. Routine questions, established territory, or no human available.

**Mode 2 Native panel:** 2-12 seats, one `delegate_task` subagent per seat in parallel.
Diversity from POV only. No keys. Human's model pick runs throughout.

**Mode 3 Full panel:** 2-12 seats, each seat its own fanout (OpenRouter Fusion or Hermes
MoA: presets under the top-level `moa` key, used as `provider: moa` with the preset name as `model`; lineup chosen by the human). Diversity from POV times models. Engine key
required. Pillar pieces, ambitious claims, shared-blind-spot risk. Cap 12 seats x 4 slots;
dry-run and state the call count first.

## Gates (human decides, judge recommends)

1. Cast: orchestrator proposes seats and count from complexity, human approves or amends.
2. Validation: fused seat reports checked pre-curation, only validated findings proceed.
3. Verdict: judge recommends with weighted contradictions, human makes the call.
4. Audit: moderator sweeps bias transfer, red herrings, missing seats, open contradictions.

## Pipeline

Cast -> interview (per mode) -> human validation -> outline -> grounded writing ->
moderator audit -> polish. Unsourced claims marked `unverified`. Thin sections say
`needs more research`. Full procedure: `skills/storm-fusion-research/SKILL.md`.
Design spec: `PANEL-SPEC.md`.

## Native cross-references

Citations: `grounded-citations`. Papers: `arxiv`.
Fanout mechanics: Hermes MoA docs. Prior thinking first: your memory or notes recall tool,
if you have one.

## License

MIT.

## Credits

Based on STORM by Shao et al., Stanford Oval Lab, NAACL 2024.
Co-STORM collaborative extension, EMNLP 2024.
Reference implementation: github.com/stanford-oval/storm
Adaptation: github.com/bmtrnavsky/storm-fusion-research-pipeline
