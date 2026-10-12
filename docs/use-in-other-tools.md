# Use it in Claude Code, Codex, OpenCode, OpenWork, and Pi

The method is a folder of plain markdown plus one optional script. Any agent that can load a
`SKILL.md` skill can run modes 1 and 2. Any agent that can run a shell command can run mode 3
through `run_panel.py`. You pick the models in every tool; this repo never ships a lineup.

**Status:** the paths below come from each tool's current docs (linked at the end). The skill
itself has been tested in Hermes only. Treat the other tools as "should work, tell me what
breaks."

## The same three steps everywhere

1. **Install the skill.** Copy the folder `skills/storm-fusion-research/` into the tool's skills
   directory (table below). It holds `SKILL.md` and its `references/`.
2. **Tell the agent which tools you have.** `SKILL.md` names Hermes tools (`delegate_task`,
   `storm_run_panel`, `web_search`). Other tools call these things something else. Say it once
   at the start of a run: "Use your own web search. For mode 2 use your own subagents. For
   mode 3 run `python run_panel.py panel.json` instead of `storm_run_panel`."
3. **Keep the gates.** You still approve the cast, validate the seat reports, make the call,
   and approve the audit. No human at the gates means mode 1 only.

## Where things live

| Tool | Skills folder | Project instructions | Mode 2 (parallel seats) | Mode 3 |
|------|---------------|----------------------|--------------------------|--------|
| Claude Code | `~/.claude/skills/` or `.claude/skills/` | `CLAUDE.md` | Subagents, one per seat | `run_panel.py` |
| Codex | `~/.agents/skills/` or `.agents/skills/` | `AGENTS.md` | Subagents (TOML files in `.codex/agents/`) | `run_panel.py` |
| OpenCode | `.opencode/skills/`, `~/.config/opencode/skills/`, and it also reads the Claude and `.agents` paths | `AGENTS.md` | Subagents, but parallel runs are only documented for the built-in general one | `run_panel.py` |
| OpenWork | Built on OpenCode, so use the OpenCode paths. Teams can also publish skills through OpenWork Den. | Same as OpenCode | Same as OpenCode | `run_panel.py` |
| Pi | `~/.agents/skills/` or `.agents/skills/` | `AGENTS.md` under `~/.pi/agent/` | No native subagents; run mode 1, or use mode 3 | `run_panel.py` |

## Claude Code

- Copy the skill folder to `~/.claude/skills/storm-fusion-research/` (all projects) or
  `.claude/skills/storm-fusion-research/` (one repo). Run it with `/storm-fusion-research`, or
  just say "run a storm panel on ...".
- Mode 2: ask for "one subagent per seat, each given only its seat card." Subagents run in
  their own context and return summaries, which is what a seat report should be.
- For a real multi-model fanout across seats, use `run_panel.py` (see below).

## Codex

- Put the skill folder in `.agents/skills/` in your repo, or `~/.agents/skills/` for everywhere.
  Put "use the storm-fusion-research skill for panel research" in `AGENTS.md` if you want it
  picked up without asking.
- Mode 2: define a seat subagent as a TOML file in `.codex/agents/` and let Codex run them in
  parallel. Each agent file can set its own `model`. Concurrency is capped in
  `.codex/config.toml` under `[agents]` (`max_threads`).
- Source note: these Codex details come from a third-party write-up, not OpenAI's own docs.
  Check your installed version.

## OpenCode

- Put the skill at `.opencode/skills/storm-fusion-research/SKILL.md` (this repo), or
  `~/.config/opencode/skills/` (global). OpenCode also reads `.claude/skills/` and
  `.agents/skills/`, so a copy you already made for Claude Code works.
- The skill loads on demand through its `skill` tool. The `name` in the frontmatter must match
  the folder name (`storm-fusion-research` does).
- Seat subagents: a markdown file in `.opencode/agents/` with `mode: subagent` and an optional
  `model: provider/model-id`. A subagent uses the calling agent's model if you leave `model` out.
- Parallel subagents are not clearly documented, so for mode 2 expect the seats may run one at a
  time. Mode 3 through `run_panel.py` does not depend on subagents, because it is a plain script (it makes its calls one after another).

## OpenWork

- OpenWork is a desktop app built on OpenCode, so OpenCode's skill and agent rules apply.
  Its docs did not give local install steps, so start with the OpenCode paths and check the
  OpenWork docs if the skill does not show up.
- Teams can publish skills to an org or team through OpenWork Den, and the OpenWork MCP exposes
  `list_skills` and `get_skill`. That is the easy way to hand this skill to a whole team.

## Pi

- Put the skill in `~/.agents/skills/storm-fusion-research/` or `.agents/skills/`. Pi lists skill
  names in its prompt and loads one when the task matches. Force it with
  `/skill:storm-fusion-research`. Run `/reload` after editing.
- Pi has no built-in subagents (they exist as example extensions). Use mode 1 for a quick
  panel, or mode 3 with `run_panel.py` for a real multi-model run.
- Pi can switch models mid-session with `/model`, which suits mode 1 if you want a different
  brain per seat by hand.

## Mode 3 from any tool: `run_panel.py`

Ask the agent to write the panel file from the approved cast, run `--dry-run` first, then run
it. Nested fanout works here too: give a lineup slot `reference_models` plus an `aggregator`
under a `moa` key and the script fans out again inside that slot. See
`docs/use-without-hermes.md` for the file format, flags, and cost math.

## Sources

- Claude Code: [Extend Claude Code](https://code.claude.com/docs/en/features-overview)
- Codex: [Codex CLI customisation stack](https://codex.danielvaughan.com/2026/04/12/codex-cli-customisation-stack-unified-system/) (third party)
- OpenCode: [Skills](https://opencode.ai/docs/skills), [Agents](https://opencode.ai/docs/agents)
- OpenWork: [README](https://github.com/different-ai/openwork)
- Pi: [Skills](https://pi.dev/docs/latest/skills), [overview](https://urandom.io/blog/2026-03-07-pi-dev-deep-dive)
