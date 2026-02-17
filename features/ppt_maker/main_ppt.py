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
from datetime import datetime

from typing import Dict, Any, List

from langgraph.graph import StateGraph, END, START
from dotenv import load_dotenv

from features.ppt_maker.nodes_code.state import GraphState

from features.ppt_maker.nodes_code.extract_text_node import extract_text as extract_text_node
from features.ppt_maker.nodes_code.section_split_node import section_split_node
from features.ppt_maker.nodes_code.section_deck_generation_node import section_deck_generation_node
from features.ppt_maker.nodes_code.merge_deck_node import merge_deck_node
from features.ppt_maker.nodes_code.gamma_generation_node import gamma_generation_node
from features.ppt_maker.nodes_code.template_render_node import template_render_node
from features.ppt_maker.nodes_code.postprocess_diagrams import postprocess_diagrams_node


load_dotenv(override=True)
TEMPLATE_PATH = (os.environ.get("TEMPLATE_PPTX_PATH") or "").strip()
TEMPLATE_LAYOUT_WHITELIST = [
    x.strip() for x in (os.environ.get("TEMPLATE_LAYOUT_WHITELIST") or "").split(",") if x.strip()
]
BACKGROUND_IMAGE_PATH = ""
BACKGROUND_PROFILE = "basic"
BACKGROUND_BASE_DIR = os.path.join(os.path.dirname(__file__), "background")
REMOVE_BACKGROUND_IMAGE = False


# === CHECKPOINT-SKIP MODE (REMOVE LATER) ===
def _load_deck_checkpoint(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        deck = json.load(f)
    if not isinstance(deck, dict) or not (deck.get("slides") or []):
        raise RuntimeError(f"체크포인트 deck_json이 비어있습니다: {path}")

    deck = normalize_and_sort_deck(deck)  # ✅ 이 한 줄 추가

    return deck


def _save_deck_checkpoint(deck: Dict[str, Any], output_dir: str) -> str:
    outdir = os.path.join(output_dir or "output", "checkpoints")
    os.makedirs(outdir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(outdir, f"deck_prepared_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(deck or {}, f, ensure_ascii=False, indent=2)
    print(f"[CHECKPOINT] prepared deck_json saved: {path}")
    return path


# === /CHECKPOINT-SKIP MODE (REMOVE LATER) ===
CANON_SECTIONS = [
    "기관 소개",
    "연구 개요",
    "연구 필요성",
    "연구 목표",
    "연구 내용",
    "추진 계획",
    "활용방안 및 기대효과",
    "사업화 전략 및 계획",
    "Q&A",
]

def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _canonicalize_section(raw_section: str, slide_title: str) -> str:
    s = _norm_text(raw_section)
    t = _norm_text(slide_title)
    if s in {"표지", "목차", "Q&A"}:
        return s

    # 명칭 통일
    s = s.replace("기대 성과", "활용방안 및 기대효과")
    s = s.replace("기대효과", "활용방안 및 기대효과")
    s = s.replace("활용계획", "활용방안 및 기대효과")
    s = s.replace("사업개요", "연구 개요")
    s = s.replace("사업 개요", "연구 개요")
    s = s.replace("연구개요", "연구 개요")
    s = s.replace("기관소개", "기관 소개")

    # 이미 정규 섹션이면 그대로
    if s in CANON_SECTIONS:
        return s

    # 섹션/제목 기반 휴리스틱 분류 (너 케이스에 맞춰 강하게 잡음)
    key = f"{s} {t}"

    # 연구 목표
    if any(k in key for k in ["연구 목표", "최종 목표", "단계별 목표", "KPI", "성과 지표", "목표"]):
        return "연구 목표"

    if any(k in key for k in ["기관 소개", "기관소개", "수행기관", "주관기관", "참여기관", "수행역량"]):
        return "기관 소개"

    if any(k in key for k in ["연구 개요", "연구개요", "과제 개요", "대상기술", "연구범위", "개요"]):
        return "연구 개요"

    # 연구 필요성
    if any(k in key for k in ["필요성", "배경", "중요성", "국내외 현황", "선행 연구", "중복성", "차별성"]):
        return "연구 필요성"

    # 연구 내용
    if any(k in key for k in ["연구 내용", "세부", "핵심기술", "알고리즘", "시스템", "구성도", "아키텍처", "데이터", "모델"]):
        return "연구 내용"

    # 추진 계획
    if any(k in key for k in ["추진", "수행", "일정", "마일스톤", "간트", "추진체계", "역할분담", "방법", "국제공동"]):
        return "추진 계획"

    if any(k in key for k in ["활용방안", "활용 계획", "기대 효과", "파급효과", "효과", "성과 활용"]):
        return "활용방안 및 기대효과"

    if any(k in key for k in ["사업화 전략", "사업화 계획", "시장 동향", "지식재산권", "표준화", "인증기준", "상용화"]):
        return "사업화 전략 및 계획"

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
        "연구 개요",
        "연구 필요성",
        "연구 목표",
        "연구 내용",
        "추진 계획",
        "활용방안 및 기대효과",
        "사업화 전략 및 계획",
    ]
    if merged and merged[1:2] and merged[1].get("section") == "목차":
        merged[1]["bullets"] = [f"{i+1}. {t}" for i, t in enumerate(agenda_items)]

    # 5) order 재부여(1..N)
    for i, s in enumerate(merged, 1):
        s["order"] = i

    deck["slides"] = merged
    return deck

def build_graph(*, skip_to_gamma: bool = False, prepare_only: bool = False, render_mode: str = "gamma"):
    """LangGraph 워크플로우 구성

    skip_to_gamma=False, prepare_only=False:
      START -> extract_text -> split_sections -> make_sections -> merge_deck -> make_pptx -> postprocess -> END

    skip_to_gamma=True:
      START -> make_pptx -> postprocess -> END  (deck_json은 checkpoint로 주입)

    prepare_only=True:
      START -> extract_text -> split_sections -> make_sections -> merge_deck -> END
    """
    workflow = StateGraph(GraphState)

    # 노드 등록 (공통)
    workflow.add_node("make_pptx", gamma_generation_node)
    workflow.add_node("make_template_pptx", template_render_node)
    workflow.add_node("postprocess", postprocess_diagrams_node)

    if skip_to_gamma:
        start_node = "make_template_pptx" if render_mode == "template" else "make_pptx"
        workflow.add_edge(START, start_node)
        workflow.add_edge(start_node, "postprocess")
        workflow.add_edge("postprocess", END)
        return workflow.compile()

    # 전체 파이프라인 노드 등록
    workflow.add_node("extract_text", extract_text_node)
    workflow.add_node("split_sections", section_split_node)
    workflow.add_node("make_sections", section_deck_generation_node)
    workflow.add_node("merge_deck", merge_deck_node)

    workflow.add_edge(START, "extract_text")
    workflow.add_edge("extract_text", "split_sections")
    workflow.add_edge("split_sections", "make_sections")
    workflow.add_edge("make_sections", "merge_deck")
    if prepare_only:
        workflow.add_edge("merge_deck", END)
        return workflow.compile()
    render_node = "make_template_pptx" if render_mode == "template" else "make_pptx"
    workflow.add_edge("merge_deck", render_node)
    workflow.add_edge(render_node, "postprocess")
    workflow.add_edge("postprocess", END)


    return workflow.compile()


def run_ppt_generation(
    *,
    source_path: str = "",
    rfp_text: str = "",
    output_dir: str = "",
    output_filename: str = "",
    gemini_model: str = "",
    gamma_theme: str = "cx5kqp1h6rwpfkj",
    gamma_timeout_sec: int = 1800,
    font_name: str = "",
    checkpoint_path: str = "",  # ✅ (ADD)
    prepare_only: bool = False,
    render_mode: str = "gamma",
):
    print("=" * 80)
    print("PPT 자동 생성 시작 (Extract -> Split -> Gemini(섹션별) -> Merge -> Gamma)")
    print("=" * 80)

    checkpoint_path = (checkpoint_path or os.environ.get("DECK_CHECKPOINT_PATH") or "").strip()
    skip_to_gamma = bool(checkpoint_path and not prepare_only)

    # 기본 모드: 입력 자동 선택 로직
    if (not skip_to_gamma) and (not source_path) and (not rfp_text):
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

    render_mode = (render_mode or "gamma").strip().lower()
    if render_mode not in {"gamma", "template"}:
        raise RuntimeError(f"unsupported render_mode: {render_mode}")

    effective_gamma_theme = (gamma_theme or "").strip() or "cx5kqp1h6rwpfkj"
    if BACKGROUND_PROFILE == "brown":
        effective_gamma_theme = os.environ.get("BROWN_GAMMA_THEME_ID") or "ijj5bah3e7ekmcw"
    elif BACKGROUND_PROFILE == "basic":
        effective_gamma_theme = os.environ.get("BASIC_GAMMA_THEME_ID") or effective_gamma_theme

    app = build_graph(skip_to_gamma=skip_to_gamma, prepare_only=prepare_only, render_mode=render_mode)

    initial_state: dict = {
        "source_path": source_path,
        "rfp_text": rfp_text,
        **({"output_dir": output_dir} if output_dir else {}),
        **({"output_filename": output_filename} if output_filename else {}),
        "render_mode": render_mode,
        "template_pptx_path": _norm_text(TEMPLATE_PATH),
        "template_layout_whitelist": TEMPLATE_LAYOUT_WHITELIST,
        "template_strict_placeholder_only": True,
        "template_table_as_shape": False,
        "gemini_model": (gemini_model or "gemini-2.5-flash"),
        "gemini_max_retries": int(os.environ.get("GEMINI_MAX_RETRIES") or 2),
        **({"gamma_theme": effective_gamma_theme} if effective_gamma_theme else {}),
        **({"gamma_timeout_sec": gamma_timeout_sec} if gamma_timeout_sec else {}),
        **({"font_name": font_name} if font_name else {}),
        # Internal deck_json is still required for the pipeline, but checkpoint file save is optional.
        "save_checkpoint": False,
        # Enable Gemini diagram image insertion by default (can be overridden by env/state).
        "enable_gemini_diagram_images": True,
        # Image policy: deck-driven text_image slides only (not cover-only).
        "gemini_cover_image_only": False,
        # Fixed policy: cover + expected-effect section only.
        "gemini_image_max_count": 2,
        # Prefer higher-quality image model first.
        "gemini_image_model": "models/gemini-2.5-flash-image",
        # 긴 섹션은 분할 생성(앞/중/뒤 반영)로 정보 손실 완화
        "max_section_chunk_chars": 6000,
        "max_section_chunks_per_section": int(os.environ.get("MAX_SECTION_CHUNKS_PER_SECTION") or 2),
        # 최소 장수 강제는 기본 비활성(부족 시에만 환경값으로 활성)
        "min_slide_count": int(os.environ.get("PPT_MIN_SLIDE_COUNT") or 0),
        # 후처리 스타일 보강
        "postprocess_rewrite_cover": True,
        "force_rewrite_cover": True,
        "postprocess_rewrite_agenda": False,
        "postprocess_style_tables": False,
        "postprocess_trim_ending": True,
        "postprocess_apply_template": False,
        "postprocess_apply_background_image": bool(BACKGROUND_IMAGE_PATH or BACKGROUND_PROFILE),
        "postprocess_background_image_path": BACKGROUND_IMAGE_PATH,
        "postprocess_background_profile": BACKGROUND_PROFILE,
        "postprocess_background_base_dir": BACKGROUND_BASE_DIR,
        "postprocess_remove_background_image": REMOVE_BACKGROUND_IMAGE,
        "deck_json": {},
        "final_ppt_path": ""
    }
    if skip_to_gamma:
        loaded_deck = _load_deck_checkpoint(checkpoint_path)
        initial_state["deck_json"] = loaded_deck
        if not source_path and not rfp_text:
            initial_state["source_path"] = ""
        print(f"[System] checkpoint loaded, skip to gamma: {checkpoint_path}")

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
        if prepare_only and deck:
            _save_deck_checkpoint(deck, output_dir or "output")
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
    parser.add_argument("--outname", default="", help="출력 pptx 파일명 (default: result_<id>.pptx)")
    parser.add_argument("--gemini_model", default="", help="Gemini 모델명 (default: gemini-2.5-flash)")
    parser.add_argument("--gamma_theme", default="cx5kqp1h6rwpfkj", help="Gamma theme name or id (default: cx5kqp1h6rwpfkj)")
    parser.add_argument("--gamma_timeout", type=int, default=1800, help="Gamma polling timeout seconds (default: 1800)")
    parser.add_argument("--font_name", default="", help="PPTX 후처리 폰트명 (default: 미적용, Gamma 테마 폰트 유지)")
    parser.add_argument("--prepare_only", action="store_true", help="Gamma 호출 없이 deck_json까지만 생성/저장")
    parser.add_argument("--render_mode", default="gamma", choices=["gamma", "template"], help="최종 렌더러 선택")

    # === CHECKPOINT-SKIP MODE (REMOVE LATER) ===
    parser.add_argument("--checkpoint", default="", help="deck_checkpoint_*.json 경로(있으면 Gemini 스킵하고 Gamma만 실행)")
    # === /CHECKPOINT-SKIP MODE (REMOVE LATER) ===

    args = parser.parse_args()

    # === CHECKPOINT-SKIP MODE (REMOVE LATER) ===
    checkpoint_path = (args.checkpoint or os.environ.get("DECK_CHECKPOINT_PATH") or "").strip()
    required_keys = ["GOOGLE_API_KEY"] if args.prepare_only else ["GOOGLE_API_KEY", "GAMMA_API_KEY"]
    if args.render_mode == "template":
        required_keys = ["GOOGLE_API_KEY"] if not checkpoint_path else []
    if checkpoint_path and not args.prepare_only and args.render_mode == "gamma":
        required_keys = ["GAMMA_API_KEY"]
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
        checkpoint_path=checkpoint_path,
        prepare_only=args.prepare_only,
        render_mode=args.render_mode,
    )

    if result:
        print("\n작업 완료!")
    else:
        print("\n작업 실패")


if __name__ == "__main__":
    main()
