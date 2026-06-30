# STORM Operational Improvements

**Status:** Next build phase -- documented but not implemented yet.
**Last updated:** 2026-06-29

## 1. Trace Context

**Problem:** When a multi-POV run fails or produces inconsistent output, debugging is hard. Subagent outputs are isolated -- there's no shared correlation ID tying artifacts back to a specific run, phase, and POV.

**Solution:** Every artifact (subagent output, judge report, moderator report, final draft) carries a structured trace context:

```json
{
  "run_id": "20260629-192339",
  "phase": "phase2-interview",
  "pov_id": "pov-03-skeptic",
  "model": "fusion:4-model-panel",
  "fuser": "deepseek/deepseek-v4-flash"
}
```

**Implementation:** Add `run_id` (timestamp-based) at pipeline start. Pass it through every `delegate_task` call via context. Each subagent embeds it in output metadata. Log files and cosdb entries keyed on `run_id + phase + pov_id`.

**Benefit:** Full traceability. Replay any POV. Compare outputs across runs. Debug exactly where quality degraded.

## 2. Dead Letter Queue

**Problem:** Subagent calls fail. Network timeouts, model rate limits, malformed prompts. When a POV subagent fails, the POV report is lost. The moderator either synthesizes without it (reducing coverage) or the whole run stalls waiting for a retry that never comes.

**Solution:** Failed subagent calls are written to a dead letter queue (cosdb table or file-based) with:
- The original prompt and context
- Failure reason (timeout, rate limit, model error, malformed output)
- Timestamp and run_id
- Retry count

**Implementation:** Wrap subagent dispatch in try/catch. On failure, write to `storm-dlq/{run_id}/{pov_id}.json`. Add a retry pass after all initial batches complete: read the DLQ, re-dispatch failed POVs (max 2 retries). If still failing, flag the POV as [FAILED] in the moderator report.

**Benefit:** No POV is silently lost. Partial failures don't kill the run. DLQ becomes a diagnostic resource for identifying systematic failure patterns.

## 3. Per-Run Structured Log

**Problem:** Pipeline runs produce unstructured output. There's no historical record of which models were used, how long each phase took, token consumption, or success/failure rates. Optimizing the pipeline requires data, and right now the data is scattered across log files and memory.

**Solution:** Write a structured run summary to cosdb after each pipeline completion:

```json
{
  "run_id": "20260629-192339",
  "timestamp": "2026-06-29T19:23:39-05:00",
  "tier": "mid",
  "topic": "...",
  "pov_count": 7,
  "phases": {
    "phase1-discovery": { "model": "cos-heavy", "latency_s": 45, "status": "ok" },
    "phase2-interview": { "model": "fusion-panel", "latency_s": 312, "status": "ok", "povs_completed": 7 },
    "phase3-curate": { "model": "owl-alpha", "latency_s": 28, "status": "ok" },
    "phase4-write": { "model": "owl-alpha", "latency_s": 180, "status": "ok" },
    "phase5-moderate": { "model": "owl-alpha", "latency_s": 67, "status": "ok" }
  },
  "tokens": { "input": 45000, "output": 12000 },
  "cost_usd": 0.84,
  "outcome": "complete",
  "povs_flagged": ["pov-05-safety"],
  "brad_checkpoints": ["phase1", "phase5"]
}
```

**Implementation:** After each phase completes, append to a run log in cosdb. On pipeline completion, write the full summary. Queryable by run_id, tier, topic, date range.

**Benefit:** Historical performance data. Identify which phases are bottlenecks. Track model quality over time. Justify tier selection with real numbers. Feed into future model tiering decisions.

## 4. Idempotent POV Checkpointing

**Problem:** If a batch of POV subagents partially fails (2 of 5 succeed, then the session dies), the next run has no way to know which POVs are already complete. It either re-runs all 5 (wasting time and tokens on the 2 that succeeded) or manually tracks completion.

**Solution:** After each POV subagent completes, write a checkpoint file to `storm-checkpoints/{run_id}/{pov_id}.json`. On pipeline start (or restart), check for existing checkpoints. Skip completed POVs. Only dispatch missing ones.

**Implementation:**
- Checkpoint path: `storm-checkpoints/{run_id}/pov-{NN}-{slug}.json`
- Checkpoint content: pov_id, status (complete/failed), output_path, completed_at
- On pipeline start: scan for run_id checkpoints, build a completion set
- Dispatch only POVs not in the completion set
- On subagent completion: write checkpoint atomically

**Benefit:** Partial batch failures are recoverable. No wasted compute on completed POVs. Enables mid-run interruption and resumption. Critical for long-running Full tier (10 POVs, potentially 10+ minutes of subagent work).

---

## Implementation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Idempotent POV Checkpointing | Medium | Prevents wasted work on partial failures |
| 2 | Dead Queue | Low | No POVs silently lost |
| 3 | Per-Run Structured Log | Low | Data-driven optimization |
| 4 | Trace Context | Medium | Debugging at scale |

All four can be implemented incrementally. None change the pipeline output -- they're operational infrastructure only.
