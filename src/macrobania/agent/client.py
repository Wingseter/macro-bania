"""OpenAI 호환 VLM 엔드포인트 클라이언트.

Ollama(``/v1``), vLLM, SGLang 모두 호환. 이미지는 base64 data URL로 인코딩.
"""
from __future__ import annotations

import base64
import io
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from PIL import Image

from macrobania.config import VLMSettings, get_settings
from macrobania.logging import get_logger

log = get_logger(__name__)


def encode_image(image: Image.Image | bytes, fmt: str = "PNG") -> str:
    """PIL 이미지/바이트 → base64 data URL."""
    if isinstance(image, Image.Image):
        buf = io.BytesIO()
        image.save(buf, format=fmt)
        raw = buf.getvalue()
        mime = f"image/{fmt.lower()}"
    else:
        raw = image
        mime = f"image/{fmt.lower()}"
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_BARE_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """모델 응답에서 JSON 객체를 뽑는다.

    - 코드펜스 ```json ... ``` 우선
    - 없으면 가장 바깥 ``{...}`` 매치
    """
    m = _JSON_BLOCK_RE.search(text)
    if m:
        return _safe_load(m.group(1))
    m = _BARE_JSON_RE.search(text)
    if m:
        return _safe_load(m.group(0))
    raise ValueError(f"JSON not found in response: {text[:200]!r}")


def _safe_load(raw: str) -> dict[str, Any]:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse failed: {e}; raw={raw[:200]!r}") from e
    if not isinstance(obj, dict):
        raise ValueError(f"Expected JSON object, got {type(obj).__name__}")
    return obj


@dataclass
class VLMClient:
    """얇은 VLM 호출 래퍼.

    OpenAI Python SDK에 OpenAI-호환 엔드포인트를 물려 쓴다.
    """

    settings: VLMSettings

    def __post_init__(self) -> None:
        self._client = OpenAI(
            base_url=str(self.settings.base_url),
            api_key=self.settings.api_key,
            timeout=self.settings.request_timeout_s,
            max_retries=self.settings.max_retries,
        )

    @classmethod
    def from_env(cls) -> VLMClient:
        return cls(settings=get_settings().vlm)

    # --- primitives ---

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 512,
        temperature: float = 0.0,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """채팅 호출 → 첫 choice의 message.content 문자열 반환."""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        log.debug("vlm.chat", model=model, msg_count=len(messages))
        resp = self._client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""
        return content

    def chat_vision(
        self,
        *,
        model: str,
        system: str,
        user_text: str,
        images: Iterable[Image.Image | bytes],
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> str:
        """시스템+(이미지 여러장)+텍스트 원샷 호출."""
        user_content: list[dict[str, Any]] = []
        for img in images:
            user_content.append(
                {"type": "image_url", "image_url": {"url": encode_image(img)}}
            )
        user_content.append({"type": "text", "text": user_text})
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]
        return self.chat(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def ping(self) -> bool:
        """엔드포인트 가용 체크 (models 리스트 호출)."""
        try:
            self._client.models.list()
            return True
        except Exception as e:
            log.warning("vlm.ping_failed", error=str(e))
            return False
