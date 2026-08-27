#!/usr/bin/env python3
"""s07_skill_loading.py - advertise small skill summaries, load details on demand."""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import yaml
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)
WORKDIR = Path.cwd()
SKILLS_DIR = WORKDIR / "skills"
client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")


class SkillLoader:
    """Discover skills from skills/<name>/SKILL.md and expose their metadata."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills: dict[str, dict] = {}
        self.scan()

    def scan(self):
        if not self.skills_dir.is_dir():
            return
        for skill_file in self.skills_dir.glob("*/SKILL.md"):
            try:
                text = skill_file.read_text()
                if not text.startswith("---"):
                    continue
                _, frontmatter, _ = text.split("---", 2)
                metadata = yaml.safe_load(frontmatter) or {}
                name = metadata.get("name", skill_file.parent.name)
                self.skills[name] = {
                    "name": name,
                    "description": metadata.get("description", ""),
                    "path": skill_file,
                }
            except Exception as error:
                print(f"[skill warning] could not load {skill_file}: {error}")

    def catalog(self) -> str:
        if not self.skills:
            return "(no skills found)"
        return "\n".join(
            f"- **{item['name']}**: {item['description']}"
            for item in self.skills.values()
        )

    def load(self, name: str) -> str:
        skill = self.skills.get(name)
        if not skill:
            return f"Skill not found: {name}. Available: {', '.join(self.skills) or '(none)'}"
        return skill["path"].read_text()


skill_loader = SkillLoader(SKILLS_DIR)
SYSTEM = f"""You are a coding agent at {WORKDIR}.

You have base tools for working in this directory. You also have optional skills.
The skill catalog is cheap context; call load_skill only when a skill is relevant.

<available_skills>
{skill_loader.catalog()}
</available_skills>
"""


def run_bash(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True,
                                text=True, timeout=120)
        output = (result.stdout + result.stderr).strip()
        return output[:50000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: timeout after 120 seconds"


def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = (WORKDIR / path).resolve().read_text().splitlines()
        if limit is not None and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as error:
        return f"Error: {error}"


def run_write(path: str, content: str) -> str:
    try:
        target = (WORKDIR / path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as error:
        return f"Error: {error}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        target = (WORKDIR / path).resolve()
        content = target.read_text()
        if old_text not in content:
            return f"Error: text not found in {path}"
        target.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as error:
        return f"Error: {error}"


def run_glob(pattern: str) -> str:
    try:
        matches = [str(path.relative_to(WORKDIR)) for path in WORKDIR.glob(pattern)]
        return "\n".join(matches) if matches else "(no matches)"
    except Exception as error:
        return f"Error: {error}"


def run_load_skill(name: str) -> str:
    return skill_loader.load(name)


def tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required}}}


TOOLS = [
    tool("bash", "Run a shell command.", {"command": {"type": "string"}}, ["command"]),
    tool("read_file", "Read a file.", {"path": {"type": "string"}, "limit": {"type": "integer"}}, ["path"]),
    tool("write_file", "Write a file.", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    tool("edit_file", "Replace exact text once.", {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, ["path", "old_text", "new_text"]),
    tool("glob", "Find paths with a glob pattern.", {"pattern": {"type": "string"}}, ["pattern"]),
    tool("load_skill", "Load the complete SKILL.md for a listed skill.", {"name": {"type": "string"}}, ["name"]),
]
TOOL_HANDLERS = {"bash": run_bash, "read_file": run_read, "write_file": run_write,
                 "edit_file": run_edit, "glob": run_glob, "load_skill": run_load_skill}


def execute_tool(block: SimpleNamespace) -> str:
    print(f"\033[90m[tool] {block.name}\033[0m")
    try:
        handler = TOOL_HANDLERS.get(block.name)
        return str(handler(**block.input)) if handler else f"Unknown tool: {block.name}"
    except Exception as error:
        return f"Error: {error}"


def agent_loop(messages: list[dict]):
    while True:
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, max_tokens=8000,
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            return message.content or ""

        for tool_call in message.tool_calls:
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as error:
                output = f"Error: invalid tool arguments: {error}"
            else:
                output = execute_tool(SimpleNamespace(name=tool_call.function.name, input=arguments))
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": output})


def main():
    history = [{"role": "system", "content": SYSTEM}]
    print("DeepSeek Skill Loading Agent. Type 'exit' to quit.")
    while True:
        try:
            query = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if query.lower() in {"exit", "quit"}:
            return
        if not query:
            continue
        history.append({"role": "user", "content": query})
        print(f"\nAssistant: {agent_loop(history)}")


if __name__ == "__main__":
    main()
