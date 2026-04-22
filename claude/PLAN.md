# macro-bania — Context-Aware Macro via Vision-Language Agents

> 작성일: 2026-04-22
> 상태: 초안 (v0.1) — 구현 전 합의용
> 대상 독자: 프로젝트 개발자, 리뷰어

---

## 0. 한 줄 요약

**"녹화한 화면+입력을 VLM이 의도(semantic action)로 추상화해두고, 재생 시 VLM이 현재 화면 맥락에 맞춰 다시 좌표를 찾아 동작하는 차세대 매크로."** 전부 로컬 소비자 GPU에서 동작.

---

## 1. 왜 지금인가

| 기존 매크로 | macro-bania |
|---|---|
| 고정 좌표 / 고정 키 이벤트 | "Login 버튼 찾아 클릭"을 매 실행마다 화면에서 재탐색 |
| 창 위치 바뀌면 깨짐 | 창 이동·크기·DPI 변경에도 동작 |
| UI 변경 시 스크립트 재작성 | VLM이 의미 기반으로 재해석 |
| 비전 API에 의존 시 고가·프라이버시 문제 | 로컬 오픈소스 VLM (Qwen3-VL, UI-TARS 계열) |

2026년 현재 핵심 동인:
- **Qwen3.5 Small Series (0.8B/2B/4B)**와 **Qwen3-VL Dense (2B/4B/8B)**가 소비자 GPU에서 양자화 실행 가능 (RTX 4060 이상)
- GUI 전용 VLA가 산재: UI-TARS-1.5-7B, OS-Atlas, UI-Venus-1.5-2B, GUI-Actor, Fara-7B(Microsoft), OpenCUA
- DXGI Desktop Duplication 기반 캡처가 240 FPS까지 가능 (DXcam) — 캡처 병목은 사실상 없음
- `llama.cpp`, `vLLM`, `SGLang`, `Ollama`가 Qwen3-VL을 1등 시민으로 지원

---

## 2. 스코프와 비(非)스코프

### 스코프 (V1)
- Windows 10/11 호스트 데스크톱
- 단일 사용자·단일 머신 실행 (SaaS 아님)
- 로컬 모델 오프라인 실행 (선택적으로 OpenAI 호환 원격 엔드포인트)
- 녹화 → 후처리 → 재생 사이클
- 오프라인/캐주얼 시나리오: 웹 브라우저 기반 단순 퀘스트, 업무 반복 작업, Steam 싱글게임 메뉴 루프, 샌드박스 개발 테스트

### 비(非)스코프 (V1에서 제외, 명시적으로 지원하지 않음)
- **커널 안티치트(Riot Vanguard/BattlEye/EAC)가 탑재된 경쟁 온라인 게임** — 기술적으로 탐지되고 ToS 위반
- 실시간 전투/FPS 에임 (2-8초 VLM 루프로 불가능)
- 모바일 OS 제어 (ADB/XCTest 연동은 Phase 8+)
- 클라우드 멀티테넌시, SaaS, 팀 협업

### 도덕적/법적 가드레일
- "게임 일일퀘스트 자동화"는 타이틀별 ToS 검증 후 개인 책임으로 사용
- 기본값은 **Dry Run + 사용자 확인**. 자동 실행은 명시적 opt-in
- PII 스크러버 기본 활성화 (카드번호/이메일/주민번호 패턴)

---

## 3. 제약 조건과 설계 원칙

### 하드웨어 프로필 (타깃 매트릭스)
| 프로필 | GPU | VRAM | 기본 모델 구성 | 기대 속도 |
|---|---|---|---|---|
| **Mini** | RTX 3060 / 4060 | 8 GB | Qwen3-VL-2B (Q4) 단일 | 스텝당 1.5–3 s |
| **Standard** | RTX 4070 / 4070S | 12 GB | Qwen3-VL-8B (Q4) 단일 | 스텝당 1–2 s |
| **Pro** | RTX 4080 / 4090 | 16–24 GB | Planner(Qwen3-VL-8B) + Grounder(UI-Venus-2B) 동시 | 스텝당 0.5–1.5 s |
| **Workstation** | A6000 / 2x 4090 | 48 GB+ | Qwen3-VL-30B-A3B MoE | 스텝당 0.3–1 s |

### 설계 원칙
1. **Local-first**: 기본적으로 전량 오프라인. 외부 API 호출은 opt-in.
2. **Tiered intelligence**: 빠른 Grounder를 타이트 루프에, 비싼 Planner는 드물게.
3. **Fail-safe by default**: Dry run 기본, 사용자 확인, 실패 시 즉시 정지.
4. **Data-owned**: 모든 녹화 데이터는 `%APPDATA%/macrobania`(또는 설정된 디렉토리) 아래 SQLite+파일로 로컬.
5. **Minimum glue**: LangChain/LlamaIndex 같은 거대 프레임워크 지양. OpenAI-호환 SDK 얇은 래퍼.

---

## 4. 기술 스택

| 레이어 | 선택 | 근거 |
|---|---|---|
| 언어 | Python 3.11+ | VLM SDK/캡처/입력 라이브러리 생태계 |
| 화면 캡처 | `DXcam` (DXGI) 기본, `windows-capture` (Rust) 폴백 | 240 FPS 벤치, Python 연동 용이 |
| 입력 리스너 | `pynput` + Win32 Raw Input (ctypes) | Scan code 보존 |
| 입력 주입 | `pydirectinput`(Scan code `SendInput`), 필요 시 ctypes 원시 호출 | DirectInput 게임 호환 |
| VLM 서버 | `Ollama` (개발·배포 편의) / `vLLM` (성능) | Qwen3-VL 1등 지원 |
| VLM 클라이언트 | `openai` SDK + OpenAI-호환 엔드포인트 | Ollama/vLLM 공통 |
| 저장소 | SQLite (메타데이터) + 파일시스템 (이미지·WebP) | 임베디드, 백업 용이 |
| UI | PySide6 (v1), Tauri+React (v2 검토) | Python 통일, Qt 성숙 |
| 패키징 | `uv` + `hatch` + `pyinstaller` (배포) | 현대적 빌드 |
| 관측 | 구조화 로그(`structlog`) + SQLite 이벤트 테이블 | 외부 서비스 의존 X |

---

## 5. 모델 전략 (중요)

### 5.1 사용자가 제안한 "Qwen3.5-0.8B"에 대한 평가

**결론: 단독 사용은 부적합. 보조 역할(Captioner)로 채용.**

| 항목 | Qwen3.5-0.8B | Qwen3-VL-2B | UI-Venus-1.5-2B | Qwen3-VL-8B | UI-TARS-1.5-7B |
|---|---|---|---|---|---|
| VRAM (Q4) | ~2 GB | ~4 GB | ~4 GB | ~8 GB | ~8 GB |
| 시각 추론 | 기본 (OCR/설명) | 강 (Visual Agent 전용 학습) | 매우 강 (GUI 전용) | 매우 강 | SOTA |
| GUI grounding | 미검증 (저조 예상) | 0-1000 bbox, 학습됨 | ScreenSpot-Pro 58.8% | ScreenSpot-Pro 67.7% | ScreenSpot 91.6% |
| 속도 (RTX 4070) | 매우 빠름 | 빠름 | 빠름 | 보통 | 보통 |
| 컨텍스트 | 262K | 256K (→1M) | 동일 | 동일 | 128K |
| 용도 제안 | **Captioner** | **경량 Grounder** | **정밀 Grounder** | **Planner** | **통합 Agent(단일 모델 모드)** |

**공식 권장 조합 (프로필별)**:
- **Mini 프로필**: Qwen3-VL-2B 단일 (Grounder + Planner 겸용, 성능 낮지만 저비용)
- **Standard 프로필**: Qwen3-VL-8B 단일 또는 UI-TARS-1.5-7B 단일
- **Pro 프로필**: Qwen3-VL-8B (Planner) + UI-Venus-1.5-2B (Grounder) + Qwen3.5-0.8B (후처리 Captioner)

사용자가 여전히 Qwen3.5-0.8B만 고집할 경우: "녹화 데이터 자동 캡션 + 간단한 의도 요약" 역할로만 쓰고, 실제 클릭 결정은 더 큰 모델에게 맡기는 hybrid를 기본값으로 제공.

### 5.2 역할별 책임

```
┌────────────────────────────────────────────────────┐
│  Planner (Qwen3-VL-8B)                             │
│  - 새 상황에서 전체 전략 결정                       │
│  - 현재 상태 → 다음 스텝 서술 (자연어)              │
│  - 호출 빈도: 낮음 (1스텝/5–30초, 필요 시만)        │
├────────────────────────────────────────────────────┤
│  Grounder (UI-Venus-2B / Qwen3-VL-2B)              │
│  - "Login 버튼" + 스크린샷 → [x,y,w,h]             │
│  - 호출 빈도: 높음 (매 스텝)                        │
├────────────────────────────────────────────────────┤
│  Verifier (Grounder 재사용)                        │
│  - postcondition 체크 (yes/no + 근거)              │
├────────────────────────────────────────────────────┤
│  Captioner (Qwen3.5-0.8B)                          │
│  - 녹화 후처리: raw event → semantic step          │
│  - 오프라인 배치, 사용자 대기 X                     │
└────────────────────────────────────────────────────┘
```

---

## 6. 시스템 아키텍처

```
┌────────────────────────────────────────────────────────────┐
│                     PySide6 UI                              │
│   Library │ Record │ Process │ Play │ Editor │ Logs         │
└────────────────────────────────────────────────────────────┘
                           │  (asyncio / Qt signals)
┌────────────────────────────────────────────────────────────┐
│                      Orchestrator                           │
│      FSM: idle → record → processing → play → paused        │
└────────────────────────────────────────────────────────────┘
     │            │             │              │
┌─────────┐  ┌──────────┐  ┌────────────┐  ┌─────────────┐
│Capture  │  │ Input    │  │  Storage   │  │  VLM        │
│Service  │  │ I/O      │  │  SQLite +  │  │  Server     │
│         │  │ Listener │  │  Frames    │  │  (Ollama /  │
│DXcam/WGC│  │ Injector │  │            │  │   vLLM)     │
└─────────┘  └──────────┘  └────────────┘  └─────────────┘
                                                  │
                                    ┌─────────────┴──────────────┐
                                    │      Agent Core             │
                                    │  Planner │ Grounder │       │
                                    │  Verifier │ Captioner       │
                                    └─────────────────────────────┘
```

### 패키지 구조
```
macro-bania/
├── src/macrobania/
│   ├── capture/          # DXGI/WGC 래퍼, 프레임 디프
│   ├── inputio/          # listener / injector / failsafe
│   ├── agent/
│   │   ├── planner.py
│   │   ├── grounder.py
│   │   ├── captioner.py
│   │   ├── verifier.py
│   │   └── prompts/      # Jinja 프롬프트 템플릿
│   ├── recording/        # event aggregation, step builder
│   ├── player/
│   │   ├── mode_a_faithful.py
│   │   ├── mode_b_grounded.py
│   │   └── mode_c_autonomous.py
│   ├── storage/          # SQLite 스키마, 이미지 I/O
│   ├── safety/           # PII, fail-safe, allowed-process
│   ├── orchestrator.py
│   └── ui/               # PySide6
├── models/               # gguf / safetensors (git-ignored)
├── recordings/           # 사용자 데이터 (git-ignored)
├── tests/
├── pyproject.toml
└── PLAN.md
```

---

## 7. 데이터 스키마

### 7.1 Recording (상위 객체)
```json
{
  "id": "rec_2026-04-22_14-33-01",
  "task_name": "daily-quest-login",
  "description": "웹 게임 로그인 후 일일퀘스트 5개 수령",
  "created_at": "2026-04-22T14:33:01+09:00",
  "platform": {
    "os": "Windows 11 22H2",
    "resolution": [2560, 1440],
    "dpi_scale": 1.25,
    "primary_monitor": 0
  },
  "target_process": "chrome.exe",
  "target_window_title_regex": "My Game .*",
  "frame_count": 183,
  "event_count": 1241,
  "duration_ms": 92430,
  "step_count": 14
}
```

### 7.2 Event (저수준)
```json
{
  "ts_ns": 173840293410293,
  "kind": "mouse_down" | "mouse_up" | "mouse_move" | "key_down" | "key_up" | "scroll" | "text_input",
  "data": {
    "x": 1024, "y": 680,                    // mouse_*
    "button": "left",                       // mouse_*
    "vk": 65, "scan": 0x1E, "extended": 0,  // key_*
    "text": "password123",                  // text_input
    "dx": 0, "dy": -1                       // scroll
  },
  "window_hwnd": 0x000A5B2C,
  "window_title": "My Game — Chrome"
}
```

### 7.3 Frame (스크린샷 델타)
```
frames/
├── rec_xxx/
│   ├── f0000.webp     // keyframe (전체)
│   ├── f0001.webp     // delta (변경 영역만)
│   └── meta.sqlite    // (ts_ns, kind, bbox_changed, window_hwnd)
```

### 7.4 Step (의미 단위, VLM 후처리 생성)
```json
{
  "index": 3,
  "ts_start_ns": 173840293410293,
  "ts_end_ns": 173840295110293,
  "frame_before": "f0041.webp",
  "frame_after":  "f0043.webp",
  "raw_event_ids": [234, 235, 236, 237],
  "action": {
    "type": "click",
    "target_description": "'일일 퀘스트' 탭 (사이드바 상단 두 번째 아이콘)",
    "target_bbox_hint": [124, 280, 176, 332],
    "target_crop_path": "crops/step3_target.webp",
    "value": null,
    "modifiers": []
  },
  "caption": "일일 퀘스트 탭을 클릭",
  "precondition": "로비 화면이 표시되고 사이드바가 열려 있다",
  "postcondition": "오른쪽 패널에 퀘스트 목록이 나타난다",
  "confidence": 0.88
}
```

### 7.5 액션 공간 (통합)
| type | 설명 | value | 비고 |
|---|---|---|---|
| `click` | 단일 클릭 | button (left/right/middle) | bbox 중심 |
| `double_click` | 더블 클릭 | button | |
| `drag` | 드래그 | to_bbox | start→end |
| `type` | 텍스트 입력 | text | IME 고려 |
| `hotkey` | 조합키 | keys (e.g. ["ctrl","s"]) | scan code 기반 |
| `scroll` | 스크롤 | direction, amount | |
| `wait` | 대기 | ms 또는 조건 | `until` VLM 검증 |
| `focus_window` | 창 포커스 | window_regex | |
| `done` | 종료 | - | 성공/실패 |

---

## 8. Record 파이프라인

```
┌─────────────┐    ┌──────────────┐    ┌────────────────┐
│  User hits  │───▶│  Capture on  │───▶│  Event listener│
│  Record     │    │  (DXcam 30fps│    │  (pynput raw)  │
└─────────────┘    │   diff-only) │    └────────────────┘
                   └──────────────┘            │
                          │                    ▼
                          │           ┌────────────────┐
                          │           │  Ring buffer   │
                          │           │  (events, ts)  │
                          ▼           └────────────────┘
                   ┌──────────────┐            │
                   │  Frame queue │◀───────────┘
                   │  (webp)      │
                   └──────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  SQLite +    │
                   │  files       │
                   └──────────────┘
```

**원칙**:
- 녹화 중 VLM 호출 **금지** (GPU를 사용자 작업에 양보)
- 프레임 기록: 변경 영역이 임계값(default 2%) 초과할 때만 delta 저장. 5초마다 keyframe
- PII 마스킹: `text_input`은 녹화 후 즉시 정규식/ML로 스크럽 (로컬)

**후처리(Post-processing)**:
1. 이벤트를 시간창(default 1.5s)으로 클러스터링 → 후보 Step
2. 각 후보 Step에 대해 `frame_before`, `frame_after`, `raw_events` → Captioner 프롬프트
3. 대상 요소 크롭 + 자연어 서술 생성
4. 사용자가 UI에서 리뷰/편집 가능 (caption/description 수정)

---

## 9. Play 파이프라인

### Mode A — Faithful Replay
- 원본 타임스탬프대로 이벤트 재생
- 각 Step 전 VLM에 "precondition이 화면에 보입니까?" yes/no 질문
- 실패 시 최대 N초 대기 후 재시도 → 그래도 실패 시 일시정지 + 사용자 알림

### Mode B — Grounded Replay (★ 핵심 기능)
```
for step in recording.steps:
    screenshot = capture.now()
    if step.precondition:
        ok = verifier.yesno(screenshot, step.precondition)
        if not ok: wait_and_retry(); continue

    if step.action.type in (click, double_click, drag):
        # 좌표를 현재 화면에서 재탐색
        bbox = grounder.locate(
            screenshot,
            query=step.action.target_description,
            hint_bbox=step.action.target_bbox_hint
        )
        inject.click(bbox.center)
    elif step.action.type == type:
        inject.type_text(step.action.value)
    # ...

    # postcondition 검증
    new_screenshot = capture.now()
    if step.postcondition:
        ok = verifier.yesno(new_screenshot, step.postcondition)
        if not ok: escalate_to_planner(step)
```

### Mode C — Autonomous Goal
- 사용자는 task description만 제공 (녹화 없이도 가능)
- Planner가 ReAct 루프:
  ```
  Observation: <스크린샷 + OCR 요약>
  Thought: <다음 행동 추론>
  Action: <액션 JSON>
  ```
- 녹화가 있으면 RAG로 유사 Step을 Few-shot에 주입
- 속도 2-8 s/step, 성공률은 태스크 난이도에 비례

### 공통 Fail-Safe
- Hotkey `Ctrl+Esc+Esc`(double tap) 전역 중단
- 마우스 좌상단 이동 시 중단 (`pyautogui.FAILSAFE`)
- 허용 프로세스 화이트리스트 — 벗어난 창에서는 입력 차단
- 재생 속도 slider (25–200%)
- 실패 N회 연속 시 자동 정지 + 상세 로그

---

## 10. 프롬프트 설계 (초안)

### 10.1 Grounder (Qwen3-VL)
```
System:
You are a GUI grounding assistant. Given a screenshot and a target description,
return the bounding box of the exact UI element. Use 0-1000 normalized coords.
Return ONLY: {"bbox":[x1,y1,x2,y2], "confidence":0.0-1.0, "reason":"..."}

User:
[image]
Target: "일일 퀘스트 탭 (사이드바 상단 두 번째 아이콘)"
Hint (from recording): [124, 280, 176, 332] at 2560x1440
Current resolution: 1920x1080
```

### 10.2 Verifier
```
System:
Return ONLY one JSON: {"answer":"yes"|"no", "reason":"..."}

User:
[image]
Question: "오른쪽 패널에 퀘스트 목록이 나타났는가?"
```

### 10.3 Captioner (후처리)
```
System:
You generate one "semantic step" from low-level input events.
Output one JSON matching the Step schema. Be concise in Korean.

User:
[image: frame_before]
[image: frame_after]
Events (timeline):
  t=0ms   mouse_move (124,280)
  t=50ms  mouse_down left
  t=180ms mouse_up left
  window: "My Game — Chrome"
```

### 10.4 Planner (Mode C)
```
System:
You control a Windows desktop. Plan the next single action toward the goal.
Action schema: { "type": "click"|"type"|"hotkey"|"scroll"|"wait"|"done",
                 "target_description"?: str, "value"?: str, "rationale": str }

User:
Goal: "웹 게임 일일 퀘스트 5개 모두 수령 후 로그아웃"
Recent history: [step-1 clicked '로그인', step-2 typed username, ...]
[image: current screen]
```

---

## 11. 안전 / 프라이버시

- **프로세스 화이트리스트**: Play 시 활성 창이 녹화 시점의 `target_process`와 일치할 때만 입력 주입
- **Dry Run**: 실제 클릭 대신 화면에 crosshair 오버레이만 (OpenCV 창)
- **사용자 확인 게이트**: 최초 실행·장시간 미실행 후 재실행·최근 N회 실패 후 재시도 시 모달 확인
- **PII Scrubber**: `presidio-analyzer` 또는 간단한 정규식 (카드/주민/이메일/주소)
- **로컬-only 모드**: 기본값, 네트워크 호출은 opt-in (원격 VLM 엔드포인트)
- **감사 로그**: 모든 주입된 입력을 타임스탬프와 함께 SQLite에 기록 (삭제는 사용자 동의)
- **HWID/프로세스 격리 없음**: 우리는 안티치트 우회를 하지 않는다. 커널 AC 게임에는 사용 말 것 (README 경고)

---

## 12. 로드맵

| Phase | 기간 (1인 기준) | 산출물 | 성공 지표 |
|---|---|---|---|
| **P0** Spike | 1주 | Qwen3-VL-2B를 Ollama로 띄우고 스크린샷 → bbox 데모 노트북 | 단일 요청 지연 < 1.5s, bbox 정확도 체감 80% |
| **P1** Record MVP | 2-3주 | 캡처·리스너·SQLite, CLI로 녹화/정지 | 1시간 녹화 크래시 0회, 프레임 드롭 < 1% |
| **P2** Trajectory Extract | 2주 | Captioner 배치, 뷰어 | 20개 녹화에서 Step caption 수동 리뷰 정확도 ≥ 80% |
| **P3** Faithful Replay (A) | 1주 | Mode A 구현 | 노트패드 열기→쓰기→저장 20회 중 18회 |
| **P4** Grounded Replay (B) ★ | 3주 | Mode B + Verifier | 창 위치 랜덤화해도 동일 태스크 16/20 |
| **P5** UI & Editor | 2주 | PySide6 GUI, 태스크 라이브러리, 편집 | 비개발자 5명 사용성 테스트 통과 |
| **P6** Autonomous (C) | 4주+ | Mode C + RAG + 복구 | 샌드박스 웹 태스크 3/5 완주 |
| **P7** Fine-tuning (옵션) | 4주+ | 개인 태스크 LoRA | Grounder 실패율 30% → 15% |

**총 MVP (P0–P5) ≈ 3–4개월**, P6+는 연구 성격.

---

## 13. KPI 대시보드

| 카테고리 | 지표 | 목표 (v1.0) |
|---|---|---|
| 녹화 품질 | 프레임 드롭율 | < 1% |
| 녹화 품질 | PII 미스 | < 0.1% |
| 후처리 | Step caption 정확도 | ≥ 85% |
| 재생 성공률 | Mode A 단순 업무 | ≥ 95% |
| 재생 성공률 | Mode B UI 변화 시 | ≥ 80% |
| 재생 성공률 | Mode C 오픈도메인 | ≥ 40% |
| 성능 | Grounder p50 지연 | < 800 ms |
| 성능 | Planner p50 지연 | < 3 s |
| 안정성 | 1시간 연속 재생 크래시 | 0 |
| 자원 | RTX 4070에서 idle VRAM | < 10 GB |

---

## 14. 리스크 & 오픈 이슈

| # | 리스크 | 영향 | 완화 |
|---|---|---|---|
| R1 | 커널 AC 게임 대상 사용자가 밴 당함 | 사용자 피해 + 평판 | README·UI 경고, 프로세스 블랙리스트, 해당 게임 감지 시 실행 거부 |
| R2 | 2B grounder의 작은 아이콘 grounding 실패 | 재생률 저하 | UI-Venus/UI-TARS로 자동 업그레이드 옵션, 해상도 업스케일 후 재질의 |
| R3 | VLM 지연이 기대보다 큼 | UX 저하 | Grounder Q4 양자화 기본, Flash Attention, continuous batching |
| R4 | 녹화 파일 용량 폭증 | 디스크 포화 | delta-only 프레임, WebP 양자화, 주기적 정리 |
| R5 | DPI/멀티모니터/HDR 엣지케이스 | 재생률 저하 | P4 전 통합 테스트 스위트 작성 |
| R6 | Qwen3.5/Qwen3-VL 라이선스 변경 | 배포 차단 | Apache 2.0 확인됨 (2026-04 기준), 정기 모니터링 |
| R7 | 사용자가 전역 입력 주입을 실수로 적대적 창에 | 사용자 피해 | 프로세스 화이트리스트, Dry Run 기본 |

**오픈 이슈 (의사결정 필요)**:
1. **UI 프레임워크**: PySide6 vs. Tauri+React (권장: PySide6)
2. **VLM 서버 기본값**: Ollama(쉬움) vs. vLLM(빠름) — Ollama를 기본, vLLM은 Pro 프로필 옵션
3. **데이터 디렉터리 위치**: `%APPDATA%` vs. 프로젝트 상대경로 — `%APPDATA%/macrobania` 권장
4. **Python 패키지 매니저**: `uv` 권장
5. **라이선스**: Apache 2.0 권장 (Qwen과 호환)

---

## 15. 참고 레퍼런스

### 모델 / VLM
- Qwen3-VL: https://github.com/QwenLM/Qwen3-VL (Apache 2.0)
- Qwen3.5 Small (2026-03): https://qwen.ai/blog?id=qwen3.5
- UI-TARS: https://github.com/bytedance/UI-TARS
- UI-Venus (ByteDance)
- OS-Atlas, ShowUI, GUI-Actor, GUI-G1 — NeurIPS 2025
- Fara-7B (Microsoft, 2025-11): 7B computer-use agent

### 선행 오픈소스 프로젝트
- **OpenAdapt** (MIT): https://github.com/OpenAdaptAI/OpenAdapt — Generative RPA, 녹화/재생 프레임워크
- **Bytebot** (self-hosted Docker 데스크톱 agent)
- **Screenpipe** (24/7 로컬 화면 인덱싱)
- **Skyvern** (웹 자동화)
- **OpenCUA / AgentNet Tool** — 크로스 OS 녹화 도구, 22.6K 트라젝토리 데이터셋
- **DuckTrack** — 키/마우스 트래커 (OpenAdapt 내부 사용)

### 캡처 / 입력
- DXcam: https://github.com/ra1nty/DXcam (DXGI, 240 FPS)
- windows-capture (Rust/Python): https://github.com/NiiightmareXD/windows-capture
- PyDirectInput (scan code): https://pypi.org/project/PyDirectInput/
- PH3 Blog "Things you really should know about Windows Input"

### 안티치트 배경 (주의)
- Riot Vanguard dispatch table hooks (Archie's reversing diary)
- BattlEye EULA
- OSDev: kernel mode AC는 DXGI/SendInput을 직접 훅킹

### 학술
- "Open Foundations for Computer-Use Agents" (OpenCUA, arXiv 2508.09123)
- "Learning Next Action Predictors from Human-Computer Interaction" (arXiv 2603.05923)
- ScreenSpot-Pro Leaderboard: https://gui-agent.github.io/grounding-leaderboard/

---

## 16. 다음 단계 (이 문서 승인 후)

1. 본 문서에 대한 피드백 1사이클 (특히 §5 모델 전략, §11 안전, §14 이슈)
2. P0 Spike 착수: Ollama + Qwen3-VL-2B 설치 스크립트 + 단일 스크린샷 grounding 노트북
3. P1 설계 문서 작성 (Capture 서비스 인터페이스, 이벤트 스키마 확정)

> **이 문서는 살아있는 설계 문서다.** 버전은 Git 태그로, 중대한 결정은 ADR(Architecture Decision Record)로 `docs/adr/` 아래 추가한다.
