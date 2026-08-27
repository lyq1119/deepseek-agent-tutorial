# s07：Skill Loading —— 用到时再加载

[English](README.md) · [中文](README.zh.md)

s01 → s02 → s03 → s04 → s05 → s06 → `s07`

> system prompt 保存技能目录；`load_skill` 返回完整的 `SKILL.md`。
>
> **Harness 层**：知识加载 —— 让模型先知道有哪些技能，再按名称读取内容。

---

## 问题

假设某个项目有一套 React 组件规范、一份 SQL 风格指南和一份 API 设计文档。希望 Agent 在开发过程中遵守这些规范，最直接的做法就是把它们全部放进 system prompt：

```python
SYSTEM = (
    "You are a coding agent. "
    + open("docs/react-style.md").read()
    + open("docs/sql-style.md").read()
    + open("docs/api-design.md").read()
)
```

这种做法能让 Agent 读到所有规范，但每次调用 LLM 时也会发送三份全文。当前任务只修改 React 组件时，SQL 风格指南和 API 设计文档依然占用输入 token 和上下文窗口，留给代码、对话与工具结果的空间就会变少。

---

## 解决方案

```text
skills/*/SKILL.md ──启动时扫描──> 名称 + 描述放入 SYSTEM
                                            │
LLM ──load_skill(name)──> 完整 SKILL.md ──工具消息──> messages[]
```

启动时，`SkillLoader` 扫描 `skills/*/SKILL.md`，读取 YAML frontmatter 中的 `name` 和 `description`，并把这份目录加入 system prompt。模型需要完整说明时，调用 `load_skill(name)`；返回的 `SKILL.md` 作为工具消息追加到消息列表。

| 内容 | 进入模型的位置 | 何时加入 |
|------|----------------|----------|
| 技能名称和描述 | system prompt | 启动时 |
| 完整 `SKILL.md` | 工具消息 | 调用 `load_skill` 时 |

---

## 工作原理

每个技能是一个包含 `SKILL.md` 的目录：

```text
skills/
  agent-builder/SKILL.md
  code-review/SKILL.md
  mcp-builder/SKILL.md
  pdf/SKILL.md
```

### 扫描技能

下面的代码和 [`code.py`](code.py) 中的实现一致：

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

`catalog()` 只输出名称和描述：

```text
- code-review: Perform thorough code reviews...
- pdf: Process PDF files...
```

### 组装 system prompt

```python
def build_system_prompt() -> str:
    return (
        f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. "
        "Act, don't explain.\n\n"
        f"Skills available:\n{SKILL_LOADER.catalog()}\n\n"
        "Use load_skill to read the full instructions when a skill applies."
    )
```

固定的 Agent 指令和扫描得到的技能目录在这里组成实际传给模型的 system prompt。

### 加载完整内容

```python
def load(self, name: str) -> str:
    skill = self.skills.get(name)
    if skill:
        return skill["content"]
    available = ", ".join(self.skills) or "none"
    return f"Error: Unknown skill '{name}'. Available: {available}"
```

`name` 用于查询启动时建立的注册表，不会被当作文件路径，因此 skill 工具不会任意读取文件。

---

## DeepSeek API 适配

教程的控制流保持一致，可运行客户端使用 DeepSeek 的 OpenAI 兼容接口，默认模型为 `deepseek-v4-flash`：

```python
client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
```

DeepSeek 从 `message.tool_calls` 返回函数调用。实际循环会解析每个调用，并以匹配的 OpenAI 兼容工具消息格式追加结果：

```python
message = response.choices[0].message
messages.append(message.model_dump(exclude_none=True))

for tool_call in message.tool_calls:
    arguments = json.loads(tool_call.function.arguments)
    output = execute_tool(SimpleNamespace(
        name=tool_call.function.name, input=arguments,
    ))
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": output,
    })
```

`load_skill` 同样被定义为 OpenAI 兼容的函数工具，并和 `bash`、`read_file` 等工具一样通过 `TOOL_HANDLERS` 分发。

---

## 试一下

先在仓库根目录创建一个 skill：

```sh
mkdir -p skills/code-review
```

然后创建 `skills/code-review/SKILL.md`：

```md
---
name: code-review
description: Perform thorough code reviews with concrete, actionable findings.
---

# Code review guide

Read the changed code first. Report correctness, security, and test issues.
```

在仓库根目录运行本章：

```sh
python s07_skill_loading/code.py
```

试试这些 prompt：

1. `What skills are available?`
2. `Load the code-review skill and follow its instructions.`
3. `Review README.md and load the relevant skill first.`

观察 system prompt 中是否只有技能目录，以及调用 `load_skill` 后是否才出现完整的 `SKILL.md`。

---

## 接下来

随着工具调用增加，`messages[]` 会积累较早的文件内容和工具结果。下一个自然的问题是上下文压缩：缩短较早的消息，同时为后续调用保留足够的信息。

教程结构参考 [lyq1119/learn-claude-code](https://github.com/lyq1119/learn-claude-code)，可运行 API 已替换为 DeepSeek。
