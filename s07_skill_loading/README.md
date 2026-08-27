# s07: Skill Loading — Load Skills When Needed

[English](README.md) · [中文](README.zh.md)

s01 → s02 → s03 → s04 → s05 → s06 → `s07` → s08 → s09 → ... → s16 → s17

> The system prompt contains the skill catalog; `load_skill` returns the full `SKILL.md`.
>
> **Harness Layer**: Knowledge loading — show the model which skills exist, then load one by name.

---

## The Problem

Suppose a project has a React component specification, a SQL style guide, and an API design document. We want the Agent to follow these rules during development, so the most direct approach is to put all of them into the system prompt:

```python
SYSTEM = (
    "You are a coding agent. "
    + open("docs/react-style.md").read()
    + open("docs/sql-style.md").read()
    + open("docs/api-design.md").read()
)
```

This makes every specification available, but every LLM call also sends all three documents. When the task only changes a React component, the SQL and API documents still consume tokens and context-window space that could hold code, conversation, and tool results.

---

## The Solution

```text
skills/*/SKILL.md ──scan at startup──> name + description in SYSTEM
                                                   │
LLM ──load_skill(name)──> full SKILL.md ──tool message──> messages[]
```

At startup, `SkillLoader` scans `skills/*/SKILL.md`, reads `name` and `description` from YAML frontmatter, and adds that catalog to the system prompt. When the model needs full instructions, it calls `load_skill(name)`; the returned `SKILL.md` is appended to the message list as a tool response.

| Content | Model input | Added |
|---------|-------------|-------|
| Skill name and description | system prompt | At startup |
| Full `SKILL.md` | tool message | When `load_skill` is called |

---

## How It Works

Each skill is a directory containing `SKILL.md`:

```text
skills/
  agent-builder/SKILL.md
  code-review/SKILL.md
  mcp-builder/SKILL.md
  pdf/SKILL.md
```

### Scan Skills

This is the same logic used by [`code.py`](code.py):

```python
def scan(self):
    self.skills.clear()
    if not self.skills_dir.exists():
        return
    for manifest in sorted(self.skills_dir.glob("*/SKILL.md")):
        content = manifest.read_text()
        metadata, body = self.parse_frontmatter(content)
        name = str(metadata.get("name") or manifest.parent.name).strip()
        description = metadata.get("description") or body.splitlines()[0]
        description = " ".join(str(description).lstrip("# ").split())
        self.skills[name] = {"name": name, "description": description, "content": content}
```

`catalog()` returns only names and descriptions:

```text
- code-review: Perform thorough code reviews...
- pdf: Process PDF files...
```

### Build the System Prompt

```python
def build_system_prompt() -> str:
    return (
        f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. "
        "Act, don't explain.\n\n"
        f"Skills available:\n{SKILL_LOADER.catalog()}\n\n"
        "Use load_skill to read the full instructions when a skill applies."
    )
```

The fixed Agent instructions and the scanned catalog are combined into the system prompt.

### Load Full Content

```python
def load(self, name: str) -> str:
    skill = self.skills.get(name)
    if skill:
        return skill["content"]
    available = ", ".join(self.skills) or "none"
    return f"Error: Unknown skill '{name}'. Available: {available}"
```

`name` looks up the startup registry; it is not treated as a file path. This is what prevents arbitrary files from being loaded by the skill tool.

---

## Try It

Create a skill at the repository root first:

```sh
mkdir -p skills/code-review
```

Then create `skills/code-review/SKILL.md`:

```md
---
name: code-review
description: Perform thorough code reviews with concrete, actionable findings.
---

# Code review guide

Read the changed code first. Report correctness, security, and test issues.
```

Run the chapter from the repository root:

```sh
python s07_skill_loading/code.py
```

Try these prompts:

1. `What skills are available?`
2. `Load the code-review skill and follow its instructions.`
3. `Review README.md and load the relevant skill first.`

Check that the system prompt contains only the catalog and that the full `SKILL.md` appears only after `load_skill` is called.

---

## What's Next

As tool calls accumulate, `messages[]` retains earlier file contents and tool results. The next natural problem is context compaction: shorten earlier messages while keeping enough information for later calls.

The lesson structure is adapted from [lyq1119/learn-claude-code](https://github.com/lyq1119/learn-claude-code), with the runnable API integration changed to DeepSeek.
