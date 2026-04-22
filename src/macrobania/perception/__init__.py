"""Hybrid Perception — UIA + OCR + Screenshot (Phase 1+).

PLAN.md §9.2 에 따라 VLM 호출 전 후보를 좁히는 matcher를 제공한다.

예정 구현:
  - :mod:`uia`      — pywinauto / uiautomation 래퍼
  - :mod:`ocr`      — RapidOCR 래퍼
  - :mod:`matcher`  — UIA/OCR 후보 → Grounder 입력 목록
"""
