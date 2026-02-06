# utils/db_lookup.py

import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    """
    환경변수에서 DB 정보를 읽어 MySQL 연결 반환
    """
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "rootpw"),
        db=os.environ.get("DB_NAME", "randi_db"),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor  # 딕셔너리 형태로 결과 반환
    )

def get_notice_info_by_id(notice_id):
    """
    notice_id(PK)로 공고 정보 조회
    
    Args:
        notice_id: 공고 고유 ID (PK)
    
    Returns:
        dict: {"seq": "공고번호", "author": "소관부처", "title": "공고명"}
        실패 시 None
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 테이블명과 컬럼명은 실제 DB 스키마에 맞게 수정하세요
            sql = """
                SELECT 
                    seq,
                    author,
                    title
                FROM project_notices 
                WHERE notice_id = %s
                LIMIT 1
            """
            cursor.execute(sql, (notice_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "seq": row["seq"],
                    "author": row["author"],
                    "title": row.get("title", "")
                }
    except Exception as e:
        print(f"[DB Error] get_notice_info_by_id 실패: {e}")
        return None
    finally:
        if conn:
            conn.close()
    
    return None

def find_ministry_by_seq_author(seq, author=None):
    """
    공고 번호(seq)로 부처명을 찾습니다. 
    author가 이미 있으면 그대로 반환하거나 검증용으로 씁니다.
    
    Args:
        seq: 공고 번호
        author: 기존 부처명 (있으면 그대로 반환)
    
    Returns:
        str: 부처명, 실패 시 None
    """
    # 1. 이미 부처명이 있으면 DB 조회 없이 바로 반환 (속도 최적화)
    if author:
        return author

    # 2. 부처명이 없을 때만 DB 조회
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            sql = "SELECT author FROM project_notices WHERE seq = %s LIMIT 1"
            cursor.execute(sql, (seq,))
            result = cursor.fetchone()
            if result:
                return result["author"]
    except Exception as e:
        print(f"[DB 조회 실패] find_ministry_by_seq_author: {e}")
        return None
    finally:
        if conn:
            conn.close()
    
    return None
                                                                                                                                                                                    