"""
模型适配器 — 统一接口调用不同的 LLM API。

每个适配器只需实现一个方法:
    def call(self, system: str, user: str) -> str

支持:
  - AnthropicModel:        /v1/messages (Claude 系列)
  - ResponsesModel:        /v1/responses (OpenAI Responses API, GPT-5 系列)
  - ChatCompletionsModel:  /v1/chat/completions (通用 OpenAI Chat API)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx


class BaseModel(ABC):
    """模型调用的抽象基类"""

    def __init__(self, base_url: str, model: str, timeout: float = 180.0,
                 extra_headers: dict[str, str] | None = None,
                 extra_params: dict[str, Any] | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self.extra_params = extra_params or {}

    @abstractmethod
    def call(self, system: str, user: str) -> str:
        """发送一次请求，返回模型的文本输出"""
        ...

    def _make_client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model!r})"


# ─── Anthropic Messages API ──────────────────────────────────────────────────

class AnthropicModel(BaseModel):
    """Claude 系列 — Anthropic /v1/messages"""

    def __init__(self, base_url: str = "http://127.0.0.1:18080",
                 model: str = "claude-opus-4.6",
                 api_key: str = "unused",
                 max_tokens: int = 8192,
                 **kwargs):
        super().__init__(base_url, model, **kwargs)
        self.api_key = api_key
        self.max_tokens = max_tokens

    def call(self, system: str, user: str) -> str:
        with self._make_client() as c:
            resp = c.post("/v1/messages", json={
                "model": self.model,
                "max_tokens": self.max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
                **self.extra_params,
            }, headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                **self.extra_headers,
            })
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]


# ─── OpenAI Responses API ────────────────────────────────────────────────────

class ResponsesModel(BaseModel):
    """GPT-5 系列 — OpenAI /v1/responses"""

    def __init__(self, base_url: str = "http://127.0.0.1:18080",
                 model: str = "gpt-5-mini",
                 **kwargs):
        super().__init__(base_url, model, **kwargs)

    def call(self, system: str, user: str) -> str:
        # Responses API 用 instructions + input
        with self._make_client() as c:
            resp = c.post("/v1/responses", json={
                "model": self.model,
                "instructions": system,
                "input": user,
                "stream": False,
                **self.extra_params,
            })
            resp.raise_for_status()
            data = resp.json()
            # 从 output 数组中提取文本
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for part in item.get("content", []):
                        if part.get("type") == "output_text":
                            return part["text"]
            if data.get("output_text"):
                return data["output_text"]
            return str(data)


# ─── OpenAI Chat Completions API ─────────────────────────────────────────────

class ChatCompletionsModel(BaseModel):
    """通用 /v1/chat/completions (OpenAI, vLLM, Ollama, LiteLLM 等)"""

    def __init__(self, base_url: str = "http://127.0.0.1:11434/v1",
                 model: str = "llama3",
                 api_key: str = "unused",
                 **kwargs):
        super().__init__(base_url, model, **kwargs)
        self.api_key = api_key

    def call(self, system: str, user: str) -> str:
        with self._make_client() as c:
            resp = c.post("/chat/completions", json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                **self.extra_params,
            }, headers={
                "Authorization": f"Bearer {self.api_key}",
                **self.extra_headers,
            })
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
