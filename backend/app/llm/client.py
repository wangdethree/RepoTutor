from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings


@dataclass
class LLMResponse:
    content: str
    raw: dict[str, Any] | None = None


class LLMClient:
    """OpenAI 兼容接口封装；未配置 API Key 时返回清晰错误。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self.temperature = settings.llm_temperature

    async def complete_json(self, messages: list[dict[str, str]]) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("未配置 LLM_API_KEY，当前可使用确定性课程与测验生成")
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("openai 依赖未安装") from exc

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return LLMResponse(content=content, raw=response.model_dump())

