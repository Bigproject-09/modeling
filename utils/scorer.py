import os
import sys
import glob
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
from dotenv import load_dotenv

# [핵심 수정] 프로젝트 루트(modeling 폴더)를 파이썬 경로에 강제 추가
current_dir = os.path.dirname(os.path.abspath(__file__))  # utils 폴더
project_root = os.path.dirname(current_dir)               # modeling 폴더
if project_root not in sys.path:
    sys.path.append(project_root)

# 이제 modeling 폴더가 기준이 되므로 utils 패키지를 찾을 수 있습니다.
try:
    from utils.document_parsing import extract_text_from_pdf, parse_docx_to_blocks
    from utils.vector_db import search_two_tracks
except ImportError as e:
    # 혹시나 해서 예외 처리 추가
    print(f"❌ 모듈 로딩 실패: {e}")
    print(f"   (현재 경로: {current_dir})")
    print(f"   (프로젝트 루트: {project_root})")
    sys.exit(1)

load_dotenv()

# [설정] 테스트할 문서들이 있는 폴더 경로 (본인 경로에 맞게 수정 필요!)
TEST_DATA_DIR = r"C:\Users\User\Downloads\df"
CACHE_FILE = os.path.join(current_dir, "analysis_cache.json") # 캐시 파일 위치도 명확하게

def set_korean_font():
    """한글 폰트(맑은 고딕) 강제 설정"""
    sns.set_theme(style="ticks")
    font_path = 'C:/Windows/Fonts/malgun.ttf'
    if os.path.exists(font_path):
        font_prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = font_prop.get_name()
    else:
        plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False

def get_all_scores(folder_path):
    if os.path.exists(CACHE_FILE):
        print(f"\n[⚡] 캐시 파일 발견! ({CACHE_FILE})")
        print("    무거운 분석 과정을 건너뛰고 저장된 데이터를 불러옵니다...")
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            print(f"    -> {len(cached_data)}개의 점수 데이터를 로드했습니다. (완료)")
            return cached_data
        except Exception as e:
            print(f"    [!] 캐시 로드 실패: {e}. 다시 분석합니다.")

    files = glob.glob(os.path.join(folder_path, "*.pdf")) + glob.glob(os.path.join(folder_path, "*.docx"))
    
    if not files:
        print(f"[!] '{folder_path}' 폴더에 파일이 없습니다.")
        return []

    print(f"\n[*] 총 {len(files)}개 파일에 대해 분석을 시작합니다 (첫 실행이라 시간이 좀 걸립니다)...")
    
    all_top_scores = []
    
    for i, file_path in enumerate(files):
        print(f"[{i+1}/{len(files)}] 분석 중: {os.path.basename(file_path)}")
        
        full_text = ""
        try:
            if file_path.endswith(".pdf"):
                parsed = extract_text_from_pdf(file_path)
                for page in parsed:
                    full_text += " ".join(page.get("texts", [])) + "\n"
            elif file_path.endswith(".docx"):
                parsed = parse_docx_to_blocks(file_path)
                full_text = str(parsed)
        except Exception as e:
            print(f"  - 파싱 에러: {e}")
            continue
            
        if len(full_text.strip()) < 100:
            continue

        try:
            results = search_two_tracks(
                notice_text=full_text,
                ministry_name="해양수산부", 
                top_k_a=5,
                top_k_b=0,
                score_threshold=0.0
            )
            for item in results.get('track_a', []):
                all_top_scores.append(item['score'])
                
        except Exception as e:
            print(f"  - 검색 에러: {e}")

    if all_top_scores:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(all_top_scores, f)
        # [수정] 역슬래시 제거하여 SyntaxWarning 해결
        print(f"\n[💾] 분석 결과 저장 완료: {CACHE_FILE} (다음 실행부터는 즉시 실행됩니다)")

    return all_top_scores

def plot_distribution(scores, p5, p10, mean_val):
    if len(scores) < 2:
        print("[!] 데이터가 부족하여 그래프를 그릴 수 없습니다.")
        return

    fig, ax = plt.subplots(figsize=(12, 7))

    sns.histplot(scores, bins=20, kde=True,
                 color='#4A69BD', edgecolor='white', linewidth=1, alpha=0.6,
                 line_kws={'color': '#1E3799', 'linewidth': 3}, ax=ax)

    ax.axvline(mean_val, color='gray', linestyle=':', linewidth=2)
    ax.axvline(p10, color='#F6B93B', linestyle='--', linewidth=2)
    ax.axvline(p5, color='#E55039', linestyle='-', linewidth=3)

    max_score = np.max(scores)
    x_limit = max_score + 5 if max_score < 95 else 100
    ax.axvspan(p5, x_limit, color='#E55039', alpha=0.1, zorder=0)

    y_max = ax.get_ylim()[1]
    ax.annotate(f'★추천 임계값 ({p5:.1f}점)\n(상위 95% 구간)',
                xy=(p5, y_max * 0.7), 
                xytext=(p5 + (x_limit-p5)/2, y_max * 0.8), 
                arrowprops=dict(facecolor='#E55039', shrink=0.05, alpha=0.8),
                fontsize=12, fontweight='bold', color='#E55039',
                ha='center', va='bottom',
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#E55039", alpha=0.9))

    stats_text = (
        f" 분석 요약\n"
        f"━━━━━━━━━━━━━━\n"
        f"• 표본 수 (N): {len(scores)}건\n"
        f"• 평균 점수: {mean_val:.2f}\n"
        f"• 표준편차: {np.std(scores):.2f}\n"
        f"• 최소/최대: {np.min(scores):.1f} / {np.max(scores):.1f}"
    )
    
    ax.text(0.02, 0.95, stats_text, transform=ax.transAxes,
            fontsize=11, verticalalignment='top', 
            fontfamily='Malgun Gothic',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#F8F9FA', edgecolor='#BDC3C7', alpha=0.9))

    sns.despine(top=True, right=True)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    ax.set_xlim(np.min(scores)-2, x_limit)

    ax.set_title('해양 R&D 유사 과제 매칭 점수 분포 및 임계값 설정 근거', 
                 fontsize=18, fontweight='bold', pad=20, color='#2C3A47')
    ax.set_xlabel('유사도 점수 (Cosine Similarity, 0~100)', fontsize=13, fontweight='bold', labelpad=10)
    ax.set_ylabel('빈도 (Frequency)', fontsize=13, fontweight='bold', labelpad=10)

    plt.tight_layout()
    # 저장 경로를 현재 폴더(utils)로 지정
    save_path = os.path.join(current_dir, "score_distribution_final.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"\n[*] 최종 그래프 저장 완료: {save_path}")

def calculate_statistics(scores):
    if not scores:
        print("[!] 수집된 점수가 없습니다.")
        return
    
    scores = np.array(scores)
    mean_val = np.mean(scores)
    p5 = np.percentile(scores, 5)   
    p10 = np.percentile(scores, 10) 
    
    print("\n" + "="*50)
    print(" [분석 완료]")
    print(f" - 평균: {mean_val:.2f} / 추천 임계값(95%): {p5:.2f}")
    print("="*50)
    
    plot_distribution(scores, p5, p10, mean_val)

if __name__ == "__main__":
    set_korean_font()
    scores = get_all_scores(TEST_DATA_DIR)
    calculate_statistics(scores)