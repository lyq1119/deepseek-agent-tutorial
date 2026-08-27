[English](README.md) · [中文](README.zh.md)

# s07：Skill Loading —— 需要时再加载知识

前面的章节不断给 Agent 增加工具。本章增加另一种扩展：skill 是带 YAML 元数据的 Markdown 指令文件。Agent 启动时只看到精简目录；遇到相关任务时，才通过 `load_skill` 读取完整说明。

```text
启动：扫描 skills/*/SKILL.md → 将名称和描述放进系统提示词
运行：任务匹配某个领域 → load_skill(name) → 使用完整指引
```

这样既保持初始上下文短小，也能提供专业工作流。

## Skill 文件

在仓库根目录创建，例如 `skills/release/SKILL.md`：

```md
---
name: release
description: Prepare and verify a Python release.
---

# Release guide

Run tests, update the version, then summarize the changes.
```

`SkillLoader` 在 `scan()` 时只读取 frontmatter；正文只有在调用 `load_skill("release")` 后才进入上下文。

## DeepSeek 实现

本教程使用 DeepSeek 的 OpenAI 兼容客户端，默认模型为 `deepseek-v4-flash`：

```python
client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
```

加载后的内容和其他工具结果一样，追加到同一段对话：

```python
messages.append({
    "role": "tool",
    "tool_call_id": tool_call.id,
    "content": output,
})
```

## 试一试

在仓库根目录运行：

```sh
mkdir -p skills/release
# 按上方示例创建 skills/release/SKILL.md
python s07_skill_loading/code.py
```

然后输入：`Use the release skill to explain how you would prepare this project for release.`

Agent 应该先调用 `load_skill`，再依据加载的指引回答。

## 相比 s06 增加了什么？

| 部分 | s06 | s07 |
|---|---|---|
| 扩展方式 | 委派给新 Agent | 为同一 Agent 提供可选知识 |
| 启动上下文 | 固定系统提示词 | 精简的 skill 目录 |
| 按需动作 | `task(prompt)` | `load_skill(name)` |
| 主要收益 | 为子任务隔离上下文 | 不加载无关指令 |

教程结构和讲解顺序参考 [learn-claude-code](https://github.com/lyq1119/learn-claude-code)，可运行 API 已替换为 DeepSeek。
