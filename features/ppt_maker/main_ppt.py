"""Entrypoint: Extract -> (Split) -> Gemini(섹션별) -> (Merge) -> Gamma(1회)

실행 예시(프로젝트 루트에서):
  python -m features.ppt_maker.main_ppt --source data/ppt_input/sample.pdf --outdir output --outname result.pptx

체크포인트로 Gamma만 재시도:
  set DECK_CHECKPOINT_PATH=output/checkpoints/deck_checkpoint_20260205_123000.json
  python -m features.ppt_maker.main_ppt

  또는
  python -m features.ppt_maker.main_ppt --checkpoint output/checkpoints/deck_checkpoint_....json
"""

import argparse
import os
import json  # ✅ (ADD) checkpoint load 용
import re

from typing import Dict, Any, List

from langgraph.graph import StateGraph, END, START
from dotenv import load_dotenv

from features.ppt_maker.nodes_code.state import GraphState

from features.ppt_maker.nodes_code.extract_text_node import extract_text as extract_text_node
from features.ppt_maker.nodes_code.section_split_node import section_split_node
from features.ppt_maker.nodes_code.section_deck_generation_node import section_deck_generation_node
from features.ppt_maker.nodes_code.merge_deck_node import merge_deck_node
from features.ppt_maker.nodes_code.gamma_generation_node import gamma_generation_node


load_dotenv(override=True)


# === CHECKPOINT-SKIP MODE (REMOVE LATER) ===
def _load_deck_checkpoint(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        deck = json.load(f)
    if not isinstance(deck, dict) or not (deck.get("slides") or []):
        raise RuntimeError(f"체크포인트 deck_json이 비어있습니다: {path}")

    deck = normalize_and_sort_deck(deck)  # ✅ 이 한 줄 추가

    return deck

# === /CHECKPOINT-SKIP MODE (REMOVE LATER) ===
CANON_SECTIONS = [
    "기관 소개",
    "사업 개요",
    "연구 필요성",
    "연구 목표",
    "연구 내용",
    "추진 계획",
    "기대 효과",
    "활용 계획",
    "Q&A",
]

def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _canonicalize_section(raw_section: str, slide_title: str) -> str:
    s = _norm_text(raw_section)
    t = _norm_text(slide_title)

    # 명칭 통일
    s = s.replace("기대 성과", "기대 효과")
    s = s.replace("기대효과", "기대 효과")
    s = s.replace("사업개요", "사업 개요")
    s = s.replace("기관소개", "기관 소개")

    # 이미 정규 섹션이면 그대로
    if s in CANON_SECTIONS:
        return s

    # 섹션/제목 기반 휴리스틱 분류 (너 케이스에 맞춰 강하게 잡음)
    key = f"{s} {t}"

    # 기관 소개
    if any(k in key for k in ["기관", "조직", "역량", "인프라", "협력", "수행기관"]):
        return "기관 소개"

    # 사업 개요
    if any(k in key for k in ["사업 개요", "연구개발의 개요", "과제 개요", "사업 목적", "개요"]):
        return "사업 개요"

    # 연구 목표
    if any(k in key for k in ["연구 목표", "최종 목표", "단계별 목표", "KPI", "성과 지표", "목표"]):
        return "연구 목표"

    # 연구 필요성
    if any(k in key for k in ["필요성", "배경", "중요성", "국내외 현황", "선행 연구", "중복성", "차별성"]):
        return "연구 필요성"

    # 연구 내용
    if any(k in key for k in ["연구 내용", "세부", "핵심기술", "알고리즘", "시스템", "구성도", "아키텍처", "데이터", "모델"]):
        return "연구 내용"

    # 추진 계획
    if any(k in key for k in ["추진", "수행", "일정", "마일스톤", "간트", "추진체계", "역할분담", "방법", "국제공동"]):
        return "추진 계획"

    # 기대 효과
    if any(k in key for k in ["기대 효과", "파급효과", "경제적", "사회적", "효과", "성과 활용"]):
        return "기대 효과"

    # 활용 계획
    if any(k in key for k in ["활용", "사업화", "기술이전", "확산", "라이센싱", "상용화"]):
        return "활용 계획"

    # Q&A
    if any(k in key for k in ["Q&A", "질의", "감사합니다", "문의"]):
        return "Q&A"

    # 못 맞추면 연구 내용으로 귀속(안전)
    return "연구 내용"

def normalize_and_sort_deck(deck: Dict[str, Any]) -> Dict[str, Any]:
    slides: List[Dict[str, Any]] = deck.get("slides") or []
    if not slides:
        return deck

    # 1) 섹션 정규화 + 이미지 정책(사진/AI틱 방지: 도식/표 중심만 true 유지)
    for s in slides:
        sec = s.get("section", "")
        title = s.get("slide_title", "")
        s["section"] = _canonicalize_section(sec, title)

        image_type = _norm_text(s.get("image_type", ""))
        brief = _norm_text(s.get("image_brief_ko", ""))

        # "사진/일러스트" 느낌이거나 애매하면 이미지 요청 끄기
        if any(k in image_type for k in ["사진", "일러스트"]) or any(k in brief for k in ["사진", "실사", "일러스트"]):
            s["image_needed"] = False

        # 도식/표/구성도/그래프 계열만 켜두기(원하면 더 엄격하게 조절 가능)
        if any(k in image_type for k in ["도식", "표", "그래프", "diagram", "block", "system"]):
            # image_brief_ko가 “도형 기반” 지시 없으면 보강(선택)
            if "도형" not in brief and "블록" not in brief and "표" not in brief:
                # 너무 강제하고 싶지 않으면 이 줄은 주석 처리 가능
                pass
        else:
            s["image_needed"] = False

    # 2) 표지/목차를 무조건 앞에 고정
    cover = [x for x in slides if x.get("section") == "표지"]
    agenda = [x for x in slides if x.get("section") == "목차"]
    rest = [x for x in slides if x.get("section") not in ["표지", "목차"]]

    # 3) 섹션 순서대로 그룹핑(섹션 내부 순서는 기존 order 유지)
    def old_order(x):
        try:
            return int(x.get("order", 10**9))
        except:
            return 10**9

    section_rank = {sec: i for i, sec in enumerate(CANON_SECTIONS)}
    rest.sort(key=lambda x: (section_rank.get(x.get("section"), 999), old_order(x)))

    merged = []
    if cover:
        merged.append(cover[0])
    if agenda:
        merged.append(agenda[0])
    merged.extend(rest)

    # 4) 목차 bullets 재생성(요구한 8개 대분류로)
    agenda_items = [
        "기관 소개",
        "사업 개요",
        "연구 목표",
        "연구 필요성",
        "연구 내용",
        "추진 계획",
        "기대 효과",
        "활용 계획",
    ]
    if merged and merged[1:2] and merged[1].get("section") == "목차":
        merged[1]["bullets"] = [f"{i+1}. {t}" for i, t in enumerate(agenda_items)]

    # 5) order 재부여(1..N)
    for i, s in enumerate(merged, 1):
        s["order"] = i

    deck["slides"] = merged
    return deck

def build_graph(*, skip_to_gamma: bool = False):
    """LangGraph 워크플로우 구성

    skip_to_gamma=False:
      START -> extract_text -> split_sections -> make_sections -> merge_deck -> make_pptx -> postprocess -> END

    skip_to_gamma=True:
      START -> make_pptx -> postprocess -> END  (deck_json은 checkpoint로 주입)
    """
    workflow = StateGraph(GraphState)

    # 노드 등록 (공통)
    workflow.add_node("make_pptx", gamma_generation_node)

    if skip_to_gamma:
        # ✅ START 엣지를 명시 (langgraph 버전에 따라 set_entry_point만으로는 부족할 때가 있음)
        workflow.add_edge(START, "make_pptx")
        workflow.add_edge("make_pptx", "postprocess")
        workflow.add_edge("postprocess", END)
        return workflow.compile()

    # 전체 파이프라인 노드 등록
    workflow.add_node("extract_text", extract_text_node)
    workflow.add_node("split_sections", section_split_node)
    workflow.add_node("make_sections", section_deck_generation_node)
    workflow.add_node("merge_deck", merge_deck_node)

    # ✅ START -> extract_text
    workflow.add_edge(START, "extract_text")
    workflow.add_edge("extract_text", "split_sections")
    workflow.add_edge("split_sections", "make_sections")
    workflow.add_edge("make_sections", "merge_deck")
    workflow.add_edge("merge_deck", "make_pptx")
    workflow.add_edge("make_pptx", END)

    return workflow.compile()


def run_ppt_generation(
    *,
    source_path: str = "",
    rfp_text: str = "",
    output_dir: str = "",
    output_filename: str = "",
    gemini_model: str = "",
    gamma_theme: str = "",
    gamma_timeout_sec: int = 0,
    font_name: str = "",
    checkpoint_path: str = "",  # ✅ (ADD)
):
    print("=" * 80)
    print("PPT 자동 생성 시작 (Extract -> Split -> Gemini(섹션별) -> Merge -> Gamma)")
    print("=" * 80)

    # ✅ checkpoint 기능 비활성화 (Gemini 항상 실행)
    checkpoint_path = ""
    skip_to_gamma = False

    # 기본 모드: 입력 자동 선택 로직
    if not source_path and not rfp_text:
        default_dir = os.path.join(os.getcwd(), "data", "ppt_input")
        if os.path.isdir(default_dir):
            pdfs = [f for f in os.listdir(default_dir) if f.lower().endswith(".pdf")]
            if pdfs:
                source_path = os.path.join(default_dir, pdfs[0])
                print(f"[System] 기본 입력 파일 자동 선택: {source_path}")
            else:
                raise RuntimeError(f"입력 PDF가 없습니다: {default_dir}")
        else:
            raise RuntimeError(f"기본 입력 폴더가 없습니다: {default_dir}")

    app = build_graph(skip_to_gamma=skip_to_gamma)

    initial_state: dict = {
        "source_path": source_path,
        "rfp_text": rfp_text,
        **({"output_dir": output_dir} if output_dir else {}),
        **({"output_filename": output_filename} if output_filename else {}),
        **({"gemini_model": gemini_model} if gemini_model else {}),
        **({"gamma_theme": gamma_theme} if gamma_theme else {}),
        **({"gamma_timeout_sec": gamma_timeout_sec} if gamma_timeout_sec else {}),
        **({"font_name": font_name} if font_name else {}),
        "deck_json": {},
        "final_ppt_path": ""
    }

    try:
        final_state = app.invoke(initial_state)

        print("\n" + "=" * 80)
        print("PPT 생성 완료!")
        print("=" * 80)

        if final_state.get("final_ppt_path"):
            print(f"저장 경로: {final_state['final_ppt_path']}")
        else:
            print("PPT 저장 경로가 비어있습니다. Gamma 단계가 실패했을 수 있습니다.")

        deck = final_state.get("deck_json") or {}
        slides = deck.get("slides") or []
        print(f"\n슬라이드 수(설계 기준): {len(slides)}")
        if slides:
            print("슬라이드 미리보기(앞 5개):")
            for i, s in enumerate(slides[:5], 1):
                title = s.get("slide_title") or s.get("title") or "(no title)"
                section = s.get("section") or "(no section)"
                img = s.get("image_needed")
                print(f"  [{i}] [{section}] {title} (image_needed={img})")

        return final_state

    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    parser = argparse.ArgumentParser(description="PPT 자동 생성 (Extract -> Split -> Gemini(섹션별) -> Merge -> Gamma)")
    parser.add_argument("--source", default="", help="입력 파일 경로(pdf/docx/json). 비우면 data/ppt_input에서 자동 선택")
    parser.add_argument("--outdir", default="", help="출력 폴더 (default: ./output)")
    parser.add_argument("--outname", default="", help="출력 pptx 파일명 (default: gamma_<id>.pptx)")
    parser.add_argument("--gemini_model", default="", help="Gemini 모델명 (default: deck_generation_node 내부 기본값)")
    parser.add_argument("--gamma_theme", default="", help="Gamma themeName (선택)")
    parser.add_argument("--gamma_timeout", type=int, default=0, help="Gamma polling timeout seconds (선택)")
    parser.add_argument("--font_name", default="", help="PPTX 후처리 폰트명 (비우면 후처리 안 함)")

    # === CHECKPOINT-SKIP MODE (REMOVE LATER) ===
    parser.add_argument("--checkpoint", default="", help="deck_checkpoint_*.json 경로(있으면 Gemini 스킵하고 Gamma만 실행)")
    # === /CHECKPOINT-SKIP MODE (REMOVE LATER) ===

    args = parser.parse_args()

    # === CHECKPOINT-SKIP MODE (REMOVE LATER) ===
    checkpoint_path = ""
    required_keys = ["GOOGLE_API_KEY", "GAMMA_API_KEY"]
    # 키 체크: 스킵이면 GAMMA만, 아니면 둘 다
    
    # === /CHECKPOINT-SKIP MODE (REMOVE LATER) ===

    missing = [k for k in required_keys if not os.environ.get(k)]
    if missing:
        print(f"환경변수 누락: {', '.join(missing)}")
        print("   .env 파일에 API 키를 설정해주세요.")
        return

    result = run_ppt_generation(
        source_path=args.source,
        output_dir=args.outdir,
        output_filename=args.outname,
        gemini_model=args.gemini_model,
        gamma_theme=args.gamma_theme,
        gamma_timeout_sec=args.gamma_timeout,
        font_name=args.font_name,
        checkpoint_path="",  # ✅ (ADD)
    )

    if result:
        print("\n작업 완료!")
    else:
        print("\n작업 실패")


if __name__ == "__main__":
    main()