"""
features.rnd_search 패키지

R&D 과제 유사도 검색 및 분석 기능을 제공합니다.

주요 모듈:
- search_llm: LLM 기반 유사 과제 분석 보고서 생성
- main_search: 유사 과제 검색 실행 로직 (DB 연동 지원)
"""

from .search_llm import summarize_report
from .main_search import main

__all__ = ['summarize_report', 'main']
