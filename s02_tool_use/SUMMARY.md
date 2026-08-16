# Project Summary

This is a summary of the tutorial's README files and dependency list.

---

## s01_agent_loop/README.md — The Agent Loop

**Core idea**: "One Loop Is All You Need" — the entire agent harness is a `while True` loop with two signals:

| Signal | Meaning | Loop Action |
|--------|---------|-------------|
| `stop_reason == "tool_use"` | Model requests a tool | Execute → feed result back → continue |
| `stop_reason != "tool_use"` | Model is done | Exit loop |

**The loop** (under 30 lines):
1. Start with the user's question as the first message.
2. Send messages + tool definitions to the LLM.
3. Append the model's response; if no tool call → return.
4. Execute requested tools (bash) and collect results.
5. Append results as a new message; repeat from step 2.

**Key points**:
- s01 has only **one tool: bash**.
- The model decides (which tool, whether to call), the harness executes and feeds results back.
- The next 16 chapters add mechanisms on top of this loop; the loop itself never changes.
- Safety: executes model-generated shell commands — run in a temporary test directory (permission controls arrive in s03).

**Try it**: `python s01_agent_loop/code.py`

---

## s02_tool_use/README.md — Tool Use

**Core idea**: "Add a tool, add just one handler" — the loop is unchanged from s01; only tool execution changes from hardcoded `run_bash()` to a `TOOL_HANDLERS` dispatch lookup.

**Tools expand from 1 to 5**:
- `bash` — run a shell command
- `read_file` — read file contents
- `write_file` — write content to file
- `edit_file` — replace text in file once
- `glob` — find files by pattern

**Adding a tool requires two things**:
1. One entry in the `TOOLS` array (JSON schema telling the model what it can do)
2. One mapping in the `TOOL_HANDLERS` dict (tool name → handler function)

**Multiple tool calls**: The model may return several `tool_use` blocks at once; they execute one by one in their original order.

**Changes from s01**:

| Component | Before (s01) | After (s02) |
|-----------|-------------|-------------|
| Tool count | 1 (bash) | 5 (+read, write, edit, glob) |
| Tool execution | Hardcoded `run_bash()` | TOOL_HANDLERS dispatch lookup |
| Path safety | None | `safe_path` validation (file tools only) |
| Loop | `while True` + `stop_reason` | Identical to s01 |

**Try it**: `python s02_tool_use/code.py` (e.g. "Read both README.md and requirements.txt, then create a summary file")

**Next**: s03 Permission — gate tool execution (bash is still unrestricted in s02).

---

## requirements.txt — Dependencies

- `openai>=1.0.0`
- `python-dotenv>=1.0.0`

Minimal dependency set: the OpenAI SDK (for LLM calls) and python-dotenv (for loading `.env` config, e.g. `DEEPSEEK_API_KEY`).

---

*Generated summary covering `s01_agent_loop/README.md`, `s02_tool_use/README.md`, and `requirements.txt`.*
