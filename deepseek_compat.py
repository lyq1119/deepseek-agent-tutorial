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
                if message.get("role") == "user":
                    for block in content:
                        if block.get("type") == "tool_result":
                            converted.append({"role": "tool", "tool_call_id": block["tool_use_id"],
                                              "content": str(block.get("content", ""))})
                else:
                    converted.append({"role": message["role"], "content": str(content)})
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
