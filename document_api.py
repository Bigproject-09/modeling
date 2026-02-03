#document_api.py
import requests
import xml.etree.ElementTree as ET
import pymysql
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from config import API_KEY, BASE_URL, DB_CONFIG


def get_text(item, tag):
    el = item.find(tag)
    if el is None or el.text is None:
        return ""
    return el.text.strip()

def safe(v):
    return v if v is not None else ""


def build_session():
    session = requests.Session()
    retry = Retry(
        total=5,
        connect=5,
        read=3,
        backoff_factor=0.7,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "bizinfo-ingest/1.0"})
    return session


def lcategory_is_tech(lcat):
    if not lcat:
        return False
    parts = [p.strip() for p in lcat.replace("|", "@").split("@")]
    return "기술" in parts


def fetch_page(session, api_key, page_index=1, page_unit=100):
    params = {
        "crtfcKey": api_key,
        "dataType": "rss",
        "pageIndex": page_index,
        "pageUnit": page_unit,
        "searchCnt": page_unit,
    }

    r = session.get(BASE_URL, params=params, timeout=(5, 30))
    r.raise_for_status()

    root = ET.fromstring(r.text)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS channel 없음")

    raw_items = channel.findall("item")
    raw_count = len(raw_items)

    tot_cnt = None
    rows = []

    for it in raw_items:
        seq = get_text(it, "seq")
        if not seq:
            continue

        lcat = get_text(it, "lcategory")
        if not lcategory_is_tech(lcat):
            continue

        if tot_cnt is None:
            tc = get_text(it, "totCnt")
            if tc and tc.isdigit():
                tot_cnt = int(tc)

        rows.append({
            "seq": seq,
            "title": get_text(it, "title"),
            "link": get_text(it, "link"),
            "author": get_text(it, "author"),
            "exc_instt_nm": get_text(it, "excInsttNm"),
            "description": get_text(it, "description"),
            "pub_date": get_text(it, "pubDate"),
            "reqst_dt": get_text(it, "reqstDt"),
            "trget_nm": get_text(it, "trgetNm"),
            "print_flpth_nm": get_text(it, "printFlpthNm"),
            "print_file_nm": get_text(it, "printFileNm"),
            "flpth_nm": get_text(it, "flpthNm"),
            "file_nm": get_text(it, "fileNm"),
            "hash_tags": get_text(it, "hashtags"),
        })

    return raw_count, tot_cnt, rows


def parse_hashtags(hash_tags_str):
    """
    해시태그 문자열 파싱
    예: "AI,빅데이터,클라우드" → ["AI", "빅데이터", "클라우드"]
    """
    if not hash_tags_str:
        return []
    
    # 쉼표로 split하고 빈 문자열 제거
    tags = [tag.strip() for tag in hash_tags_str.split(",") if tag.strip()]
    return tags


def parse_files(print_file_nm_str, print_flpth_nm_str):
    """
    파일명, 파일경로 문자열 파싱
    예: "파일1.hwp@파일2.pdf" + "경로1@경로2" 
        → [("파일1.hwp", "경로1"), ("파일2.pdf", "경로2")]
    """
    if not print_file_nm_str or not print_flpth_nm_str:
        return []
    
    # @ 구분자로 split
    file_names = [f.strip() for f in print_file_nm_str.split("@") if f.strip()]
    file_paths = [p.strip() for p in print_flpth_nm_str.split("@") if p.strip()]
    
    if len(file_names) != len(file_paths):
        print(f"⚠️ 파일명({len(file_names)})과 경로({len(file_paths)}) 개수 불일치")
        return []
    
    return list(zip(file_names, file_paths))


def ingest_to_db(api_key, page_unit=100, max_pages=None):
    session = build_session()
    conn = pymysql.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cursor:
            page = 1
            tot_cnt_seen = None
            inserted = 0
            seen_seq = set()

            while True:
                raw_count, tot_cnt, rows = fetch_page(
                    session,
                    api_key=api_key,
                    page_index=page,
                    page_unit=page_unit,
                )

                if tot_cnt_seen is None and tot_cnt is not None:
                    tot_cnt_seen = tot_cnt

                print(
                    f"page={page} raw_items={raw_count} "
                    f"tech_items={len(rows)} totCnt={tot_cnt_seen}"
                )

                if raw_count == 0:
                    break

                for notice in rows:
                    seq = notice["seq"]
                    if seq in seen_seq:
                        continue
                    seen_seq.add(seq)

                    cursor.execute(
                        "SELECT 1 FROM project_notices WHERE seq = %s",
                        (seq,),
                    )
                    if cursor.fetchone():
                        continue

                    # ✅ 1. project_notices 테이블에 기본 정보만 INSERT
                    sql = """
                        INSERT INTO project_notices (
                            seq, title, link, author, exc_instt_nm,
                            description, pub_date, reqst_dt, trget_nm
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """

                    cursor.execute(
                        sql,
                        (
                            safe(seq),
                            safe(notice.get("title")),
                            safe(notice.get("link")),
                            safe(notice.get("author")),
                            safe(notice.get("exc_instt_nm")),
                            safe(notice.get("description")),
                            safe(notice.get("pub_date")),
                            safe(notice.get("reqst_dt")),
                            safe(notice.get("trget_nm")),
                        ),
                    )

                    notice_id = cursor.lastrowid

                    # ✅ 2. notice_files 테이블에 파일 정보 INSERT
                    print_file_nm_str = safe(notice.get("print_file_nm"))
                    print_flpth_nm_str = safe(notice.get("print_flpth_nm"))
                    file_nm_str = safe(notice.get("file_nm"))
                    flpth_nm_str = safe(notice.get("flpth_nm"))

                    # 🔥 디버깅 로그
                    print(f"\n{'='*60}")
                    print(f"🔍 공고 seq={seq} 파일 정보")
                    print(f"{'='*60}")
                    print(f"📌 제목: {notice.get('title')[:50]}...")
                    print(f"📄 본문파일명: [{print_file_nm_str}]")
                    print(f"📂 본문경로: [{print_flpth_nm_str}]")
                    print(f"📎 첨부파일명: [{file_nm_str}]")
                    print(f"📂 첨부경로: [{flpth_nm_str}]")

                    print_files = parse_files(print_file_nm_str, print_flpth_nm_str)
                    attach_files = parse_files(file_nm_str, flpth_nm_str)
                    all_files = print_files + attach_files

                    print(f"✅ 본문파일: {len(print_files)}개")
                    print(f"✅ 첨부파일: {len(attach_files)}개")
                    print(f"✅ 총 파일: {len(all_files)}개")
                    
                    if all_files:
                        for i, (fname, fpath) in enumerate(all_files, 1):
                            print(f"   파일 {i}: {fname}")
                    else:
                        print(f"   ⚠️ 파일 없음")
                    
                    for file_name, file_path in all_files:
                        sql_file = """
                            INSERT INTO notice_files (
                                notice_id, print_file_nm, print_flpth_nm
                            )
                            VALUES (%s, %s, %s)
                        """
                        cursor.execute(sql_file, (notice_id, file_name, file_path))

                    # ✅ 3. notice_hashtags 테이블에 해시태그 INSERT
                    hash_tags_str = safe(notice.get("hash_tags"))
                    
                    # 🔥 해시태그 디버깅 로그 추가
                    print(f"🏷️  원본 해시태그: [{hash_tags_str}]")
                    
                    hashtags = parse_hashtags(hash_tags_str)
                    
                    print(f"✅ 파싱된 해시태그: {len(hashtags)}개")
                    if hashtags:
                        for i, tag in enumerate(hashtags, 1):
                            print(f"   태그 {i}: {tag}")
                    else:
                        print(f"   ⚠️ 해시태그 없음")
                    print(f"{'='*60}\n")

                    for tag in hashtags:
                        if tag:
                            sql_hashtag = """
                                INSERT INTO notice_hashtags (
                                    notice_id, tag_name
                                )
                                VALUES (%s, %s)
                            """
                            cursor.execute(sql_hashtag, (notice_id, tag))

                    inserted += 1

                conn.commit()

                if max_pages is not None and page >= max_pages:
                    break
                if tot_cnt_seen is not None and page * page_unit >= tot_cnt_seen:
                    break

                page += 1

            print(f"\nDB에 새로 적재된 기술 공고: {inserted}건")
            return inserted

    finally:
        conn.close()



if __name__ == "__main__":
    ingest_to_db(API_KEY, page_unit=100)