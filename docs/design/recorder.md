# Phase 1 Recorder 설계

> 상태: 초안 (2026-04-22). 구현은 P0 Spike 성공 후 착수.
> 관련: [PLAN.md §11](../../PLAN.md), [ADR-0001](../adr/0001-three-ai-synthesis.md)

## 목표

1. 1시간 연속 녹화 중 크래시 0, 프레임 드롭 < 1%
2. 이벤트/프레임/UIA 트리/OCR 결과를 시간 정렬하여 SQLite + 파일시스템에 저장
3. 사용자 작업에 체감 영향 없음 (녹화 중 VLM 호출 금지)

## 컴포넌트

```
┌─────────────────┐      ┌──────────────────┐
│ CaptureBackend  │──┐   │ InputListener    │
│ (DXcam/MSS)     │  │   │ (pynput)         │
└─────────────────┘  │   └──────────────────┘
        ▼            │            ▼
┌──────────────────┐ │   ┌──────────────────┐
│ FrameQueue       │ │   │ EventQueue       │
│ (ring buffer)    │ │   │ (ring buffer)    │
└──────────────────┘ │   └──────────────────┘
        │            │            │
        └────────────┴────────────┘
                     ▼
             ┌──────────────────┐
             │ Recorder         │
             │ - 시간 정렬       │
             │ - diff 판별       │
             │ - PII scrub       │
             │ - UIA snapshot    │
             │ - OCR snapshot    │
             │ - SQLite write    │
             └──────────────────┘
```

## 스레드/동시성

- Capture는 DXcam 자체 worker 스레드 → `FrameQueue` (maxsize ~120, 4s 버퍼)
- Input listener는 pynput의 hook 스레드 → `EventQueue`
- Writer는 async 태스크 (asyncio) — DB 접근 직렬화
- 종료 시 drain 후 마지막 keyframe 강제

## 데이터 흐름 결정

| 항목 | 규칙 |
|---|---|
| Frame 저장 | 이전 대비 pixel diff ≥ 2% 또는 5초 간격 keyframe |
| UIA snapshot | 입력 이벤트 발생 ±300ms 내에 hwnd 포커스 기준으로만 채취 |
| OCR snapshot | UIA와 동일 타이밍. 비용 큼 → 설정으로 OFF 가능 |
| Text input | 키다운 시퀀스를 IME-aware로 조합 후 저장. 저장 전에 PII scrub |
| 타임스탬프 | ``time.monotonic_ns()`` (단조 증가), 실시간 wall clock은 메타데이터에만 |

## 위험 & 완화

- **UIA가 Unity/Unreal 게임에서 동작 안 함**: 감지 시 UIA skip, frame + OCR만 저장
- **Raw Input 과다 → 이벤트 손실**: PH3 blog 권고대로 배치 flush, N=32 단위
- **디스크 폭증**: diff-only + WebP + 옵션으로 해상도 다운샘플
- **HiDPI / 멀티 모니터**: `Platform.dpi_scale`에 기록, 재생 시 변환

## 인터페이스 초안

```python
# src/macrobania/recording/session.py
class RecordingSession:
    def __init__(self, *, task_name: str, capture: CaptureBackend, ...): ...
    def start(self) -> None: ...
    def stop(self) -> Recording: ...
    async def _loop(self) -> None: ...

# src/macrobania/recording/builder.py
async def build_steps(rec: Recording, captioner: Captioner) -> list[Step]: ...
```

## KPI 검증 (P1 완료 조건)

- ▢ 1시간 Chrome+엑셀 녹화 무크래시
- ▢ 평균 이벤트 드롭율 < 0.1%
- ▢ 디스크 사용량 < 500 MB/h (FHD 기준 기대치)
- ▢ `macrobania inspect` 로 JSON 덤프 확인 가능
- ▢ PII 스크럽이 카드번호/이메일/RRN 샘플 100% 마스킹

## 오픈 이슈

1. DXcam이 DPI scale > 100%에서 좌표 오프셋을 주는지 재검증 필요
2. `text_input` IME 조합 규칙 (한글) — Phase 1 스파이크 소항목으로 분리
3. 키프레임 trigger를 시간 고정 vs 변화량 기반으로 선택 (현재 둘 다)
