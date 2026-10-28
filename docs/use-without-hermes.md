# Use the panel without Hermes

The method does not depend on Hermes. Hermes just gives you a tool that runs the fanout for
you. Everything else (the seats, the judge, the four human gates) works anywhere. Pick the
path that matches how you work.

| Path | You need | Best for |
|------|----------|----------|
| A. Copy and paste | Any chat assistant | Trying the method, one-off decisions |
| B. `run_panel.py` | Python 3.9+, an OpenAI-compatible endpoint | Real multi-model fanout, repeatable runs |
| C. Your own agent | An agent framework | Wiring the panel into an existing workflow |

In every path, **you choose the models**. This repo never ships a default lineup, because
lineups go stale. See `skills/storm-fusion-research/references/storm-method.md` for how to
choose one.

## Path A: copy and paste

This is mode 1 (solo) or mode 2 (one chat per seat). It gives you viewpoint diversity but
not model diversity, which is still a real upgrade over asking one question one way.

**Step 1. Cast (gate 1).** Paste this, then edit the cast before moving on:

```
Question under review: <your question>

Propose the seats this question deserves. Size the panel to the problem: two seats for a
narrow technical call, up to a dozen for a broad societal issue. Include one skeptic and one
practitioner. For each seat give: name, what they care about, their 3 to 5 sharpest
questions, and why the seat matters. Do not answer the questions yet.
```

Approve, cut, or add seats. Seats you add yourself are the cast gate working, not failing.

**Step 2. Interview.** For each seat, in a fresh chat if you can (that is mode 2), paste:

```
You are the <seat name> seat on a perspective panel.
Seat brief: <what they care about>
Topic: <your question>
Answer these questions from this seat's viewpoint only:
- <question 1>
- <question 2>
Ground factual claims in retrievable sources and list them. Mark anything unsourced as
unverified. End with 3 to 5 key findings.
```

For mode 1, run the seats one after another in the same chat and say "now answer as the
next seat, ignoring what the previous seat concluded."

**Step 3. Validate (gate 2).** Read each seat report yourself. Correct what is wrong, add
what is missing. Anything that is neither sourced nor confirmed by you stays `unverified`.

**Step 4. Judge (gate 3).** Paste the validated reports into a chat, ideally with a
different and stronger model than the seats, and use:

```
You are the panel judge. Recommend, do not decide: the human makes the call.
Topic: <your question>

Seat reports:
<paste every report, labeled by seat>

Synthesize: consensus first, then contradictions WITH weights (which seats, what evidence,
never averaged away), then what stays unresolved or unverified. Ties and value calls go to
the human with the trade stated plainly.
```

You make the call.

**Step 5. Audit (gate 4).** Before you write anything up, paste the draft into a fresh chat:

```
You are an independent moderator auditing this draft. Check for: source-bias transfer
(leaning on one biased source), red herrings (connecting facts that are not related),
missing seats (viewpoints nobody consulted), and contradictions left unresolved. List
findings only. Do not rewrite.
```

Fix what it finds, then polish.

## Path B: the standalone script

`run_panel.py` runs mode 3 against any OpenAI-compatible chat endpoint. It uses the same
seat and judge prompts as the Hermes tool (it imports them from `panel.py`) and only the
Python standard library.

**1. Write the input file.** Same shape as the Hermes tool:

```json
{
  "topic": "Should a small DC add a second packing station before peak?",
  "seats": [
    {"name": "associate", "brief": "You pack boxes every shift.",
     "questions": ["Where does packing actually bottleneck?"]},
    {"name": "supervisor", "brief": "You own the shift plan and labor hours.",
     "questions": ["Does a second station pay back in one season?"]}
  ],
  "lineup": [{"model": "<model-a>"}, {"model": "<model-b>"}],
  "judge": {"model": "<judge-model>"}
}
```

Every seat runs across every model in `lineup`, then the judge synthesizes. Use the model
IDs your provider documents.

**2. Point it at an endpoint and run it.**

```bash
export STORM_API_KEY=...        # or the env var named by --api-key-env
python run_panel.py panel.json --base-url https://<your-provider>/v1 --out result.json
```

Any provider that speaks the OpenAI chat-completions format works, including hosted
routers and local servers. Local servers usually need no key, and the script then sends no
auth header.

**Nested fanout (a mini mixture of agents).** A lineup slot can ask several reference
models, then have an aggregator model merge them into one seat view:

```json
{"moa": {"reference_models": [{"model": "<a>"}, {"model": "<b>"}],
         "aggregator": {"model": "<merge-model>"}}}
```

This is the script's own stand-in for Hermes MoA. It does not call Hermes presets (those are
presets under the top-level `moa` key, used as `provider: moa` with the preset name as `model`, plugin path only). One level
only, and the aggregator should be a different model from the judge when you can.

**Useful options**

- `--dry-run` prints every prompt and calls nothing. Run this first to see what each seat
  will be asked, and to catch typos in the cast before you spend money.
- `--model <id>` uses one model for every seat and the judge (a mode 2 style run).
- A lineup slot can carry its own `base_url` and `api_key_env`, so one panel can span
  several providers. The `api_key_env` name must start with `STORM_` (anything else
  is refused), so a panel file can never point at an unrelated secret such as
  `OPENAI_API_KEY` or `AWS_SECRET_ACCESS_KEY`.

> [!WARNING]
> A slot's `base_url` receives that slot's key as a Bearer token. Only run panel
> files you trust, and only point slots at endpoints you trust.
- `--temperature`, `--max-tokens`, `--timeout` pass through as expected.

**What it does not do.** It runs the interview and the judge only. You still hold the gates:
approve the cast before you run it, read the raw seat reports (the result's
`seat_reports`) before you trust the verdict, and run the audit
step from Path A on whatever you write up. If a model call fails, the script stops with a
clear error and writes nothing partial. It never swaps in another model for you.

## Path C: your own agent

If you already run an agent framework, you do not need either path above. Reuse the pieces:

- `panel.py` has the seat prompt, the judge prompt, and the JSON schema the judge fills in.
  Only `make_panel_handler` touches Hermes (`ctx.llm`). The prompts and schema are plain
  Python.
- `skills/storm-fusion-research/SKILL.md` is the procedure. Most agent frameworks can load
  a markdown skill as instructions as-is, since it names tools generically.
- Keep the gates. The method falls apart without a human at the cast, validation, verdict,
  and audit steps.

## Costs, in plain terms

A mode 3 run makes `seats x models` seat calls plus one judge call. Two seats and three
models is seven calls. Twelve seats and four models is forty-nine, which is the cap: max
12 seats x 4 slots per run. Run `--dry-run`, count the calls it prints, and state the count
before any live run.

If a slot points at a Fusion or MoA style endpoint, that slot fans out again behind the
scenes. Multiply by the inner model count, and add a merge call per slot.
