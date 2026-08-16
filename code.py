#!/usr/bin/env python3
"""s01_agent_loop.py - The Agent Loop.

The entire secret of an AI coding agent in one pattern:

    while the model calls a tool:
        response = LLM(messages, tools)
        execute tools
        append results

Usage:
    pip install openai python-dotenv
    DEEPSEEK_API_KEY=... python code.py
"""

import json
import os
import subprocess

try:
    import readline
    # #143 UTF-8 backspace fix for macOS libedit
    readline.parse_and_bind('set bind-tty-special-chars off')
    readline.parse_and_bind('set input-meta on')
    readline.parse_and_bind('set output-meta on')
    readline.parse_and_bind('set convert-meta off')
except ImportError:
    pass

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

# -- Tool definition: just bash --
TOOLS = [{
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}]


# -- Tool execution --
def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=os.getcwd(),
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"


# -- The core pattern: a while loop that calls tools until the model stops --
def agent_loop(messages: list):
    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            max_tokens=8000,
        )
        message = response.choices[0].message

        # Append assistant turn
        messages.append(message.model_dump(exclude_none=True))

        # If the model didn't call a tool, we're done
        if not message.tool_calls:
            return

        # Execute each tool call, collect results
        for tool_call in message.tool_calls:
            if tool_call.function.name == "bash":
                command = json.loads(tool_call.function.arguments)["command"]
                print(f"\033[33m$ {command}\033[0m")
                output = run_bash(command)
                print(output[:200])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": output,
                })


# -- Entry point --
if __name__ == "__main__":
    print("s01: Agent Loop (DeepSeek)")
    print("Enter a question, press Enter to send. Type q to quit.\n")

    history = [{"role": "system", "content": SYSTEM}]
    while True:
        try:
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        # Print the model's final text response
        print(history[-1].get("content") or "")
        print()
