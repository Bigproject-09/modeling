import os
import sys
import glob
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
from dotenv import load_dotenv

# 1. [경로 설정]
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from utils.document_parsing import extract_text_from_pdf, parse_docx_to_blocks
    from utils.vector_db import search_two_tracks
except ImportError:
    print("❌ 모듈을 찾을 수 없습니다.")
    sys.exit(1)

load_dotenv()

# ==========================================================
# [설정] 테스트할 문서 폴더
TEST_DATA_DIR = r"C:\Users\User\Downloads\df"
# ==========================================================

CACHE_FILE = os.path.join(current_dir, "full_dist_cache.json")

def set_korean_font():
    sns.set_theme(style="whitegrid")
    font_path = 'C:/Windows/Fonts/malgun.ttf'
    if os.path.exists(font_path):
        font_prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = font_prop.get_name()
    else:
        plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False

def collect_full_scores(folder_path):
    if os.path.exists(CACHE_FILE):
        print(f"\n[⚡] 캐시 데이터 로드: {CACHE_FILE}")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    files = glob.glob(os.path.join(folder_path, "*.pdf")) + glob.glob(os.path.join(folder_path, "*.docx"))
    
    if not files:
        print(f"[!] 폴더에 파일이 없습니다: {folder_path}")
        return []

    print(f"\n[*] 총 {len(files)}개 파일로 'DB 전체 완전 검색' 시작...")
    print("    (제한 없이 검색 가능한 모든 유사 문서를 긁어옵니다. 시간이 걸릴 수 있습니다.)")
    
    all_scores = []
    
    for i, file_path in enumerate(files):
        print(f"[{i+1}/{len(files)}] 전체 데이터 스캔 중: {os.path.basename(file_path)}")
        
        full_text = ""
        try:
            if file_path.endswith(".pdf"):
                parsed = extract_text_from_pdf(file_path)
                for page in parsed: full_text += " ".join(page.get("texts", [])) + "\n"
            elif file_path.endswith(".docx"):
                parsed = parse_docx_to_blocks(file_path)
                full_text = str(parsed)
        except Exception:
            continue
            
        if len(full_text.strip()) < 50: continue

        try:
            # 🔥 [핵심] top_k를 5000으로 설정하여 사실상 DB 전체를 가져옴
            # 부처명 "ALL_SCAN"으로 필터링 무력화 -> 전체 검색
            results = search_two_tracks(
                notice_text=full_text,
                ministry_name="ALL_SCAN", 
                top_k_a=0, 
                top_k_b=5000, # <--- 50개가 아니라 5000개! (전부 다)
                score_threshold=0.0
            )
            
            # 필터링 없이 몽땅 수집
            items = results.get('track_b', [])
            for item in items:
                all_scores.append(item['score'])

        except Exception as e:
            print(f"  - 에러: {e}")

    if all_scores:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(all_scores, f)
        print(f"\n[💾] 전체 데이터 저장 완료: {CACHE_FILE}")

    return all_scores

def show_full_statistics(scores):
    if not scores:
        print("[!] 데이터가 없습니다.")
        return
    
    scores = np.array(scores)
    mean_val = np.mean(scores)
    median_val = np.median(scores)
    
    print("\n" + "="*70)
    print(f" 📊 [DB 전체 완전 분석 결과]")
    print("="*70)
    print(f" • 수집된 총 유사도 데이터 수 : {len(scores)} 개")
    print(f" • 전체 평균 점수           : {mean_val:.2f} 점")
    print(f" • 중앙값 (Median)          : {median_val:.2f} 점")
    print("-" * 70)
    print(" 💡 결론 (이 점수를 쓰세요)")
    print(f"   👉 [평균 기준] Score Threshold : {mean_val:.1f}")
    print(f"   👉 [중앙 기준] Score Threshold : {median_val:.1f}")
    print("="*70)

    # 그래프
    plt.figure(figsize=(12, 6))
    sns.histplot(scores, kde=True, bins=100, color='black') # 구간을 100개로 쪼개서 상세하게 봄
    plt.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'Mean ({mean_val:.1f})')
    plt.axvline(median_val, color='yellow', linestyle=':', linewidth=2, label=f'Median ({median_val:.1f})')
    
    plt.title(f'Full Database Similarity Distribution (Top-5000 Limit)')
    plt.xlabel('Similarity Score')
    plt.ylabel('Count')
    plt.legend()
    
    save_path = os.path.join(current_dir, "full_distribution.png")
    plt.savefig(save_path)
    print(f" [Graph] 전체 분포 그래프 저장 완료: {save_path}")

if __name__ == "__main__":
    set_korean_font()
    scores = collect_full_scores(TEST_DATA_DIR)
    show_full_statistics(scores)