"""structlog 기반 로깅 설정.

- stderr 로 사람이 읽는 형식
- 감사 로그는 별도 파일로 분리 (:func:`get_audit_logger`)
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog

from macrobania.config import get_settings

_configured = False


def configure_logging(level: str | None = None) -> None:
    """전역 로깅 초기화.

    두 번째 호출부터는 idempotent — 최초 한 번만 실제 설정.
    """
    global _configured
    if _configured:
        return

    settings = get_settings()
    log_level = (level or settings.log_level).upper()

    logging.basicConfig(
        stream=sys.stderr,
        level=log_level,
        format="%(message)s",
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=False),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None) -> Any:
    """모듈 로거."""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)


# --- 감사 로그 ---


def _audit_file_handler(path: Path) -> logging.Handler:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


_audit_logger: logging.Logger | None = None


def get_audit_logger() -> logging.Logger:
    """입력 주입/재생 이벤트 전용 감사 로거.

    DB 감사 테이블과 이중 기록하여 검증 가능성 확보.
    """
    global _audit_logger
    if _audit_logger is not None:
        return _audit_logger

    settings = get_settings()
    settings.ensure_dirs()
    logger = logging.getLogger("macrobania.audit")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        logger.addHandler(_audit_file_handler(settings.audit_log_path))
    _audit_logger = logger
    return logger


def reset_logging() -> None:
    """테스트용."""
    global _configured, _audit_logger
    _configured = False
    _audit_logger = None
