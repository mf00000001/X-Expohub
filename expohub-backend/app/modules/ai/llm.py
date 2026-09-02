"""
LLM 网关（P5）

- LLMProvider 抽象：统一 complete(prompt, capability) -> (text)
- MockProvider：无 key / 未配置时的确定性降级（fail-soft）
- OpenAICompatProvider：通用 OpenAI 兼容 /chat/completions
  DeepSeek / SiliconFlow 只是不同 base_url + key 的实例
- get_llm_provider()：按 settings.AI_PROVIDER 选型；缺 key 自动降级 mock
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def complete(self, prompt: str, capability: str = "generic") -> str:
        """同步调用 LLM，返回文本；失败抛异常（由网关决定是否降级）"""


class MockLLMProvider(LLMProvider):
    """确定性 Mock：演示/联调/无 key 降级"""
    name = "mock"

    def complete(self, prompt: str, capability: str = "generic") -> str:
        return f"【{capability}·mock】AI 服务未配置真实密钥，当前为降级模式。收到内容：{prompt[:80]}"


class OpenAICompatProvider(LLMProvider):
    """OpenAI 兼容 /chat/completions 实现（DeepSeek/SiliconFlow/自建）"""

    def __init__(self, name: str, api_key: str, base_url: str, model: str):
        self.name = name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    def complete(self, prompt: str, capability: str = "generic") -> str:
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "你是展会撮合平台 ExpoHub 的助手，回答简洁专业。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 600,
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        resp = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"LLM 响应格式异常: {exc}") from exc


def _build_real_provider() -> Optional[LLMProvider]:
    """按配置构造真实渠道；缺 key 返回 None（触发 mock 降级）"""
    p = (settings.AI_PROVIDER or "mock").lower()
    if p == "deepseek":
        if settings.DEEPSEEK_API_KEY:
            return OpenAICompatProvider("deepseek", settings.DEEPSEEK_API_KEY,
                                        settings.DEEPSEEK_BASE_URL, settings.AI_MODEL)
    elif p == "siliconflow":
        if settings.SILICONFLOW_API_KEY:
            return OpenAICompatProvider("siliconflow", settings.SILICONFLOW_API_KEY,
                                        settings.SILICONFLOW_BASE_URL, settings.AI_MODEL)
    elif p == "openai-compat":
        if settings.OPENAI_COMPAT_API_KEY and settings.OPENAI_COMPAT_BASE_URL:
            return OpenAICompatProvider("openai-compat", settings.OPENAI_COMPAT_API_KEY,
                                        settings.OPENAI_COMPAT_BASE_URL, settings.AI_MODEL)
    return None


class LLMGateway:
    """网关：真实渠道失败时自动降级 mock（fail-soft），并报告 degraded"""

    def complete(self, prompt: str, capability: str = "generic") -> dict:
        provider = _build_real_provider()
        if provider is None:
            mock = MockLLMProvider()
            return {"provider": mock.name, "content": mock.complete(prompt, capability), "degraded": True}
        try:
            return {"provider": provider.name, "content": provider.complete(prompt, capability), "degraded": False}
        except Exception as exc:  # 网络/鉴权/限流等一律降级，不让 AI 阻断业务
            logger.warning("[ai] provider %s failed(%s), fallback to mock", provider.name, exc)
            mock = MockLLMProvider()
            return {"provider": mock.name, "content": mock.complete(prompt, capability), "degraded": True}


gateway = LLMGateway()

# 能力注册点：后续新增 AI 能力只需在此登记
AI_CAPABILITIES = {"reason", "copy", "qa", "generic"}
