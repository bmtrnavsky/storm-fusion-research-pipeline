"""Storm panel plugin: skill plus the automatic panel-execution tool."""

from pathlib import Path

from .panel import PANEL_TOOL_SCHEMA, make_panel_handler


def register(ctx):
    skills_dir = Path(__file__).parent / "skills"
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.exists():
            ctx.register_skill(child.name, skill_md)
    ctx.register_tool(
        name="storm_run_panel",
        toolset="storm",
        schema=PANEL_TOOL_SCHEMA,
        handler=make_panel_handler(ctx),
        description="Run a perspective-panel round across a model lineup, then judge.",
    )
