[English](README.md) · [中文](README.zh.md)

# s07: Skill Loading — Load Knowledge Only When Needed

Previous chapters keep adding tools to the agent. This chapter adds a different extension: a skill is a Markdown instruction file with YAML metadata. The agent sees a short catalog at startup, then calls `load_skill` when a task needs the full instructions.

```text
startup: scan skills/*/SKILL.md → put name + description in the system prompt
runtime: task mentions a matching domain → load_skill(name) → use the full guide
```

This keeps the initial context small while making specialised workflows available.

## A skill file

Create a file such as `skills/release/SKILL.md` at the repository root:

```md
---
name: release
description: Prepare and verify a Python release.
---

# Release guide

Run tests, update the version, then summarize the changes.
```

`SkillLoader` reads only the frontmatter during `scan()`. The body stays out of the context until `load_skill("release")` is called.

## DeepSeek implementation

The tutorial uses DeepSeek's OpenAI-compatible client and the default `deepseek-v4-flash` model:

```python
client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
```

The tool response is appended to the same conversation as every other tool call:

```python
messages.append({
    "role": "tool",
    "tool_call_id": tool_call.id,
    "content": output,
})
```

## Try it

From the repository root:

```sh
mkdir -p skills/release
# Create skills/release/SKILL.md using the example above.
python s07_skill_loading/code.py
```

Then ask: `Use the release skill to explain how you would prepare this project for release.`

The agent should first call `load_skill` and then answer using the loaded guide.

## What changed from s06?

| Part | s06 | s07 |
|---|---|---|
| Extension | Delegate to a new agent | Give the same agent optional knowledge |
| Startup context | Fixed system prompt | Compact skill catalog |
| On demand | `task(prompt)` | `load_skill(name)` |
| Main benefit | Separate context for a subtask | Avoid loading irrelevant instructions |

The source teaching sequence is adapted from [learn-claude-code](https://github.com/lyq1119/learn-claude-code). Only the runnable API integration is changed for DeepSeek.
