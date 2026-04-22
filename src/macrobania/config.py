"""전역 설정.

기본 소스 순서(pydantic-settings):
  1) 인스턴스 생성 시 전달된 kwargs
  2) 환경변수 (prefix = ``MACROBANIA_``)
  3) ``.env`` 파일
  4) 하드코딩 기본값

사용자 데이터 경로 기본값은 Windows 기준 ``%APPDATA%/macrobania``.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    """플랫폼별 기본 사용자 데이터 디렉토리."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "macrobania"
    # Linux/macOS 폴백 — 현재 V1은 Windows만 공식 지원
    return Path.home() / ".macrobania"


HardwareTier = Literal["mini", "standard", "pro", "workstation"]


class VLMSettings(BaseSettings):
    """VLM 서버 설정. OpenAI 호환 엔드포인트."""

    model_config = SettingsConfigDict(env_prefix="MACROBANIA_VLM_", extra="ignore")

    base_url: HttpUrl = Field(
        default="http://localhost:11434/v1",  # type: ignore[arg-type]
        description="Ollama 기본, vLLM 등 OpenAI 호환 서버",
    )
    api_key: str = Field(
        default="ollama",
        description="Ollama는 키 불필요. OpenAI 호환 서버 호환성 위해 더미 허용",
    )
    grounder_model: str = Field(default="qwen3-vl:2b")
    captioner_model: str = Field(default="qwen3.5:0.8b")
    planner_model: str = Field(default="qwen3-vl:8b")
    verifier_model: str = Field(default="qwen3-vl:2b")

    request_timeout_s: float = 30.0
    max_retries: int = 2


class SafetySettings(BaseSettings):
    """안전/프라이버시 관련 스위치. 기본값은 보수적."""

    model_config = SettingsConfigDict(env_prefix="MACROBANIA_SAFETY_", extra="ignore")

    dry_run_default: bool = True
    pii_scrub_enabled: bool = True
    require_process_allowlist: bool = True
    irreversible_action_confirm: bool = True
    kill_switch_hotkey: str = "ctrl+shift+esc"
    failsafe_corner: bool = True  # pyautogui.FAILSAFE


class Settings(BaseSettings):
    """애플리케이션 전역 설정."""

    model_config = SettingsConfigDict(
        env_prefix="MACROBANIA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Field(default_factory=_default_data_dir)
    hardware_tier: HardwareTier = "standard"
    log_level: str = "INFO"
    audit_log_enabled: bool = True

    vlm: VLMSettings = Field(default_factory=VLMSettings)  # type: ignore[arg-type]
    safety: SafetySettings = Field(default_factory=SafetySettings)  # type: ignore[arg-type]

    # 파생 경로
    @property
    def recordings_dir(self) -> Path:
        return self.data_dir / "recordings"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "macrobania.sqlite"

    @property
    def audit_log_path(self) -> Path:
        return self.data_dir / "audit.log"

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.recordings_dir, self.models_dir):
            p.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    """전역 설정 singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """테스트용 리셋."""
    global _settings
    _settings = None
