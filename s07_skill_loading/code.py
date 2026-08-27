#!/usr/bin/env python3
"""
s07_skill_loading.py - Skill Loading

The system prompt contains a catalog of skill names and descriptions.
The model loads the full SKILL.md only when it calls load_skill.
    skills/                    Startup
    +------------------+       +------------------+
    | code-review/     | ----> | SkillLoader      |
    |   SKILL.md       |       | name + summary   |
    | pdf/             |       +--------+---------+
    |   SKILL.md       |                |
    +------------------+                v
                                 system prompt catalog
    LLM -- load_skill(name) --> full SKILL.md
     ^                              |
     +--------- tool result --------+
"""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import yaml

try:
    import readline
    readline.parse_and_bind("set bind-tty-special-chars off")
    readline.parse_and_bind("set input-meta on")
    readline.parse_and_bind("set output-meta on")
    readline.parse_and_bind("set convert-meta off")
except ImportError:
    pass

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)
WORKDIR = Path.cwd()
SKILLS_DIR = WORKDIR / "skills"
client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")


# -- Skill catalog --

class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills: dict[str, dict[str, str]] = {}
        self.scan()

    @staticmethod
    def parse_frontmatter(text: str) -> tuple[dict, str]:
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        try:
            metadata = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        return metadata, parts[2].lstrip()

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

    def catalog(self) -> str:
        if not self.skills:
            return "(no skills found)"
        return "\n".join(f"- {skill['name']}: {skill['description']}" for skill in self.skills.values())

    def load(self, name: str) -> str:
        skill = self.skills.get(name)
        if skill:
            return skill["content"]
        available = ", ".join(self.skills) or "none"
        return f"Error: Unknown skill '{name}'. Available: {available}"


SKILL_LOADER = SkillLoader(SKILLS_DIR)


def build_system_prompt() -> str:
    return (
        f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. "
        "Act, don't explain.\n\n"
        f"Skills available:\n{SKILL_LOADER.catalog()}\n\n"
        "Use load_skill to read the full instructions when a skill applies."
    )


SYSTEM = build_system_prompt()


# -- Tools --

def run_bash(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True,
                                text=True, timeout=120)
        output = (result.stdout + result.stderr).strip()
        return output[:50000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, limit: Optional[int] = None) -> str:
    try:
        lines = (WORKDIR / path).resolve().read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as error:
        return f"Error: {error}"


def run_write(path: str, content: str) -> str:
    try:
        file_path = (WORKDIR / path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as error:
        return f"Error: {error}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        file_path = (WORKDIR / path).resolve()
        text = file_path.read_text()
        if old_text not in text:
            return f"Error: text not found in {path}"
        file_path.write_text(text.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as error:
        return f"Error: {error}"


def run_glob(pattern: str) -> str:
    import glob
    try:
        matches = []
        for match in glob.glob(pattern, root_dir=WORKDIR):
            if (WORKDIR / match).resolve().is_relative_to(WORKDIR):
                matches.append(match)
        return "\n".join(matches) if matches else "(no matches)"
    except Exception as error:
        return f"Error: {error}"


def tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOLS = [
    tool("bash", "Run a shell command.", {"command": {"type": "string"}}, ["command"]),
    tool("read_file", "Read file contents.", {"path": {"type": "string"}, "limit": {"type": "integer"}}, ["path"]),
    tool("write_file", "Write content to a file.", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    tool("edit_file", "Replace exact text in a file once.", {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, ["path", "old_text", "new_text"]),
    tool("glob", "Find files matching a glob pattern.", {"pattern": {"type": "string"}}, ["pattern"]),
    tool("load_skill", "Load the full SKILL.md content by skill name.", {"name": {"type": "string"}}, ["name"]),
]
TOOL_HANDLERS = {"bash": run_bash, "read_file": run_read, "write_file": run_write,
                 "edit_file": run_edit, "glob": run_glob, "load_skill": SKILL_LOADER.load}


# -- Hooks --

HOOKS = {"UserPromptSubmit": [], "PreToolUse": [], "PostToolUse": [], "Stop": []}


def register_hook(event: str, callback):
    HOOKS[event].append(callback)


def trigger_hooks(event: str, *args):
    for callback in HOOKS[event]:
        result = callback(*args)
        if result is not None:
            return result
    return None


DENY_LIST = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if="]
DESTRUCTIVE = ["rm ", "> /etc/", "chmod 777"]


def permission_hook(block):
    """PreToolUse: block denied operations and ask about risky ones."""
    if block.name == "bash":
        command = block.input.get("command", "")
        for pattern in DENY_LIST:
            if pattern in command:
                print(f"\n\033[31m[blocked] '{pattern}'\033[0m")
                return "Permission denied by deny list"
        for keyword in DESTRUCTIVE:
            if keyword in command:
                print("\n\033[33m[permission] Potentially destructive command\033[0m")
                print(f"   Tool: {block.name}({block.input})")
                choice = input("   Allow? [y/N] ").strip().lower()
                if choice not in ("y", "yes"):
                    return "Permission denied by user"
    if block.name in ("read_file", "write_file", "edit_file"):
        path = block.input.get("path", "")
        if not (WORKDIR / path).resolve().is_relative_to(WORKDIR):
            print("\n\033[33m[permission] Access outside workspace\033[0m")
            print(f"   Tool: {block.name}({block.input})")
            choice = input("   Allow? [y/N] ").strip().lower()
            if choice not in ("y", "yes"):
                return "Permission denied by user"
    return None


def log_hook(block):
    """PreToolUse: log every tool call."""
    args_preview = str(list(block.input.values())[:2])[:60]
    print(f"\033[90m[HOOK] {block.name}({args_preview})\033[0m")
    return None


def large_output_hook(block, output):
    """PostToolUse: warn on large output."""
    if len(str(output)) > 100000:
        print(f"\033[33m[HOOK] Large output from {block.name}: {len(str(output))} chars\033[0m")
    return None


def context_inject_hook(query: str):
    """UserPromptSubmit: log the working directory."""
    print(f"\033[90m[HOOK] UserPromptSubmit: working in {WORKDIR}\033[0m")
    return None


def summary_hook(messages: list[dict]):
    """Stop: print the number of tool results in this message list."""
    tool_count = sum(message.get("role") == "tool" for message in messages)
    print(f"\033[90m[HOOK] Stop: session used {tool_count} tool calls\033[0m")
    return None


register_hook("UserPromptSubmit", context_inject_hook)
register_hook("PreToolUse", permission_hook)
register_hook("PreToolUse", log_hook)
register_hook("PostToolUse", large_output_hook)
register_hook("Stop", summary_hook)


def execute_tool(block) -> str:
    blocked = trigger_hooks("PreToolUse", block)
    if blocked:
        return str(blocked)
    handler = TOOL_HANDLERS.get(block.name)
    try:
        output = handler(**block.input) if handler else f"Unknown: {block.name}"
    except Exception as error:
        output = f"Error: {error}"
    trigger_hooks("PostToolUse", block, output)
    return str(output)


def agent_loop(messages: list[dict]) -> str:
    while True:
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, max_tokens=8000,
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if not message.tool_calls:
            force = trigger_hooks("Stop", messages)
            if force:
                messages.append({"role": "user", "content": force})
                continue
            return message.content or ""
        for tool_call in message.tool_calls:
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as error:
                output = f"Error: invalid tool arguments: {error}"
            else:
                block = SimpleNamespace(name=tool_call.function.name, input=arguments)
                output = execute_tool(block)
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": output})


if __name__ == "__main__":
    print("s07: Skill Loading - catalog first, full content on demand (DeepSeek)")
    print("Enter a question, press Enter to send. Type q to quit.\n")
    history = [{"role": "system", "content": SYSTEM}]
    while True:
        try:
            query = input("\033[36ms07 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        trigger_hooks("UserPromptSubmit", query)
        history.append({"role": "user", "content": query})
        print(agent_loop(history))
        print()
