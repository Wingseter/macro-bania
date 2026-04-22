# ADR-0001: 3-AI 계획서 통합 결과 채택

- 날짜: 2026-04-22
- 상태: Accepted
- 작성자: (single maintainer)
- 관련 문서: [PLAN.md](../../PLAN.md), `claude/PLAN.md`, `idea/codex/PLAN.md`, `idea/gemini/implementation_plan.md`

## 배경

3개의 AI(Codex, Claude, Gemini)가 동일 주제 — "소형 VLM 기반 문맥 인식 매크로" — 에 대해 **독립적으로** 계획서를 작성했다. 각자 강약점이 다르고 일부 주장은 충돌했다. 단일 마스터 플랜을 확정하기 위해 차이를 추적하고 결정을 남긴다.

## 결정

**Claude 초안을 전체 뼈대로 채택**하고, 여기에 다음을 병합한다.

| 출처 | 병합 항목 | 이유 |
|---|---|---|
| Codex | UIA + OCR + Screenshot 하이브리드 인식 | UFO2 논문 근거로 순수 비전보다 실측 우위 |
| Codex | Fara-7B, OpenCUA-7B 구체 추천 | 공식 벤치마크와 computer-use 전용 학습 |
| Codex | CLI 4명령(`record/inspect/semanticize/play`) | 재사용·스크립팅에 유리 |
| Gemini | 픽셀 diff 기반 VLM 호출 캐싱 | GPU 부하 감소, 실사용 최적화 |
| Gemini | 상태전이 그래프(State Machine) 슬롯 | V2 autonomous 모드에서 활용 여지 |

**거부**

| 출처 | 항목 | 이유 |
|---|---|---|
| Gemini | "안티치트 우회용 자연스러운 커서 곡선" | 윤리·법적. Codex/Claude 모두 out-of-scope 입장 |
| Gemini | CustomTkinter | PySide6가 생산성·성숙도 면에서 우위 |
| Gemini | "Qwen3.5-0.8B 단독으로 충분" | Codex 벤치마크로 반박됨 (ScreenSpot-Pro 46.5) |

## 결과

- 마스터 플랜: `PLAN.md` v1.0
- 원본 3종은 참조·투명성 목적으로 보존: `claude/`, `idea/codex/`, `idea/gemini/`
- 모델 전략: **Captioner(Qwen3.5-0.8B) + Grounder(UI-Venus-1.5-2B or Qwen3-VL-2B) + Standard Agent(OpenCUA-7B / Fara-7B / Qwen3-VL-8B)** 계층형
- 재생 모드: Mode A(Faithful) / **Mode B(Grounded, V1 핵심)** / Mode C(Autonomous, V2)
- 인식: UIA + OCR + Screenshot hybrid (Codex 채택)
- 최적화: 픽셀 diff 캐싱 (Gemini 채택)

## 대안

1. **Codex만 채택**: 분석은 탁월했으나 Mode A/B/C 같은 제품 프레임이 약해 UX 관점 부족.
2. **Claude만 채택**: 구조는 완벽했으나 hybrid perception을 놓쳤고 모델 후보가 Qwen 일변도.
3. **Gemini만 채택**: 너무 간결하고 안티치트 이슈를 과소평가.

하이브리드(본 결정)가 각 장점을 모두 흡수하면서 약점을 상호 보완한다.

## 후속 영향

- 다음 ADR 후보: `0002-hybrid-perception-architecture.md` (UIA/OCR/Vision 융합 상세), `0003-model-tier-default.md` (Grounder 기본값 벤치 결과), `0004-recording-storage-schema.md` (SQLite + WebP + UIA/OCR snapshot 최종 포맷)
- PLAN.md §15 로드맵 적용. Phase 0 Spike는 ADR-0003 근거 수립 용도.
