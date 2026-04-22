# macro-bania

> **Context-aware macro via Vision-Language Agents.**
> 녹화 한 번, 재생은 어디서나 — 창 위치·해상도·DPI가 바뀌어도 의미로 다시 찾아 클릭한다.

[![status](https://img.shields.io/badge/status-planning%20v1.0-yellow)]()
[![license](https://img.shields.io/badge/license-Apache--2.0-blue)]()
[![python](https://img.shields.io/badge/python-3.11%2B-green)]()
[![os](https://img.shields.io/badge/os-Windows%2010%20%7C%2011-informational)]()

---

## ⚠️ 중요 경고 (Read me first)

- 이 프로젝트는 **사용자의 컴퓨터에 입력을 주입하는 자동화 도구**다. 잘못 사용하면 데이터 손실·개인정보 유출·계정 정지가 발생할 수 있다.
- **커널 레벨 안티치트(Riot Vanguard / BattlEye / EAC / Hyperion) 탑재 경쟁 온라인 게임에 사용하지 않는다.** 기술적으로 탐지되고 해당 게임의 ToS 위반이다. 앱은 이러한 게임 감지 시 실행을 거부한다.
- 결제·송금·계정 변경 같은 **되돌릴 수 없는 액션**은 휴먼 컨펌을 강제한다. 이 동작을 해제하지 말 것.
- 기본값은 **Dry Run**이다. 실제 입력 주입은 사용자가 명시적으로 활성화해야 한다.
- 녹화 데이터에 비밀번호·카드번호가 포함될 수 있다. PII 스크러버가 기본 활성화되어 있지만 만능이 아니다. 민감한 작업은 녹화하지 말 것.

## 한 줄 정의

좌표를 재생하는 매크로가 아니라, 사용자의 데스크톱 행동을 **의미 있는 스텝(semantic step)**으로 기록하고 재생 시 현재 화면 문맥에서 타깃을 다시 찾아 수행하는 **로컬-퍼스트 GUI 에이전트**.

## 핵심 특징

- **로컬 오프라인**: Qwen3-VL / UI-Venus / OpenCUA 계열 소형 VLM을 소비자 GPU에서 직접 구동. 클라우드 API 없이도 완결.
- **Hybrid Perception**: UIA 트리 + OCR + Screenshot 삼중 인식. 순수 비전 대비 30~60% 빠르고 정확.
- **3개 재생 모드**: Faithful(원본 재생) / **Grounded(의미 기반 재생, V1 핵심)** / Autonomous(자율 목표 수행, V2).
- **계층형 에이전트**: 빠른 Grounder를 타이트 루프에, 비싼 Planner는 에스컬레이션 시에만.
- **안전 기본값**: Dry Run, kill switch, 프로세스 화이트리스트, PII 스크러버, 감사 로그.

## 지원 범위

### ✅ 사용 가능
- 데스크톱 앱 반복 작업 (파일 정리, 엑셀, 웹 리서치)
- 브라우저 기반 단순 폼·퀘스트
- 런처·설정창·메뉴 탐색
- 안티치트 없는 싱글게임/에뮬레이터 메뉴 루프
- 창 위치·해상도·DPI 변경에도 강건한 재생

### ❌ 사용 금지 (V1)
- 커널 안티치트 온라인 게임 (Vanguard/BattlEye/EAC/Hyperion)
- 실시간 전투 / FPS 에임 (VLM 레이턴시로 불가)
- 완전 무인 결제·송금·계정 변경
- 안티치트 우회를 목적으로 한 사용

## 설치 (예정)

> 아직 개발 초기다. Phase 0 Spike 단계에서 수동 설치가 필요하다.

```bash
# 1. Python 3.11+ / uv 설치 (https://github.com/astral-sh/uv)
# 2. 저장소 클론
git clone <repo>
cd macro-bania

# 3. 의존성 설치
uv sync --extra all

# 4. Ollama 설치 + 모델 다운로드
# https://ollama.com/download
ollama pull qwen3-vl:2b

# 5. (Phase 1 이후) CLI 실행
macrobania record --help
```

## 하드웨어 요구사항

| 프로필 | GPU | VRAM | 기본 모델 |
|---|---|---|---|
| Mini | RTX 3060 / 4060 | 8 GB | Qwen3-VL-2B (Q4) |
| Standard | RTX 4070 / 4070S | 12 GB | Qwen3-VL-8B (Q4) 또는 UI-TARS-1.5-7B |
| Pro | RTX 4080 / 4090 | 16–24 GB | Planner+Grounder+Captioner 분리 |

## 프로젝트 상태

- **2026-04-22**: 기획 v1.0 확정 ([PLAN.md](./PLAN.md)). 3-AI(Codex/Claude/Gemini) 독립 계획서 통합본.
- **다음**: P0 Spike — Ollama + Qwen3-VL-2B로 스크린샷 grounding 데모.

전체 로드맵은 [PLAN.md §15](./PLAN.md)를 참조.

## 문서 구조

```
macro-bania/
├── PLAN.md                        ← 마스터 기획서 (v1.0 통합본)
├── README.md                      ← 이 파일
├── claude/PLAN.md                 ← 원본 Claude 초안 (참고)
├── idea/
│   ├── codex/PLAN.md              ← 원본 Codex 초안 (참고)
│   └── gemini/implementation_plan.md  ← 원본 Gemini 초안 (참고)
└── docs/adr/                      ← 중대 결정 기록 (Architecture Decision Record)
```

## 라이선스

Apache License 2.0 — 이 프로젝트가 의존하는 핵심 모델(Qwen 시리즈, UI-Venus, OpenCUA)과 호환되는 개방형 라이선스다.

## 기여

현재 단일 기여자 프로젝트이지만 기획에 대한 피드백·이슈는 환영한다. 기능 구현 기여는 Phase 1(Recorder) 완료 후 공개 오픈.

## 면책

이 도구 사용으로 인한 계정 정지·데이터 손실·법적 책임은 전적으로 사용자에게 있다. 특히 게임·SaaS 서비스의 ToS를 확인하고 사용자 본인 책임으로 운용할 것.
