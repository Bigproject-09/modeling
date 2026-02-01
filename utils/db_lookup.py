# modeling/db_lookup.py

import os
import pymysql

def get_connection():
    # 환경변수에 DB 정보가 없으면 기본값(로컬) 사용
    # 실제 운영 환경에 맞춰 변경 가능
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "password"),
        db=os.environ.get("DB_NAME", "randi_db"),
        charset='utf8mb4'
    )

def find_ministry_by_seq_author(seq, author=None):
    """
    공고 번호(seq)로 부처명을 찾습니다. 
    author가 이미 있으면 그대로 반환하거나 검증용으로 씁니다.
    """
    # 1. 이미 부처명이 있으면 DB 조회 없이 바로 반환 (속도 최적화)
    if author:
        return author

    # 2. 부처명이 없을 때만 DB 조회
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 예시 쿼리: project_notices 테이블에서 조회
            sql = "SELECT author FROM project_notices WHERE seq = %s LIMIT 1"
            cursor.execute(sql, (seq,))
            result = cursor.fetchone()
            if result:
                return result[0]
    except Exception as e:
        print(f"[DB 조회 실패] {e}")
        # DB 연결 실패 시에도 코드가 멈추지 않도록 None 반환
        return None
    finally:
        if conn:
            conn.close()
    
    return None