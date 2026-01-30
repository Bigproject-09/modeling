import operator
from typing import TypedDict, List, Annotated, Any

# 1. 슬라이드 1장(Page)에 대한 정의
class SlideState(TypedDict):
    page_number: int          # 페이지 번호 (나중에 정렬용)
    section: str              # 어느 파트인지 (예: 연구 목표)
    title: str                # 슬라이드 제목
    content: str              # 슬라이드 내용 (글머리 기호 등)
    image_request: str        # 그림 프롬프트 (없으면 빈 문자열)
    image_position: str       # 그림 좌표
    image_path: str           # 생성된 이미지 파일 경로 (초기엔 비어있음)

# 2. 전체 그래프 상태(Cart) 정의
class GraphState(TypedDict):
    # (1) 입력 데이터
    rfp_text: str             # PDF에서 추출한 전체 텍스트
    
    # (2) 분석 결과 (Node 1의 산출물)
    # 덮어쓰기 모드 (분석가는 1명이니까 그냥 덮어쓰면 됨)
    analyzed_json: dict       
    
    # (3) 생성된 슬라이드들 (Node 2~9의 산출물)
    # ★핵심★: 여러 노드가 동시에 값을 넣어도, 리스트에 계속 '추가(add)'해라!
    slides: Annotated[List[SlideState], operator.add]
    
    # (4) 최종 결과물
    final_ppt_path: str       # 최종 저장된 PPT 경로