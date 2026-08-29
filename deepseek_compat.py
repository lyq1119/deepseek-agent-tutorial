"""Small Anthropic-message facade backed by DeepSeek's OpenAI-compatible API."""
import json
import os
from types import SimpleNamespace

from openai import OpenAI


class DeepSeekMessages:
    def __init__(self, client):
        self.client = client

    def create(self, *, model, messages, system=None, tools=None, max_tokens=8000):
        converted = []
        if system:
            converted.append({"role": "system", "content": system})
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, list):
                role = message.get("role")
                if role == "assistant":
                    text = []
                    tool_calls = []
                    for block in content:
                        block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                        if block_type == "text":
                            text.append(block.get("text", "") if isinstance(block, dict) else getattr(block, "text", ""))
                        elif block_type == "tool_use":
                            name = block.get("name", "") if isinstance(block, dict) else getattr(block, "name", "")
                            tool_input = block.get("input", {}) if isinstance(block, dict) else getattr(block, "input", {})
                            tool_id = block.get("id", "") if isinstance(block, dict) else getattr(block, "id", "")
                            tool_calls.append({"id": tool_id, "type": "function", "function": {
                                "name": name, "arguments": json.dumps(tool_input, ensure_ascii=False)}})
                    converted.append({"role": "assistant", "content": "\n".join(text) or None,
                                      **({"tool_calls": tool_calls} if tool_calls else {})})
                elif role == "user":
                    text = []
                    for block in content:
                        block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                        if block_type == "tool_result":
                            tool_id = block.get("tool_use_id", "") if isinstance(block, dict) else getattr(block, "tool_use_id", "")
                            result = block.get("content", "") if isinstance(block, dict) else getattr(block, "content", "")
                            converted.append({"role": "tool", "tool_call_id": tool_id,
                                              "content": str(result)})
                        elif block_type == "text":
                            text.append(block.get("text", "") if isinstance(block, dict) else getattr(block, "text", ""))
                    if text:
                        converted.append({"role": "user", "content": "\n".join(text)})
                else:
                    converted.append({"role": role, "content": str(content)})
            else:
                converted.append({"role": message["role"], "content": content})
        openai_tools = [{"type": "function", "function": {"name": item["name"],
                         "description": item.get("description", ""),
                         "parameters": item["input_schema"]}} for item in (tools or [])]
        reply = self.client.chat.completions.create(model=model, messages=converted,
                                                    tools=openai_tools or None, max_tokens=max_tokens)
        message = reply.choices[0].message
        blocks = []
        if message.content:
            blocks.append(SimpleNamespace(type="text", text=message.content))
        for call in message.tool_calls or []:
            try:
                value = json.loads(call.function.arguments)
            except json.JSONDecodeError:
                value = {}
            blocks.append(SimpleNamespace(type="tool_use", id=call.id,
                                          name=call.function.name, input=value))
        return SimpleNamespace(content=blocks,
                               stop_reason="tool_use" if message.tool_calls else "end_turn")


class DeepSeekClient:
    def __init__(self):
        self._client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                              base_url="https://api.deepseek.com")
        self.messages = DeepSeekMessages(self._client)
