# STORM Method, Panel Edition

Method background for the storm-fusion-research skill. Model-agnostic by design: no model
names appear here, because lineups age fast and the human picks the engine every run.

**Source method:** Shao et al., "Assisting in Writing Wikipedia-like Articles from Scratch
with Large Language Models," Stanford Oval Lab, NAACL 2024.
**Follow-up:** Co-STORM, Jiang et al., EMNLP 2024 (collaborative discourse with a human).
**Reference implementation:** [stanford-oval/storm](https://github.com/stanford-oval/storm)
**This adaptation:** [bmtrnavsky/storm-fusion-research-pipeline](https://github.com/bmtrnavsky/storm-fusion-research-pipeline)

Published evaluation numbers live in the README under Results. They come from the Co-STORM
paper, not from this repo, so they are not repeated or extended here.

## Core insight

Direct prompting produces shallow, single-viewpoint answers. STORM mimics an investigative
journalist: work out which viewpoints a topic deserves, interview each one, ground claims in
retrievable sources, then synthesize.

This adaptation changes the question. Stanford asks how to write the article. This asks how
to make the call. So the unit of work is a **seat** (a viewpoint with a stake in the
decision), the output is a recommendation with weighted contradictions, and a human decides.

## The pipeline and its four human gates

```
Cast -> Interview -> Validate -> Outline -> Write + Verdict -> Audit -> Polish
gate 1               gate 2                   gate 3          gate 4
```

1. **Cast (gate 1).** The orchestrator maps the seats the question deserves. For each seat:
   name, what they care about, their sharpest 3 to 5 questions, why the seat matters. Every
   cast includes one skeptic and one practitioner. The human approves, amends, or adds
   seats nobody proposed.
2. **Interview.** Each seat answers its questions from its own viewpoint only, grounded in
   sources. Seats report to the judge. They do not debate each other.
3. **Validate (gate 2).** Fused seat reports go to the human before any curation: does this
   track, what is missing, what is wrong. Only validated findings move on. Claims that are
   neither sourced nor human-confirmed stay marked `unverified`.
4. **Outline.** Group findings by theme, remove duplicates, flag contradictions explicitly,
   and map every section to its sources. The outline stays alive and changes as gaps close.
5. **Write, with the verdict (gate 3).** Write section by section from the outline. The
   judge recommends, with contradictions weighted by which seats and what evidence. The
   human makes the call.
6. **Audit (gate 4).** An independent moderator pass checks for source-bias transfer,
   red-herring connections between unrelated facts, missing seats, and unresolved
   contradictions. Findings go to the human for fixes before final polish.

Why the moderator matters: the Co-STORM evaluation found that removing the moderator hurt
results more than reducing the number of experts. Keep the audit even when you cut seats.

## Why more than one model

With one model, perspective diversity comes only from the persona prompt. Every seat shares
the same training data, blind spots, and reasoning habits, so disagreement between seats is
partly theater. With several models per seat, a disagreement can reflect different training
and different knowledge, which is worth more to a judge than a persona difference.

This only pays off if the judge is good. Many models feeding a weak synthesizer give you
more text, not a better call. Treat the judge as the bottleneck.

## Choosing models (the guidance this repo used to hardcode)

You pick the lineup for every run. Nothing in this repo supplies a default, and the tool
fails closed rather than guessing. Use these principles instead of a fixed list.

**For the seats (the fanout lineup):**
- **Spread across lineages.** Pick models from different vendors or training approaches,
  not three sizes of one family. Two models from the same family often share failure modes.
- **Mix open and closed weights, and mix regions of origin** when the topic is contested or
  culturally loaded. Different training corpora surface different framings.
- **Match capability to the seat.** A seat that needs arithmetic or tool use needs a model
  that can do it. A seat that voices a viewpoint can often run on a cheaper model.
- **Three or four models per seat is the useful range.** Beyond that, cost grows faster
  than the new angles you get. One model per seat is mode 2, which is fine for most work.

**For the judge:**
- Use the strongest reasoner you can afford. The judge reads every seat report and has to
  weigh contradictions without averaging them away.
- Prefer a model that reliably follows a JSON schema, since the tool asks for structured
  output (consensus, weighted contradictions, unresolved items).
- Keep the judge different from the models that wrote the seat reports when you can. A
  model grading its own family's output tends to agree with it.

**Before every run, check:**
1. Each model is reachable right now (keys, quotas, rate limits).
2. You know what a full run costs: seats x models x tokens per seat, plus one judge call.
3. The model supports what its seat needs (long context, tools, structured output).
4. The provider and model override flags are enabled if you are using the Hermes plugin.

**If a model fails mid-run:** stop and tell the human, who picks the replacement. Do not
silently swap in another model, since that changes who is actually on the panel.

## Sizing the panel

Size seats to the problem, not to a fixed tier. A societal question can seat a dozen
viewpoints. A broken deploy seats two (design and engineering). The human approves the
count at the cast gate.

| Mode | Seats | Models | Use when |
|------|-------|--------|----------|
| 1 Solo | 2 to 4 | One, sequential | Routine, well-understood, or no human available |
| 2 Native panel | 2 to 12, parallel | One family or one pick | Cross-domain synthesis you have not connected before |
| 3 Full panel | 2 to 12, each with fanout | Several per seat | Pillar claims, or where shared blind spots are the risk |

Past about four seats, prefer mode 2 or 3. One model playing twelve experts brings back the
echo chamber. Modes 2 and 3 need a human at the gates. Without one, run mode 1 only.

## Grounding and search

Whatever tools you have, order them the same way:

1. **Your own prior notes or memory first,** if you keep any. It is free and it stops you
   rediscovering what you already concluded.
2. **Web search, then page extraction,** to ground specific claims with real sources.
3. **Domain tools** (paper search, internal knowledge base) for cross-domain connections.

Write synthesis-forcing queries ("what does the research say about X"), not bare topic
queries. Before the interview step, confirm which of these tools actually work in your
setup. If one the human asked for is missing, say so and offer the nearest alternative. Do
not silently substitute, and never describe a run as a full panel if you only ran a search.

## Hard rules

- A factual claim with no real source, and no human confirmation, is marked `unverified`.
  Fabrication ends the run.
- A thin section says `needs more research`. Never pad.
- Contradictions ship with their weights. Never average them away or smooth them.
- The judge recommends. The human decides. Ties and value calls go to the human with the
  trade stated plainly.
- No new facts appear in the writing step that were not established in the interviews.

## Pitfalls

- Skipping the gates. Without a human this is roleplay.
- Fixed seat counts. Resize every run.
- Letting seats debate. Seats report, only the judge synthesizes.
- Reimplementing citations. Use a citation-ledger skill if you have one.
- Hardcoding models. Re-pick the lineup each run.
- Using mode 3 on a small question. Seats x models is the most expensive shape here.

## Running it

- **Hermes plugin:** see the README and `skills/storm-fusion-research/SKILL.md`.
- **Any other setup (a chat window, a script, your own agent):** see
  `docs/use-without-hermes.md`.
