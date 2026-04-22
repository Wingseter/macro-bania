"""P0 Spike — 스크린샷 한 장에서 target grounding.

사전 조건:
  1. Ollama 설치 & 실행: https://ollama.com/download
  2. 모델 pull:  ollama pull qwen3-vl:2b
  3. 의존성:     uv sync --extra capture   (mss가 필요)

사용:
  python scripts/spike_grounding.py --image screenshot.png \\
      --target "로그인 버튼"

  # 또는 스크린 캡처(mss 사용, 전체 화면):
  python scripts/spike_grounding.py --capture --target "시작 메뉴"

  # 결과 시각화:
  python scripts/spike_grounding.py --capture --target "주소창" --draw out.png

KPI (PLAN.md Phase 0):
  - 응답 지연 < 1.5 s
  - 체감 정확도 ≥ 80% (Chrome/VSCode/설정창에서 눈대중)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

from macrobania.agent.client import VLMClient
from macrobania.agent.grounder import Grounder
from macrobania.config import get_settings
from macrobania.logging import configure_logging, get_logger
from macrobania.models import PixelBBox

log = get_logger(__name__)


def grab_screenshot() -> Image.Image:
    """mss로 전체 화면 캡처. DXcam은 P1에서 정식 도입."""
    try:
        import mss  # type: ignore[import-untyped]
    except ImportError as e:
        raise SystemExit(
            "mss가 설치되지 않았습니다. `uv sync --extra capture` 또는 "
            "`pip install mss` 후 다시 시도하세요."
        ) from e
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def draw_bbox(image: Image.Image, bbox: PixelBBox, label: str = "") -> Image.Image:
    out = image.copy()
    draw = ImageDraw.Draw(out)
    draw.rectangle([bbox.x1, bbox.y1, bbox.x2, bbox.y2], outline="red", width=4)
    cx, cy = bbox.center
    draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill="red")
    if label:
        draw.text((bbox.x1 + 4, max(0, bbox.y1 - 16)), label, fill="red")
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="P0 grounding spike")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", type=Path, help="스크린샷 이미지 경로")
    src.add_argument("--capture", action="store_true", help="현재 화면 캡처")
    p.add_argument("--target", required=True, help="찾을 대상 서술 (예: '로그인 버튼')")
    p.add_argument("--model", default=None, help="Grounder 모델 override")
    p.add_argument("--draw", type=Path, default=None, help="bbox 시각화 저장 경로")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(level="DEBUG" if args.verbose else "INFO")

    if args.capture:
        log.info("spike.capture_screen")
        image = grab_screenshot()
    else:
        image = Image.open(args.image).convert("RGB")

    settings = get_settings()
    client = VLMClient.from_env()

    log.info(
        "spike.start",
        model=args.model or settings.vlm.grounder_model,
        endpoint=str(settings.vlm.base_url),
        resolution=image.size,
        target=args.target,
    )

    if not client.ping():
        log.warning(
            "spike.endpoint_unreachable",
            endpoint=str(settings.vlm.base_url),
            hint="Ollama 서버가 실행 중인가? `ollama serve`",
        )
        return 2

    grounder = Grounder(client=client, model=args.model)

    t0 = time.monotonic()
    result = grounder.locate(screenshot=image, target_description=args.target)
    dt = time.monotonic() - t0

    pixel = PixelBBox.from_norm(result.bbox, *image.size)
    log.info(
        "spike.result",
        latency_ms=round(dt * 1000, 1),
        norm=[result.bbox.x1, result.bbox.y1, result.bbox.x2, result.bbox.y2],
        pixel=[pixel.x1, pixel.y1, pixel.x2, pixel.y2],
        center=pixel.center,
        confidence=result.confidence,
        reason=result.reason,
    )

    print(
        f"\n[target] {args.target}\n"
        f"[norm  ] {result.bbox.x1},{result.bbox.y1},{result.bbox.x2},{result.bbox.y2}\n"
        f"[pixel ] {pixel.x1},{pixel.y1},{pixel.x2},{pixel.y2}  "
        f"(w={pixel.width},h={pixel.height})\n"
        f"[center] {pixel.center}\n"
        f"[conf  ] {result.confidence:.2f}\n"
        f"[reason] {result.reason}\n"
        f"[time  ] {dt * 1000:.0f} ms "
        f"({'PASS' if dt < 1.5 else 'SLOW'} vs 1500ms target)"
    )

    if args.draw is not None:
        out = draw_bbox(image, pixel, label=args.target)
        args.draw.parent.mkdir(parents=True, exist_ok=True)
        out.save(args.draw)
        print(f"[saved ] {args.draw}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
