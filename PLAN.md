# macro-bania — 통합 프로젝트 계획서

> 버전: v1.0 (3-AI 종합본)
> 작성일: 2026-04-22
> 출처: `idea/codex/PLAN.md`, `claude/PLAN.md`, `idea/gemini/implementation_plan.md` 종합
> 상태: 구현 전 합의용 마스터 문서

---

## 0. 이 문서가 만들어진 방식

세 AI가 독립적으로 작성한 계획서를 비교·검증하여 **합의된 사실**과 **각자의 고유 통찰**을 모두 흡수했다. 의견 충돌 지점은 명시적으로 기록했다.

### 3-AI 합의/고유 매트릭스

| 항목 | Codex | Claude | Gemini | 채택 |
|---|---|---|---|---|
| "의미 기반 재생" 핵심 컨셉 | ✅ | ✅ | ✅ | **합의** |
| Qwen3.5-0.8B 단독 부적합 | ✅ 벤치마크 근거 | ✅ | ⚠️ "충분히 가능" | **Codex+Claude** |
| 재생 모드 구분 (A/B/C) | ◯ Faithful/Grounded/Goal | ⭐ **Mode A/B/C 명명** | ⚠️ 단일 언급 | **Claude 프레임 채택** |
| **UIA + OCR + Vision 하이브리드 인식** | ⭐ **UFO2 근거** | ✗ pure vision | ✗ pure vision | **Codex 채택 (핵심)** |
| 하드웨어 티어 (Mini/Standard/Pro) | ◯ | ⭐ 4티어 상세 | ✗ | **Claude 채택** |
| 데이터 스키마 JSON 예시 | ◯ 나열 | ⭐ 상세 | ✗ | **Claude 채택** |
| 프롬프트 초안 4종 | ✗ | ⭐ | ✗ | **Claude 채택** |
| **픽셀 diff 기반 VLM 호출 최적화** | ✗ | ✗ | ⭐ | **Gemini 채택** |
| **상태전이 그래프 중간표현** | ✗ | ✗ | ⭐ State Machine | **Gemini 채택 (옵션)** |
| Fara-7B / OpenCUA-7B 권장 | ⭐ | ✗ | ✗ | **Codex 채택** |
| 현재 코드베이스 진단 | ⭐ | ✗ | ✗ | **Codex 정신 채택** |
| CLI (`record`/`inspect`/`semanticize`/`play`) | ⭐ | ✗ | ✗ | **Codex 채택** |
| KPI 대시보드 | ◯ 수치 나열 | ⭐ 표 | ✗ | **Claude 채택** |
| 리스크 매트릭스 | ◯ R1~R5 | ⭐ R1~R7 | ✗ | **Claude 확장** |
| 안티치트 정책 | ✅ 회피 X | ✅ 회피 X | ⚠️ **우회 고려 언급** | **Codex+Claude (윤리)** |
| UI 프레임워크 | 미정 | PySide6 | CustomTkinter | **PySide6** |

**결론적 방향**: Claude의 전체 구조·스키마·프롬프트 뼈대 + Codex의 **hybrid perception** 및 구체 모델 추천 + Gemini의 **픽셀 diff 최적화**와 **상태전이 그래프** 아이디어.

---

## 1. 한 줄 정의

**"좌표를 재생하는 매크로가 아니다. 사용자의 데스크톱 행동을 `의미 있는 스텝(semantic step)`으로 기록하고, 재생 시 현재 화면 문맥에서 타깃을 다시 찾아 수행하는 로컬-퍼스트 GUI 에이전트다."**

전부 소비자 GPU(RTX 4060~4090)에서 오프라인 동작. 클라우드 API 없이도 완결.

---

## 2. 왜 지금인가 (실현 가능성 합의)

| 근거 | 3-AI 합의 요점 |
|---|---|
| **소형 VLM 성숙** | Qwen3.5 Small (0.8B/2B/4B, 2026-03), Qwen3-VL Dense (2B/4B/8B)가 4bit 양자화로 RTX 3060 이상 구동 |
| **GUI 전용 VLA 다수** | UI-TARS-1.5-7B, OS-Atlas-7B, UI-Venus-1.5-2B, GUI-Actor, GUI-G1-3B, Fara-7B(Microsoft), OpenCUA-7B |
| **벤치마크 증거** | ScreenSpot-Pro: 2B급 54~58%, 7B급 50~69%, UI-Venus-1.5 69.6%, UI-TARS-1.5 91.6% |
| **실행 인프라** | Ollama/vLLM/SGLang/llama.cpp 모두 Qwen3-VL 1등 지원, DXcam 기반 캡처 240 FPS |
| **선행 프로젝트** | OpenAdapt(MIT), Bytebot, OpenCUA(AgentNet), Screenpipe, Skyvern, UFO2 — 데이터 포맷/도구 체인 공개 |

> **합의된 판정**: 실현 가능. 단, "녹화 없이 처음 보는 UI를 완전 자율로" 같은 long-horizon은 여전히 연구 영역이며 V1 대상 아님.

---

## 3. 스코프와 비(非)스코프

### 3.1 스코프 (V1)
- **OS**: Windows 10/11 x64
- **실행 모델**: 로컬 단일 머신, 단일 사용자
- **추론**: 기본 로컬 (Ollama/vLLM), 옵션으로 OpenAI-호환 원격 엔드포인트
- **대상 도메인**:
  - 데스크톱 앱 반복 작업 (파일 정리, 엑셀, 웹 리서치, 스크린샷 업로드)
  - 브라우저 기반 단순 퀘스트/폼 제출
  - 런처·설정창·메뉴 탐색
  - 안티치트 없는 싱글게임/에뮬레이터 메뉴 루프
  - 창 위치/해상도/DPI가 달라도 동일 의미의 action 재수행

### 3.2 비(非)스코프 (V1 명시적 제외)
- **커널 안티치트(Riot Vanguard, BattlEye, EAC, Hyperion) 탑재 경쟁 온라인 게임** — 기술적 탐지 + ToS 위반
- 실시간 전투 / FPS 에임 (VLM 루프 레이턴시로 불가)
- 결제·송금·계정 변경 같은 irreversible action의 완전 무인 처리 (휴먼 체크포인트 강제)
- 모바일 OS 제어 (ADB/XCTest) — Phase 8+
- SaaS/클라우드 멀티테넌시
- **안티치트 우회 기법** (자연스러운 마우스 곡선을 "탐지 회피용"으로 쓰는 모든 기능) — Gemini 초안에 언급되었으나 윤리·법적 이유로 **탈락**. 사용자가 소유한 테스트 환경에서만 쓸 수 있는 "부드러운 커서 이동"은 접근성 개선 관점에서만 허용

### 3.3 도덕적/법적 가드레일
- "게임 일일퀘스트 자동화"는 **타이틀별 ToS 검증 후 사용자 개인 책임**. 앱은 해당 게임 감지 시 경고 모달
- Play 기본값 = **Dry Run + 사용자 확인**. 자동 실행은 명시적 opt-in
- PII 스크러버 기본 활성화 (카드/주민/이메일/주소 패턴)
- 감사 로그(audit log)는 사용자 동의하에만 삭제 가능

---

## 4. 현재 코드베이스 상태

### 2026-04-22 P0 스캐폴딩 완료 스냅샷

| 영역 | 상태 | 비고 |
|---|---|---|
| 레포 초기화 (`.gitignore`, `README.md`, `pyproject.toml`) | ✅ | Apache-2.0, Python 3.11+, uv/hatch |
| 패키지 스켈레톤 (`src/macrobania/`) | ✅ | `agent`, `capture`, `inputio`, `perception`, `recording`, `player`, `safety`, `storage` |
| Config/Settings (`config.py`) | ✅ | pydantic-settings, `MACROBANIA_*` env 오버라이드 |
| 데이터 모델 (`models.py`) | ✅ | PLAN §10 전체 스키마 Pydantic 표현 |
| SQLite 스토리지 (`storage/`) | ✅ | DDL v1, WAL 모드, 트랜잭션 헬퍼 |
| VLM 클라이언트 (`agent/client.py`) | ✅ | OpenAI-호환, 이미지 base64 인코딩 |
| Grounder (`agent/grounder.py`) | ✅ | Qwen3-VL 0-1000 bbox 관대 파서 |
| 프롬프트 (`agent/prompts.py`) | ✅ | Grounder/Verifier 시스템 + user 포맷 |
| PII 스크러버 (`safety/pii.py`) | ✅ | email/card/RRN/phone/IP/API key |
| 로깅 (`logging.py`) | ✅ | structlog + 감사 로그 분리 |
| CLI (`cli.py`) | ✅ | `info`, `doctor`, `config-dump` 동작. `record/inspect/semanticize/play`는 Phase 스텁 |
| P0 Spike (`scripts/spike_grounding.py`) | ✅ | Ollama 연결 시 bbox 출력, 부재 시 안내 종료 |
| 설계 문서 (`docs/design/recorder.md`) | ✅ | Phase 1 착수 준비 |
| ADR (`docs/adr/0001-three-ai-synthesis.md`) | ✅ | 본 통합 결정 영구 보존 |
| 테스트 (`tests/`) | ✅ | **45 passed, coverage 78%**, ruff 클린 |

Phase 1(Recorder) 실제 구현부터 사용자 기능이 시작된다.

### 현 시점 자산
```
E:\Workspace\2026\macro-bania\
├── .git/ · .gitignore · PLAN.md · README.md · pyproject.toml
├── src/macrobania/   (agent, capture, inputio, perception, recording, player, safety, storage 등)
├── scripts/          (spike_grounding.py)
├── tests/            (7 files, 45 tests)
├── docs/
│   ├── adr/0001-three-ai-synthesis.md
│   └── design/recorder.md
├── claude/PLAN.md              ← 원본 Claude 초안
├── idea/codex/PLAN.md          ← 원본 Codex 초안
├── idea/gemini/implementation_plan.md
└── venv/                        (gitignored)
```

---

## 5. 설계 원칙 (7계명)

| # | 원칙 | 의미 |
|---|---|---|
| 1 | **Local-first** | 기본은 오프라인 로컬 추론. 외부 API는 opt-in |
| 2 | **Hybrid Perception** ⭐ | Vision 단독이 아니라 `UIA + OCR + Screenshot` 삼중 인식 (UFO2 근거) |
| 3 | **Tiered Intelligence** | 빠른 Grounder를 타이트 루프에, 비싼 Planner는 에스컬레이션 시만 |
| 4 | **Record-time heavy, Play-time smart** | 녹화는 raw trace 풍부하게, 의미화는 사후 배치, grounding은 재생 시 실시간 |
| 5 | **Verification-first** | 모든 Step 전후 precondition/postcondition 검증 기본 |
| 6 | **Human override always** | 전역 kill switch, 프로세스 화이트리스트, Dry Run 기본 |
| 7 | **Model swappable** | OpenAI-호환 인터페이스로 추상화, 모델 교체가 설정 변경 수준 |

---

## 6. 하드웨어 프로필 (타깃 매트릭스)

| 프로필 | GPU | VRAM | 권장 모델 구성 | 기대 스텝 지연 |
|---|---|---|---|---|
| **Mini** | RTX 3060/4060 | 8 GB | Qwen3-VL-2B (Q4) 단일 | 1.5–3.0 s |
| **Standard** | RTX 4070/4070S | 12 GB | Qwen3-VL-8B (Q4) 단일 또는 UI-TARS-1.5-7B | 1.0–2.0 s |
| **Pro** | RTX 4080/4090 | 16–24 GB | Planner(Qwen3-VL-8B / OpenCUA-7B) + Grounder(UI-Venus-2B) + Captioner(Qwen3.5-0.8B) | 0.5–1.5 s |
| **Workstation** | A6000 / 2×4090 | 48 GB+ | Qwen3-VL-30B-A3B MoE 또는 다중 에이전트 | 0.3–1.0 s |

> 수치는 vLLM/llama.cpp 성능 자료를 근거로 한 **가이드라인**. 실측은 Phase 0 Spike에서 프로필별 확정.

---

## 7. 기술 스택

| 레이어 | 선택 | 근거 |
|---|---|---|
| 언어 | Python 3.11+ | VLM SDK / 캡처 / 입력 / UIA 전부 파이썬 생태계에서 성숙 |
| 화면 캡처 | `DXcam`(DXGI) 기본, `windows-capture`(Rust) 폴백 | 240 FPS 검증, delta 프레임 지원 |
| **UI Automation** ⭐ | `pywinauto` + `uiautomation`(cpp 래퍼) | Win32 UIA 트리 접근, UFO2 스타일 hybrid 인식의 핵심 |
| **OCR** ⭐ | `RapidOCR` (ONNX, 로컬) 또는 `PaddleOCR` | Windows에서 무료·고속 |
| 입력 리스너 | `pynput` + Win32 Raw Input (ctypes) | Scan code 보존, 전역 훅 |
| 입력 주입 | `pydirectinput`(Scan code `SendInput`) | DirectInput 게임 호환 |
| VLM 서버 | `Ollama`(개발 기본) / `vLLM`(Pro 프로필) | OpenAI-호환 API로 추상화 |
| VLM 클라이언트 | `openai` SDK + OpenAI-호환 엔드포인트 | 서버 교체 무통증 |
| 저장소 | SQLite(메타데이터) + 파일시스템(WebP 프레임) | 임베디드, 백업·포팅 용이 |
| UI | PySide6 | Python 통일, Qt 성숙 (Tkinter보다 생산성↑) |
| 에이전트 프레임 | **자체 얇은 래퍼** | LangChain 지양 (과도한 추상) |
| 패키징 | `uv` + `hatch` + `pyinstaller` | 현대 빌드, 단일 exe 배포 |
| 관측 | `structlog` + SQLite 이벤트 테이블 | 외부 의존 X |

---

## 8. 모델 전략 (세 AI 종합)

### 8.1 "Qwen3.5-0.8B 단독" 아이디어에 대한 판정

**사용자가 처음 제안한 Qwen3.5-0.8B 단일 모델 전략은 채택하지 않는다.**

근거 (Codex 벤치마크 + Claude 리서치):

| 항목 | Qwen3.5-0.8B | Qwen3.5-2B | Qwen3-VL-2B | UI-Venus-1.5-2B | Qwen3-VL-8B | UI-TARS-1.5-7B | OpenCUA-7B | Fara-7B |
|---|---|---|---|---|---|---|---|---|
| VRAM (Q4) | ~2 GB | ~3 GB | ~4 GB | ~4 GB | ~8 GB | ~8 GB | ~8 GB | ~8 GB |
| ScreenSpot-Pro | 46.5 | 54.5 | — | 58.8 | 67.7 | 91.6 (ScreenSpot) | 50.0 | — |
| OSWorld / Computer Use | 낮음 | 보통 | 보통 | 강 | 강 | 매우 강 | 24.3/27.9 | WebVoyager 73.5 |
| 컨텍스트 | 262K | 262K | 256K→1M | 256K | 256K | 128K | 128K | 128K |
| 사전학습 특화 | 범용 | 범용 | Visual Agent | GUI 전용 | Visual Agent | GUI SOTA | Computer-use | Computer-use |
| **추천 역할** | **Captioner** | 경량 통합 | 경량 Grounder | **정밀 Grounder** | Planner | Single-Agent | Single-Agent | Single-Agent |

### 8.2 역할별 모델 분담 (계층형 구조)

```
┌─────────────────────────────────────────────────────────────┐
│  Planner                   호출: 낮음 (신상황 시에만)           │
│  역할: 태스크 분해, 오류 복구, Goal Mode 주도                  │
│  후보: Qwen3-VL-8B · OpenCUA-7B · Fara-7B                    │
├─────────────────────────────────────────────────────────────┤
│  Grounder ★ 핵심           호출: 높음 (매 스텝)                │
│  역할: "Login 버튼" + 스크린샷 → [x,y,w,h] (0–1000 정규화)     │
│  후보: UI-Venus-1.5-2B · Qwen3-VL-2B · Qwen3.5-2B            │
├─────────────────────────────────────────────────────────────┤
│  Verifier                  호출: 중간 (pre/post condition)    │
│  역할: yes/no + 근거                                           │
│  후보: Grounder 재사용                                         │
├─────────────────────────────────────────────────────────────┤
│  Captioner                 호출: 낮음 (녹화 후 배치)            │
│  역할: raw event + frame_before/after → semantic step         │
│  후보: Qwen3.5-0.8B (사용자 제안 모델 — 여기서 활용)           │
└─────────────────────────────────────────────────────────────┘
```

### 8.3 단일 모델 모드 vs 다중 모델 모드

| 모드 | VRAM | 품질 | 복잡도 | 추천 대상 |
|---|---|---|---|---|
| **Single-Agent** | 8–12 GB | 중-상 | 낮음 | Standard 프로필. UI-TARS-1.5-7B 또는 Qwen3-VL-8B 단일이 Planner+Grounder 겸임 |
| **Multi-Agent** | 12–24 GB | 상 | 중 | Pro 프로필. 각 역할 분리로 레이턴시/정확도 동시 최적화 |

V1은 **Single-Agent 기본, Multi-Agent 옵션** 제공. 사용자가 자동 선택되는 기본값을 하드웨어로 결정.

---

## 9. 시스템 아키텍처

### 9.1 레이어 구성 (Codex hybrid perception 반영)

```
┌───────────────────────────────────────────────────────────────────┐
│                        PySide6 UI                                  │
│   Library │ Record │ Process │ Play │ Editor │ Audit Log           │
└───────────────────────────────────────────────────────────────────┘
                              │  (asyncio / Qt signals)
┌───────────────────────────────────────────────────────────────────┐
│                       Orchestrator (FSM)                           │
│      idle → record → processing → play → paused → failed           │
└───────────────────────────────────────────────────────────────────┘
       │            │              │              │           │
┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────┐ ┌─────────┐
│ Capture  │  │ Input I/O│  │  Perception  │  │ Storage  │ │  VLM    │
│ DXcam/   │  │ Listener │  │ ★ Hybrid     │  │ SQLite + │ │ Server  │
│ WGC      │  │ Injector │  │  UIA + OCR + │  │ Frames   │ │ Ollama/ │
│          │  │ FailSafe │  │  Screenshot  │  │ (WebP)   │ │ vLLM    │
└──────────┘  └──────────┘  └──────────────┘  └──────────┘ └─────────┘
                                    │                           │
                        ┌───────────┴───────────────┐   ┌───────┴───────┐
                        │  Frame Diff / Change Det. │   │  Agent Core   │
                        │  (★ Gemini pixel-diff)    │   │  Planner      │
                        └───────────────────────────┘   │  Grounder     │
                                                        │  Verifier     │
                                                        │  Captioner    │
                                                        └───────────────┘
```

### 9.2 Hybrid Perception 파이프라인 (UFO2 참조)

```
capture.now() ──┬──► UIA Tree (window/control/role/name/bbox)
                ├──► OCR (text blocks + bbox)
                └──► Screenshot (bytes)
                            │
                            ▼
                    ┌──────────────┐
                    │  Candidate   │  "Login" 같은 target string이 주어지면
                    │   Matcher    │  UIA+OCR이 먼저 후보 좁힘 (0~N개)
                    └──────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ VLM Grounder          │  후보가 0개 or 모호할 때만 VLM 호출
                │ (Final disambiguator) │  → 최종 bbox 결정
                └───────────────────────┘
```

**효과**: VLM 호출 빈도 감소, 작은 UI 요소 정확도 상승, 레이턴시 단축. 순수 비전 전략 대비 스텝 지연 30~60% 감소 예상.

### 9.3 패키지 구조

```
macro-bania/
├── src/macrobania/
│   ├── capture/          # DXGI/WGC 래퍼, 프레임 diff, delta 인코딩
│   ├── perception/       # ★ UIA + OCR + screenshot 통합
│   │   ├── uia.py
│   │   ├── ocr.py
│   │   └── matcher.py    # candidate reduction
│   ├── inputio/          # listener / injector / failsafe
│   ├── agent/
│   │   ├── planner.py
│   │   ├── grounder.py
│   │   ├── captioner.py
│   │   ├── verifier.py
│   │   └── prompts/      # Jinja 템플릿
│   ├── recording/        # event aggregation, step builder, state graph
│   ├── player/
│   │   ├── mode_a_faithful.py
│   │   ├── mode_b_grounded.py  ★ V1 핵심
│   │   └── mode_c_autonomous.py
│   ├── storage/          # SQLite 스키마, WebP I/O
│   ├── safety/           # PII, fail-safe, allowed-process, audit
│   ├── orchestrator.py
│   ├── cli.py            # ★ record / inspect / semanticize / play
│   └── ui/               # PySide6
├── models/               # gguf / safetensors (git-ignored)
├── recordings/           # 사용자 데이터 (git-ignored, %APPDATA% 기본)
├── docs/adr/             # 아키텍처 결정 기록
├── tests/
├── pyproject.toml
└── PLAN.md
```

---

## 10. 데이터 스키마

### 10.1 Recording (상위 객체)

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
  "step_count": 14,
  "state_graph_id": "sg_rec_..."   // ★ Gemini 상태전이 그래프 (옵션)
}
```

### 10.2 Raw Event (저수준)

```json
{
  "ts_ns": 173840293410293,
  "kind": "mouse_down | mouse_up | mouse_move | key_down | key_up | scroll | text_input",
  "data": {
    "x": 1024, "y": 680,
    "button": "left",
    "vk": 65, "scan": 30, "extended": 0,
    "text": "password123",
    "dx": 0, "dy": -1
  },
  "window_hwnd": "0x000A5B2C",
  "window_title": "My Game — Chrome"
}
```

### 10.3 Frame (스크린샷 + UIA snapshot)

```
frames/rec_xxx/
├── f0000.webp       // keyframe (5s마다 or 대변화 시)
├── f0001.webp       // delta (변경 영역만 크롭)
├── uia/
│   ├── f0000.json   // UIA tree snapshot (root → controls)
│   └── ...
├── ocr/
│   ├── f0000.json   // OCR blocks: [{text, bbox, conf}]
│   └── ...
└── meta.sqlite      // (ts_ns, kind, changed_bbox, hwnd, ...)
```

**Gemini 픽셀 diff 최적화**: 프레임은 직전 프레임과 픽셀 diff ≥ 2% 일 때만 저장. 5초 간격 keyframe 강제. UIA/OCR snapshot은 이벤트 주변 ±300ms만.

### 10.4 Semantic Step (VLM 후처리 생성)

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
    "target_uia_path": "Pane/Tree/TreeItem[2]",       // ★ UIA 경로
    "target_ocr_text": "일일 퀘스트",                  // ★ OCR 매칭 근거
    "value": null,
    "modifiers": []
  },
  "caption": "일일 퀘스트 탭을 클릭",
  "precondition": "로비 화면이 표시되고 사이드바가 열려 있다",
  "postcondition": "오른쪽 패널에 퀘스트 목록이 나타난다",
  "confidence": 0.88
}
```

### 10.5 액션 공간 (통합 표준)

| type | 설명 | value | 비고 |
|---|---|---|---|
| `click` | 단일 클릭 | button (left/right/middle) | bbox 중심 클릭 |
| `double_click` | 더블 클릭 | button | |
| `drag` | 드래그 | to_bbox | start→end 경로 |
| `type` | 텍스트 입력 | text | IME·scan code 고려 |
| `hotkey` | 조합키 | keys (예: ["ctrl","s"]) | scan code 기반 |
| `scroll` | 스크롤 | direction, amount | |
| `wait` | 대기 | ms 또는 `until` 조건 | VLM 검증 조건도 허용 |
| `focus_window` | 창 포커스 | window_regex | Play 시작 시 자동 |
| `done` | 종료 | success/fail | 로그 마감 |

### 10.6 상태전이 그래프 (State Machine, Gemini 아이디어)

녹화 여러 개를 묶으면 `state → action → state` 그래프가 된다. 같은 태스크의 변형을 학습하고 Mode C의 Few-shot에 쓸 수 있다.

```
{
  "nodes": [
    {"id": "main_lobby", "signature": "<screenshot hash + UIA hash>"},
    {"id": "quest_panel", ...}
  ],
  "edges": [
    {"from": "main_lobby", "to": "quest_panel", "action_ref": "step_3"}
  ]
}
```

V1에선 **저장만** 하고 활용은 V2에서. 지금 스키마에 자리만 잡아둔다.

---

## 11. Record 파이프라인

```
┌─────────────┐   ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
│ User hits   │──►│ Capture on     │──►│ Event listener │──►│ Ring buffer    │
│ Record      │   │ (DXcam 30fps,  │   │ (pynput raw)   │   │ (events + ts)  │
└─────────────┘   │  diff-only)    │   └────────────────┘   └────────────────┘
                  └────────────────┘            │
                          │                     ▼
                          │             ┌───────────────────┐
                          │             │ UIA snapshot ±ev  │
                          │             │ OCR cached        │
                          │             └───────────────────┘
                          ▼
                  ┌────────────────┐
                  │ SQLite + Files │
                  │ + WebP frames  │
                  └────────────────┘
```

### 11.1 녹화 중 원칙
- **VLM 호출 금지** (GPU는 사용자 작업용으로 양보)
- 프레임 저장: 직전 대비 diff ≥ 2%일 때만 delta 저장, 5초 간격 keyframe
- UIA/OCR snapshot: 입력 이벤트 발생 ±300ms 윈도우만 채취
- PII 마스킹 훅: `text_input`은 저장 전 정규식 스크러버 통과

### 11.2 후처리 (배치, Captioner 담당)
1. 이벤트를 시간창(default 1.5s)으로 클러스터링 → 후보 Step 생성
2. 각 후보에 대해 `frame_before`, `frame_after`, `raw_events`, `uia_snapshot`, `ocr_blocks` → Captioner 프롬프트
3. 대상 요소 크롭 + 자연어 서술(한국어) + UIA 경로 매칭
4. 사용자가 Editor UI에서 리뷰/수정 가능
5. (선택) 여러 녹화 통합 시 state graph 업데이트

---

## 12. Play 파이프라인 (Mode A/B/C)

### 12.1 Mode A — Faithful Replay
- 원본 타임스탬프대로 이벤트 재생
- 각 Step 전 Verifier에게 "precondition 충족?" yes/no
- 실패 시 최대 N초 대기 후 재시도, 여전히 실패면 일시정지 + 사용자 알림
- **용도**: 디버깅, baseline 비교, 타이밍 민감 태스크

### 12.2 Mode B — Grounded Replay ★ V1 핵심

```python
for step in recording.steps:
    screenshot, uia_tree, ocr_blocks = perception.snapshot()

    # 1. precondition 체크
    if step.precondition:
        ok, _ = verifier.yesno(screenshot, step.precondition)
        if not ok:
            wait_and_retry(); continue

    # 2. hybrid 후보 좁히기 (Codex UFO2 방식)
    candidates = matcher.find_candidates(
        uia_tree, ocr_blocks,
        target_desc=step.action.target_description,
        uia_hint=step.action.target_uia_path,
        ocr_hint=step.action.target_ocr_text
    )

    # 3. 후보가 1개면 VLM 없이 결정, 아니면 Grounder 호출
    if len(candidates) == 1:
        bbox = candidates[0].bbox
    else:
        bbox = grounder.locate(
            screenshot, candidates,
            query=step.action.target_description,
            hint_bbox=step.action.target_bbox_hint
        )

    # 4. 주입
    inject.execute(step.action.type, bbox, step.action.value)

    # 5. postcondition 검증
    new_shot, *_ = perception.snapshot()
    if step.postcondition:
        ok, _ = verifier.yesno(new_shot, step.postcondition)
        if not ok:
            escalate_to_planner(step)   # Mode C로 에스컬레이션
```

**최적화 (Gemini 픽셀 diff)**: `perception.snapshot()`은 직전 대비 diff < 임계값이면 VLM 호출 스킵하고 이전 결과 재사용. 화면 전환 완료 전 폴링에서 특히 유용.

### 12.3 Mode C — Autonomous Goal
- 사용자는 자연어 목표만 제공 (녹화 없이도 가능)
- Planner ReAct 루프:
  ```
  Observation: <스크린샷 + UIA + OCR 요약>
  Thought: <다음 행동 추론>
  Action: <액션 JSON>
  ```
- 녹화가 있으면 RAG(target_description 벡터 검색)로 유사 Step을 Few-shot 주입
- state graph로 현재 state 매칭 시 고속 경로 선택
- 속도 2–8 s/step. 성공률은 태스크 난이도 × 모델 티어

### 12.4 공통 Fail-Safe
- **전역 hotkey**: `Ctrl+Shift+Esc` 더블탭 → 즉시 중단
- **마우스 좌상단**: `pyautogui.FAILSAFE`
- **프로세스 화이트리스트**: 활성 창이 녹화 시점 `target_process`와 다르면 입력 차단
- **재생 속도 슬라이더**: 25–200%
- **연속 실패 임계**: N회 실패 시 자동 정지 + 상세 로그
- **Irreversible 게이트**: 결제/송금/계정 변경 감지 시 휴먼 컨펌 강제

---

## 13. 프롬프트 초안

### 13.1 Grounder (Qwen3-VL / UI-Venus)

```
System:
You are a GUI grounding assistant. Given a screenshot and a target description,
return the bounding box of the exact UI element in 0-1000 normalized coords.
You MAY receive pre-filtered candidates (UIA/OCR hits). Prefer them unless
visual evidence clearly contradicts. Return ONLY:
{"bbox":[x1,y1,x2,y2],"candidate_id":int|null,"confidence":0.0-1.0,"reason":"..."}

User:
[image]
Target: "일일 퀘스트 탭 (사이드바 상단 두 번째 아이콘)"
Hint (from recording): bbox=[124,280,176,332] @ 2560x1440
Current resolution: 1920x1080
Candidates:
  #0 UIA: TreeItem "Daily Quest", bbox=[92,210,132,248]
  #1 OCR: "일일 퀘스트", bbox=[96,215,128,232]
```

### 13.2 Verifier

```
System:
Return ONLY: {"answer":"yes"|"no","reason":"..."}

User:
[image]
Question: "오른쪽 패널에 퀘스트 목록이 나타났는가?"
```

### 13.3 Captioner (후처리, Qwen3.5-0.8B)

```
System:
You generate ONE "semantic step" from low-level input events + UIA + OCR context.
Output one JSON matching Step schema. Concise Korean for caption.

User:
[image: frame_before]
[image: frame_after]
Events (timeline):
  t=0ms   mouse_move (124,280)
  t=50ms  mouse_down left
  t=180ms mouse_up left
UIA under cursor at t=50ms: TreeItem "Daily Quest"
OCR near cursor: "일일 퀘스트"
Window: "My Game — Chrome"
```

### 13.4 Planner (Mode C)

```
System:
You control a Windows desktop. Plan the NEXT SINGLE action toward the goal.
Action schema: {"type":"click"|"type"|"hotkey"|"scroll"|"wait"|"done",
                "target_description"?:str, "value"?:str, "rationale":str}

User:
Goal: "웹 게임 일일 퀘스트 5개 모두 수령 후 로그아웃"
Recent history: [step-1 clicked '로그인', step-2 typed username, ...]
Relevant past steps (RAG, top-3):
  - step_rec_A/2: "일일 퀘스트 탭을 클릭" at bbox [124,280,176,332]
  - ...
[image: current screen]
UIA summary: 12 buttons, 3 text fields...
OCR top-5: 일일퀘스트, 로그아웃, 설정, ...
```

---

## 14. 안전 / 프라이버시

| 항목 | 구현 |
|---|---|
| 프로세스 화이트리스트 | Play 시 활성 HWND의 프로세스가 `target_process` 불일치면 입력 차단 |
| **Dry Run 기본** | 실제 클릭 대신 OpenCV 오버레이 창에 crosshair만 표시 |
| 사용자 확인 게이트 | 최초 실행 / 장시간 미실행 후 재개 / 연속 실패 후 재시도 시 모달 |
| PII Scrubber | `presidio-analyzer` + 정규식 (카드/주민/이메일/주소) |
| 로컬 전용 기본 | 네트워크 호출은 opt-in, UI에 표시 |
| 감사 로그 | 모든 주입 액션을 SQLite에 기록, 사용자 동의 전 삭제 불가 |
| 안티치트 우회 금지 | 커널 AC 게임 감지 시 실행 거부. "자연스러운 커서"는 접근성 목적에만 |
| Irreversible 액션 | 결제/송금/삭제 키워드 감지 시 휴먼 컨펌 강제 |
| 모델 서버 격리 | Ollama는 localhost만 바인드, 원격 서버는 옵션으로만 |

---

## 15. 구현 로드맵

**1인 개발자 기준, 주 단위 추정. 통합본은 Codex 단순성 + Claude 세분성 절충.**

| Phase | 기간 | 상태 | 산출물 | 완료 조건 (KPI) |
|---|---|---|---|---|
| **P0 Spike** | 1주 | 🚧 진행 중 (스캐폴딩 ✅, Ollama 실측 대기) | Ollama + Qwen3-VL-2B 띄우고 스크린샷 → bbox 데모 | 단일 grounding 요청 < 1.5s, 체감 정확도 ≥ 80% |
| **P1 Recorder** | 2–3주 | ✅ 코어 완료 | DXcam/MSS + pynput + UIA + OCR + SQLite writer + RecordingSession + CLI record/inspect | 65 tests pass (프레임 diff/PII/writer 검증) |
| **P2 Trace Viewer + Semanticizer** | 2주 | ✅ 코어 완료 | Captioner(Qwen3.5-0.8B) + rule-based fallback, event clustering, HTML viewer, CLI semanticize/export-html | 79 tests (classify/cluster/semanticize/viewer 검증) |
| **P3 Mode A Faithful** | 1주 | ⏳ | Faithful Replay + precondition 체크 | 노트패드 열기→쓰기→저장 20회 중 ≥ 18회 |
| **P4 Mode B Grounded ★** | 3주 | ⏳ | Hybrid matcher + Grounder + Verifier + Dry Run UI | 창 위치/해상도 랜덤화해도 동일 태스크 ≥ 16/20 |
| **P5 Safety & UI** | 2주 | ⏳ | PySide6 GUI, 프로세스 화이트리스트, kill switch, audit log, PII | 비개발자 5명 사용성 테스트 통과 |
| **P6 Standard Agent Tier** | 2–3주 | ⏳ | OpenCUA-7B 또는 Fara-7B 연결, retry/escalation | 긴 체인 태스크 복구율 ≥ 60% |
| **P7 Mode C Autonomous** | 4주+ | ⏳ | Planner ReAct + RAG + state graph 활용 | 샌드박스 웹 태스크 ≥ 3/5 완주 |
| **P8 Fine-tuning (옵션)** | 4주+ | ⏳ | 개인 녹화 기반 LoRA (Unsloth SFT) | Grounder 실패율 30% → 15% |

**총 MVP (P0–P5)**: 약 **11–14주 (3–4개월)**
**Standard Tier (P6 포함)**: 약 **4–5개월**
**Autonomous (P7+)**: 연구 성격, 기간 보장 X

---

## 16. KPI 대시보드

| 카테고리 | 지표 | 목표 (v1.0) |
|---|---|---|
| 녹화 품질 | 프레임 드롭율 | < 1% |
| 녹화 품질 | 1시간 연속 녹화 크래시 | 0 |
| 녹화 품질 | PII 미스율 | < 0.1% |
| 후처리 | Step caption 승인율 (수정량<20%) | ≥ 85% |
| 재생 성공률 | Mode A 단순 태스크 | ≥ 95% |
| 재생 성공률 | Mode B 창 위치/DPI 변화 시 | ≥ 80% |
| 재생 성공률 | Mode B 장시간(30min) 태스크 | ≥ 70% |
| 재생 성공률 | Mode C 오픈도메인 | ≥ 40% |
| 성능 | Grounder p50 지연 | < 800 ms |
| 성능 | Grounder p95 지연 | < 2 s |
| 성능 | Planner p50 지연 | < 3 s |
| 성능 | Hybrid matcher가 VLM 호출 제거 비율 | ≥ 40% |
| 안정성 | 1시간 연속 재생 크래시 | 0 |
| 안정성 | kill switch 반응 | 즉시 (<100ms) |
| 자원 | RTX 4070 idle VRAM | < 10 GB |

---

## 17. 리스크 & 이슈

### 17.1 리스크 매트릭스

| # | 리스크 | 영향 | 확률 | 완화 |
|---|---|---|---|---|
| R1 | 사용자가 커널 AC 게임 대상 사용 → 밴 | 평판·법적 | 중 | README/UI 경고, 감지 시 실행 거부, 회피 기능 비탑재 |
| R2 | 2B Grounder가 작은 아이콘/저대비 UI에서 실패 | 재생률 | 중 | UIA/OCR hybrid가 1차 필터, UI-Venus/UI-TARS 업그레이드 경로, 해상도 업스케일 후 재질의 |
| R3 | VLM 레이턴시 > 기대치 | UX | 중 | Q4 기본, Flash Attention, 픽셀 diff 기반 캐싱, hybrid로 호출 빈도↓ |
| R4 | 녹화 파일 용량 폭증 | 디스크 | 중 | delta-only WebP, UIA snapshot 이벤트 주변만, 주기 정리 |
| R5 | DPI/멀티모니터/HDR 엣지케이스 | 재생률 | 중 | P4 전 통합 테스트 스위트, DPI-aware 계산 헬퍼 |
| R6 | 모델 라이선스 변경 | 배포 | 저 | 현 Apache 2.0 확인 (Qwen/UI-Venus/OpenCUA), 정기 모니터링 |
| R7 | 사용자가 입력을 적대적 창에 실수 주입 | 사용자 피해 | 저 | 프로세스 화이트리스트, Dry Run 기본 |
| R8 | 작은 모델 thinking loop / hallucination | 품질 | 중 | constrained JSON 출력, short horizon, max retry/step, verifier 분리 |
| R9 | UIA가 게임 클라이언트에서 동작 X (Unity/Unreal) | 재생률 | 중 | pure vision 폴백, 후보 없으면 자동 VLM-only 모드 |
| R10 | 비동기 상태(로딩 스피너) 미인식 | 재생률 | 중 | Verifier 기반 `wait-until`, spinner/dialog detector 추가 |

### 17.2 오픈 이슈 (V1 결정 필요)

1. **Grounder 기본 모델**: UI-Venus-1.5-2B vs Qwen3-VL-2B → Phase 0에서 벤치
2. **Standard-tier 에이전트**: OpenCUA-7B vs Fara-7B vs Qwen3-VL-8B → Phase 6에서 비교
3. **OCR 엔진**: RapidOCR vs PaddleOCR → Phase 1 Spike에서 한국어 정확도 비교
4. **데이터 디렉터리**: `%APPDATA%/macrobania` (권장) vs 프로젝트 상대
5. **라이선스**: Apache 2.0 권장 (Qwen과 호환)
6. **배포 포맷**: pyinstaller onefile vs installer(Inno Setup) → 사용자 피드백 후 결정

---

## 18. 지금 바로 해야 할 일

### 완료 (2026-04-22)
- [x] `pyproject.toml` + `src/macrobania/` 스켈레톤 (uv)
- [x] `docs/adr/0001-three-ai-synthesis.md`
- [x] `README.md` (경고·라이선스·스코프)
- [x] `scripts/spike_grounding.py` (Ollama 엔드포인트 설치 시 실행 가능)
- [x] CLI 스켈레톤 (`info`/`doctor` 실동작, `record/inspect/semanticize/play` Phase 스텁)
- [x] `docs/design/recorder.md`
- [x] Foundation: config / models / storage / logging / PII
- [x] 단위 테스트 45/45 통과 (커버리지 78%)

### 다음 1주차
1. 실사용자 머신에서 `ollama serve` + `ollama pull qwen3-vl:2b` 후 `scripts/spike_grounding.py` 10회 측정 → **ADR-0003 Grounder 기본값** 결정
2. 대안 모델 벤치: UI-Venus-1.5-2B GGUF 변환·실측
3. Phase 1 구현 착수: `capture/dxcam_backend.py`, `inputio/listener.py`

---

## 19. 참고 레퍼런스

### 19.1 모델 / VLM
- **Qwen3-VL**: https://github.com/QwenLM/Qwen3-VL (Apache 2.0)
- **Qwen3.5 Small Series (2026-03)**: https://qwen.ai/blog?id=qwen3.5, HF card `Qwen/Qwen3.5-0.8B`, `Qwen3.5-2B`
- **UI-TARS**: https://github.com/bytedance/UI-TARS
- **UI-Venus-1.5 Technical Report** (2026-02, arXiv 2602.09082)
- **OS-Atlas, ShowUI, GUI-Actor, GUI-G1** — NeurIPS 2025
- **Fara-7B** (Microsoft Research, 2025-11): https://www.microsoft.com/en-us/research/blog/fara-7b-an-efficient-agentic-model-for-computer-use/
- **OpenCUA**: https://opencua.xlang.ai/ (7B 모델 + AgentNet 22.6K 데이터셋)

### 19.2 아키텍처 레퍼런스
- **UFO2: The Desktop AgentOS** (arXiv 2504.14603) — ★ hybrid UIA+vision 설계 근거
- **OpenAdapt** (MIT): https://github.com/OpenAdaptAI/OpenAdapt — Generative RPA
- **Bytebot**: self-hosted Docker 데스크톱 agent
- **Screenpipe**: 24/7 로컬 화면 인덱싱
- **Skyvern**: 웹 자동화
- **DuckTrack**: 키/마우스 트래커

### 19.3 캡처 / 입력 / Windows
- **DXcam**: https://github.com/ra1nty/DXcam (DXGI, 240 FPS)
- **windows-capture** (Rust/Python): https://github.com/NiiightmareXD/windows-capture
- **pywinauto / uiautomation**: Windows UIA 트리
- **PyDirectInput** (scan code): https://pypi.org/project/PyDirectInput/
- **PH3 Blog "Things you really should know about Windows Input"**

### 19.4 안티치트 (주의 · 참고용)
- **Riot Vanguard dispatch table hooks** (Archie's reversing diary, 2025-04)
- **BattlEye EULA** (https://www.battleye.com/downloads/EULA.txt)
- 핵심 관찰: `NtUserSendInput`, `NtGdiDdDDIOutputDuplGetFrameInfo`, `NtGdiBitBlt` 모두 Vanguard가 커널 훅

### 19.5 학술
- "Open Foundations for Computer-Use Agents" (OpenCUA, arXiv 2508.09123)
- "Learning Next Action Predictors from Human-Computer Interaction" (arXiv 2603.05923)
- **ScreenSpot-Pro Leaderboard**: https://gui-agent.github.io/grounding-leaderboard/

### 19.6 원본 3-AI 계획서
- `idea/codex/PLAN.md` — UFO2 hybrid, OpenCUA/Fara-7B 추천, 벤치마크 수치
- `claude/PLAN.md` — Mode A/B/C, 하드웨어 티어, 프롬프트, KPI, 리스크
- `idea/gemini/implementation_plan.md` — 픽셀 diff 최적화, 상태전이 그래프 아이디어

---

## 20. 문서 관리

- **버전**: Git 태그(`plan-v1.0`, `plan-v1.1`…)로 관리
- **중대 결정**: `docs/adr/NNNN-title.md` (Architecture Decision Record)
- **살아있는 문서**: Phase 완료 시 KPI 달성치와 실제 값을 부록으로 append
- **라이선스**: 본 계획서는 프로젝트와 동일 라이선스(Apache 2.0 예정)

---

### 📌 핵심 요약 (TL;DR)

1. **현실 판정**: 실현 가능. 단 "녹화 → 의미화 → 문맥 재생" 구조여야. Goal 모드는 V2.
2. **모델**: Qwen3.5-0.8B 단독 X. **Captioner(0.8B) + Grounder(UI-Venus-2B / Qwen3-VL-2B) + Standard Agent(OpenCUA-7B / Fara-7B / Qwen3-VL-8B)** 계층형.
3. **결정적 아키텍처 차별점**: **UIA + OCR + Screenshot hybrid perception** (UFO2 근거). 순수 비전보다 30~60% 빠르고 정확.
4. **재생**: Mode A (faithful) / **Mode B (grounded, V1 핵심)** / Mode C (autonomous, V2).
5. **최적화**: 픽셀 diff 캐싱, UIA/OCR이 후보를 1개로 줄이면 VLM 스킵.
6. **안전**: Dry Run 기본, kill switch, 프로세스 화이트리스트, 커널 AC 게임 out-of-scope.
7. **로드맵**: MVP(P0~P5) 3–4개월, Standard Tier 4–5개월, Autonomous 연구 영역.
