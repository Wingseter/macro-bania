# macro-bania Codex Plan

> 작성일: 2026-04-22
> 상태: 실현 가능성 검증 완료, 권장 아키텍처 확정

## 1. 결론

이 프로젝트는 **실현 가능하다**. 다만, 실현 가능한 형태는 단순한 `좌표 매크로`가 아니라 **기록 + 의미화 + 문맥 기반 재생** 구조다.

핵심 결론은 다음과 같다.

- `Qwen3.5-0.8B` 하나로 녹화 해석, UI grounding, 클릭 결정, 복구까지 모두 맡기는 전략은 **MVP 기본안으로는 약하다**.
- 대신 `0.8B는 저비용 captioner/semanticizer`, `2B~7B급은 grounding/
- Windows에서는 **순수 screenshot-only보다 UIA/OCR/vision hybrid**가 훨씬 제품성이 높다.

즉, 가장 좋은 계획은:
verification/agent`로 쓰는 **계층형 구조**가 현실적이다.
- 제품 우선순위는 `완전 자율 게임 봇`이 아니라 `Record -> Semantic Step -> Grounded Replay`다.
1. Windows-native recorder를 만든다.
2. 저수준 이벤트를 semantic step으로 바꾼다.
3. 현재 화면을 보고 step을 다시 수행하는 grounded replay를 완성한다.
4. 그 다음에만 autonomous goal mode와 게임 도메인 적응으로 확장한다.

---

## 2. 현재 코드베이스 기준 진단

현재 저장소의 `data_logger.py`는 다음 상태다.

- `mss`로 화면을 캡처한다.
- `pynput`로 마우스/키보드를 수집한다.
- 클릭/키 입력 시점에만 스크린샷을 저장한다.
- `trace.json`에 이벤트를 순차 저장한다.

이 구현은 출발점으로는 맞지만, 목표 제품과는 거리가 있다.

- 연속 프레임 스트림이 없다.
- window/process/UIA/OCR 정보가 없다.
- `semantic step` 추출이 없다.
- 재생기(player)가 없다.
- precondition/postcondition 검증이 없다.
- 해상도/DPI/창 이동 변화에 강하지 않다.

따라서 지금 코드에서 바로 자율 실행으로 가기보다, **기록 계층부터 다시 정의**하는 것이 맞다.

---

## 3. 외부 근거와 해석

### 3.1 Qwen3.5 small은 충분히 가볍지만, 0.8B 단독 메인 모델은 약하다

- 2026-02 공개된 Qwen 공식 Hugging Face 카드에 따르면 `Qwen3.5-0.8B`는 멀티모달 모델이지만 **intended use가 prototyping, task-specific fine-tuning, research/development**에 가깝다.
- 같은 카드의 Visual Agent 지표에서 `ScreenSpot Pro`는 `Qwen3.5-0.8B = 46.5`, `Qwen3.5-2B = 54.5`다.
- 같은 카드의 일반 agent 지표도 `0.8B`는 `2B`보다 크게 낮다.

해석:

- `0.8B`는 "보이긴 하지만 강하게 행동하는 모델"로 보기 어렵다.
- 특히 고해상도 UI, 작은 아이콘, 비슷한 버튼 다수, 비동기 상태 전이, 실패 복구 루프에서는 더 빨리 무너질 가능성이 높다.
- 따라서 `0.8B`를 **메인 planner/grounder**로 두는 건 권장하지 않는다.

### 3.2 7B급 로컬 computer-use model은 이미 성립했다

- 2025-11 Microsoft Research의 `Fara-7B`는 `Qwen2.5-VL-7B` 기반의 **computer use 전용 7B 모델**이다.
- Microsoft는 이 모델을 **on-device 가능**한 방향으로 소개했고, 학습 데이터도 `145,000 trajectories`, `1 million steps` 규모라고 명시했다.
- 같은 글의 표에서 `Fara-7B`는 `WebVoyager 73.5`, `Online-Mind2Web 34.1`, `DeepShop 26.2`, `WebTailBench 38.4`를 보였다.

해석:

- "소비자급 혹은 온디바이스급 모델로도 computer-use가 된다"는 점은 이미 입증됐다.
- 다만 여기서의 핵심은 **작은 모델 + 좋은 시스템/데이터/행동 포맷**이지, 단순히 파라미터 수만 줄인 것이 아니다.

### 3.3 OpenCUA는 데이터 수집과 로컬 실행 경로를 제공한다

- 2025 공개된 `OpenCUA`는 3개 OS와 200+ apps/websites를 포괄하는 `AgentNet` 데이터셋과 모델군을 공개했다.
- 2026-01 기준 OpenCUA 프로젝트는 `vLLM` 지원을 명시한다.
- `OpenCUA-7B` 카드에는 `ScreenSpot-Pro 50.0`, `OSWorld-Verified 24.3/27.9`(15/50 steps)이 제시되어 있다.

해석:

- 오픈소스 기준에서도 `7B class`는 이미 "로컬 GUI agent의 출발선"이다.
- 더 중요한 점은 **annotation infrastructure + trajectory format + action schema**까지 같이 공개된다는 점이다.

### 3.4 UFO2는 Windows에서 hybrid 설계가 정답에 가깝다고 보여준다

- 2025/2026 공개된 `UFO2: The Desktop AgentOS`는 Windows desktop automation에서 순수 screenshot loop의 한계를 지적한다.
- 특히 `Windows UI Automation (UIA)`와 visual grounding을 결합한 **hybrid control detection pipeline**을 핵심 설계로 둔다.

해석:

- 사용자의 아이디어인 "화면을 계속 보며 문맥 따라 행동"은 맞는 방향이다.
- 하지만 제품성 있게 만들려면 "화면만 보는 것"이 아니라 **UIA + OCR + screenshot**을 같이 써야 한다.
- 이는 지연, 정확도, 실패 복구, 작은 UI 요소 탐지에서 모두 유리하다.

### 3.5 GUI agent 성능은 2026 시점에 빠르게 올라왔다

- `UI-Venus-1.5 Technical Report`는 2026-02 기준 end-to-end GUI agent 계열이 `ScreenSpot-Pro 69.6`, `AndroidWorld 77.6`, `WebVoyager 76.0` 수준까지 도달했다고 주장한다.
- `GUI-Actor`는 2025 NeurIPS에서 coordinate-free grounding과 verifier 조합으로 ScreenSpot-Pro 개선을 보였다.

해석:

- 이 분야는 아직 빠르게 변하지만, **"안 된다"가 아니라 "무엇을 먼저 만들 것이냐"의 문제**로 넘어갔다.
- 따라서 지금은 거대한 frontier closed model을 기다릴 때가 아니라, **작은 로컬 모델이 잘 작동할 수 있는 시스템 구조를 설계할 때**다.

---

## 4. 실현 가능성 판정

### 판정

**예, 실현 가능하다.**

단, 다음 범위에서 시작해야 한다.

### V1에서 가능한 것

- Windows 데스크톱 앱 반복 작업
- 브라우저 기반 반복 작업
- 런처/설정창/메뉴 탐색
- 해상도나 창 위치가 바뀌어도 semantic target을 다시 찾는 grounded replay
- anti-cheat가 없는 게임/에뮬레이터 UI의 메뉴형 반복 작업

### V1에서 제외해야 하는 것

- Riot Vanguard, BattlEye, EAC 등 anti-cheat가 있는 온라인 게임 자동화
- 실시간 전투, FPS, 짧은 reaction loop가 필요한 게임 플레이
- 결제, 송신, 계정 변경 같은 irreversible action의 완전 무인 처리
- "녹화 없이 처음 보는 게임 UI를 완전 자율로 끝까지 해결" 같은 고난도 long-horizon autonomy

### 사용자 아이디어에 대한 직접 판단

`"녹화하면 VLM이 화면을 계속 주시하면서 변경 사항을 기록하고, Play 하면 Action을 수행"`하는 구조는 맞다.  
다만 다음처럼 바꿔야 현실적이다.

- 기록 시점: VLM이 실시간 추론을 계속 돌 필요는 없다.
- 기록 시점에는 **raw trace를 최대한 풍부하게 저장**해야 한다.
- 의미화는 **사후 batch 처리**로 돌리는 것이 비용과 정확도 면에서 더 낫다.
- 재생 시점에만 grounding/verifier를 사용해 현재 화면에 맞춰 action을 다시 찾게 해야 한다.

즉, 최고의 구조는 `record-time heavy logging + post-process semanticization + play-time grounding`이다.

---

## 5. 권장 제품 정의

### 제품 한 줄 정의

**"좌표를 재생하는 매크로가 아니라, 사용자의 데스크톱 행동을 semantic step으로 기록하고 현재 화면 문맥에 맞게 다시 수행하는 로컬 GUI agent."**

### V1 사용자 경험

1. 사용자가 `Record`를 누른다.
2. 시스템이 화면/입력/UIA/OCR/window metadata를 기록한다.
3. 녹화가 끝나면 semantic step으로 자동 변환한다.
4. 사용자는 step을 검토/수정한다.
5. `Play`를 누르면 시스템이 현재 화면에서 target을 다시 찾고 step을 수행한다.
6. step마다 precondition/postcondition을 검증한다.

### V1 핵심 가치

- 창 위치, 해상도, DPI가 달라도 덜 깨진다.
- 버튼 레이블, 아이콘, 문맥을 기반으로 재생한다.
- 좌표 매크로보다 유지보수가 훨씬 쉽다.
- 클라우드 API 없이도 돌아갈 수 있다.

---

## 6. 권장 시스템 아키텍처

## 6.1 레이어

### A. Recorder

기록 시 저장해야 할 것:

- 연속 화면 프레임
- raw mouse/keyboard event
- window title / process / hwnd
- Windows UIA tree snapshot
- OCR text blocks
- DPI / monitor / resolution metadata

### B. Trace Builder

저장된 raw trace를 semantic step으로 변환한다.

- 이벤트를 시간 간격 기준으로 묶는다.
- step 전후 frame을 잡는다.
- target crop을 만든다.
- 자연어 caption, target description, precondition, postcondition을 생성한다.

### C. Grounded Player

재생 시 다음 루프를 돈다.

1. 현재 화면 캡처
2. precondition 확인
3. UIA/OCR로 후보 좁히기
4. VLM grounder로 최종 위치 선택
5. 클릭/타이핑/스크롤 실행
6. postcondition 확인
7. 실패 시 retry 또는 planner escalation

### D. Planner

V1의 기본은 아니다.  
Grounded replay에서 반복 실패 시에만 limited planner를 호출한다.

---

## 6.2 가장 중요한 설계 원칙

- **Local-first**: 기본은 로컬 추론
- **Hybrid perception**: UIA + OCR + vision
- **Step-first**: action을 raw event가 아니라 semantic step으로 다룬다
- **Verification-first**: pre/postcondition 검증이 기본
- **Human override**: 언제든 중단 가능해야 한다
- **Model swapability**: OpenAI-compatible API로 모델 교체 가능해야 한다

---

## 7. 모델 전략

## 7.1 최종 추천

사용자가 생각한 `Qwen3.5-0.8B`는 **채택 가능하지만 주역이 아니라 보조역**으로 쓰는 게 최선이다.

### 권장 역할 분담

| 역할 | 권장 모델 | 이유 |
|---|---|---|
| Captioner / Step Semanticizer | `Qwen3.5-0.8B` | 저비용, 로컬 batch 처리 적합 |
| MVP Grounder / Verifier | `Qwen3.5-2B` 또는 `Qwen3-VL-2B` | 0.8B보다 GUI 성능이 의미 있게 높음 |
| Standard Agent | `OpenCUA-7B` 또는 `Fara-7B` | computer-use 전용 학습/행동 포맷 |
| 미래용 도메인 적응 | 사용자 trace 기반 LoRA | 특정 UI/게임에 대한 회복력 증가 |

### 추천 이유

- `0.8B`: 가볍지만 primary action model로는 약함
- `2B`: 여전히 로컬 친화적이면서 grounding 성능이 낫다
- `7B`: 실제 computer-use 연구가 본격적으로 성립한 구간

## 7.2 하드웨어 티어 제안

아래는 **소스 기반 추론**이다. 모든 수치는 quantization, context length, serving engine에 따라 달라진다.

### Mini

- 대상: `RTX 3060/4060 8GB`급
- 역할: Recorder + Step semanticization + simple grounded replay
- 모델: `Qwen3.5-0.8B`, `Qwen3.5-2B`

### Standard

- 대상: `RTX 4070/4070S 12GB`급 이상
- 역할: 실사용 grounded replay
- 모델: `Qwen3.5-2B` + `OpenCUA-7B` 또는 `Fara-7B`

### Pro

- 대상: `RTX 4080/4090 16GB~24GB`
- 역할: planner/grounder 분리, 더 긴 history, 더 안정적인 verifier
- 모델: `7B class agent + 2B class helper`

---

## 8. 데이터 스키마 권장안

## 8.1 Recording

- recording id
- task name
- created_at
- OS / resolution / DPI / monitor
- target process / window regex
- frame count / event count / duration

## 8.2 Raw Event

- ts_ns
- kind: mouse move/down/up, key down/up, scroll, text input
- payload: x/y, button, scan code, vk, text, delta
- hwnd / window title / process

## 8.3 Frame

- timestamp
- image path
- changed region metadata
- OCR blocks
- UIA snapshot id

## 8.4 Semantic Step

- frame_before / frame_after
- raw_event_ids
- action type
- target description
- target crop
- hint bbox
- precondition
- postcondition
- confidence

---

## 9. 재생 모드 정의

### Mode A. Faithful Replay

- 기록된 action을 최대한 그대로 재생
- 단, precondition 검증은 한다
- 디버깅과 baseline 비교용

### Mode B. Grounded Replay

- V1의 핵심
- target description을 기반으로 현재 화면에서 다시 target을 찾는다
- 창 이동/DPI/UI 이동에 강해야 한다

### Mode C. Goal Mode

- 장기 목표
- 녹화 없이 자연어 목표만으로 실행
- long-horizon planner와 memory가 필요하다

---

## 10. 구현 로드맵

## Phase 0. Recorder 재정의

기간: 1주

목표:

- 현재 `data_logger.py`를 recorder prototype 수준으로 승격
- 클릭 시점 스냅샷이 아니라 연속 trace로 바꾸기
- trace schema 고정

완료 조건:

- 10분 녹화 동안 프레임/이벤트 유실 없이 저장
- 해상도, DPI, 창 정보가 trace에 남음

## Phase 1. Trace Viewer + Semanticizer

기간: 1~2주

목표:

- raw trace를 step 후보로 묶기
- `Qwen3.5-0.8B`로 caption/target description 생성
- 사용자가 수정 가능한 viewer 제공

완료 조건:

- 샘플 20개 녹화 중 step caption의 수동 수정량이 낮음

## Phase 2. Grounded Replay MVP

기간: 2주

목표:

- `Qwen3.5-2B` 또는 `Qwen3-VL-2B` 기반 grounding/verifier 연결
- precondition/postcondition 루프 구현
- dry-run overlay 구현

완료 조건:

- 창 위치와 해상도가 달라도 반복 작업을 성공적으로 재생

## Phase 3. Standard Agent Tier

기간: 2~3주

목표:

- `OpenCUA-7B` 또는 `Fara-7B` 연결
- retry/escalation/planner fallback 추가
- 실패 recovery 개선

완료 조건:

- 긴 작업에서도 retry 후 복구 가능

## Phase 4. Safety + Productization

기간: 1~2주

목표:

- process allowlist
- global kill switch
- human checkpoint
- audit log
- PII masking

완료 조건:

- 비개발자 테스트 가능 수준의 안전장치 확보

## Phase 5. Domain Adaptation

기간: 이후

목표:

- 특정 앱/게임/업무 도메인별 LoRA
- retrieval memory
- autonomous goal mode

---

## 11. KPI

- recorder 유실률: `< 1%`
- semantic step 수동 수정 후 승인율: `>= 85%`
- grounded replay 성공률: `>= 80%`
- moved/resized window에서 재생 성공률: `>= 75%`
- 1시간 연속 동작 crash: `0`
- kill switch 반응: `즉시`

---

## 12. 주요 리스크와 대응

### R1. anti-cheat / ToS

위험:

- 온라인 게임 자동화는 기술보다 정책 리스크가 더 크다.

대응:

- V1 문서와 UI에 명시적 경고
- anti-cheat 게임은 공식 지원 범위에서 제외
- 회피/우회 기능은 만들지 않음

### R2. 작은 UI 요소와 고해상도 HUD

위험:

- 0.8B/2B는 작은 타깃에 약할 수 있다.

대응:

- crop-based second look
- OCR/UIA 후보 결합
- 실패 시 7B tier fallback

### R3. 비동기 상태와 loading

위험:

- 너무 빨리 클릭하거나, 기다려야 할 순간을 못 알아챔

대응:

- verifier 기반 `wait-until`
- spinner/dialog detector
- postcondition 실패 시 retry

### R4. 개인정보 입력

위험:

- 민감정보가 trace나 자동 입력에 남을 수 있다.

대응:

- 기본 마스킹
- critical point에서 human confirmation
- audit log 분리

### R5. 작은 모델의 looping / hallucination

위험:

- 공식 Qwen 문서도 2B의 thinking loop 위험을 언급한다.

대응:

- constrained JSON output
- short horizon planning
- max retry / max step
- verifier 분리

---

## 13. 이 저장소에서 바로 해야 할 일

1. `data_logger.py`를 단일 파일 실험 스크립트에서 `capture`, `input`, `storage`, `recording` 모듈 구조로 분리한다.
2. `SQLite + frames/ + OCR/UIA snapshot` 기반 trace schema를 먼저 고정한다.
3. CLI 기준으로 `record`, `inspect`, `semanticize`, `play --dry-run` 네 개 명령을 만든다.
4. 모델 서버는 초기에 OpenAI-compatible 인터페이스로 추상화한다.
5. 첫 실험은 `Qwen3.5-2B grounded replay`로 하고, 그 다음 `OpenCUA-7B`를 붙인다.

---

## 14. 최종 추천안

### 내가 지금 바로 채택할 기본안

- Recorder: Windows-native continuous recorder
- Semanticizer: `Qwen3.5-0.8B`
- Grounder/Verifier MVP: `Qwen3.5-2B`
- Standard Agent: `OpenCUA-7B`
- Perception: `UIA + OCR + screenshot`
- Scope: 웹/데스크톱 반복 작업, anti-cheat 없는 메뉴형 UI

### 내가 채택하지 않을 기본안

- `Qwen3.5-0.8B` 단일 모델 올인
- screenshot-only pure vision
- 녹화 없이 바로 autonomous game quest agent부터 시작
- anti-cheat 환경 지원

---

## 15. 참고 소스

- Qwen/Qwen3.5-0.8B model card, Hugging Face, 확인일 2026-04-22  
  https://huggingface.co/Qwen/Qwen3.5-0.8B

- Qwen/Qwen3.5-2B model card, Hugging Face, 확인일 2026-04-22  
  https://huggingface.co/Qwen/Qwen3.5-2B

- Qwen3.5 official blog / Alibaba Cloud community mirror, 확인일 2026-04-22  
  https://www.alibabacloud.com/blog/602894

- Fara-7B: An Efficient Agentic Model for Computer Use, Microsoft Research Blog, 2025-11, 확인일 2026-04-22  
  https://www.microsoft.com/en-us/research/blog/fara-7b-an-efficient-agentic-model-for-computer-use/

- OpenCUA project page, 확인일 2026-04-22  
  https://opencua.xlang.ai/

- OpenCUA-7B model card, 확인일 2026-04-22  
  https://huggingface.co/xlangai/OpenCUA-7B

- UFO2: The Desktop AgentOS, arXiv HTML, 확인일 2026-04-22  
  https://arxiv.org/html/2504.14603v2

- UI-Venus-1.5 Technical Report, arXiv HTML, 확인일 2026-04-22  
  https://arxiv.org/html/2602.09082v1

- GUI-Actor: Coordinate-Free Visual Grounding for GUI Agents, NeurIPS 2025 poster page, 확인일 2026-04-22  
  https://neurips.cc/virtual/2025/poster/119841
