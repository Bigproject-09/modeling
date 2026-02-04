import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def get_notice_files_by_id(notice_id: int) -> dict:
    """
    DB에서 notice_id로 파일 경로 조회
    
    Returns:
        {
            "notice_file": "path/to/notice.pdf",
            "attachments": ["path/to/attachment1.docx", ...]
        }
    """
    conn = pymysql.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        db=os.environ["DB_NAME"],
        charset='utf8mb4'
    )
    
    try:
        with conn.cursor() as cursor:
            # notice_files 테이블에서 메인 파일 조회
            cursor.execute("""
                SELECT file_path FROM notice_files 
                WHERE notice_id = %s AND file_type = 'NOTICE'
                LIMIT 1
            """, (notice_id,))
            
            notice_file = cursor.fetchone()
            
            # 첨부파일 조회
            cursor.execute("""
                SELECT file_path FROM notice_attachments
                WHERE notice_id = %s AND status = 'DONE'
            """, (notice_id,))
            
            attachments = [row[0] for row in cursor.fetchall()]
            
            return {
                "notice_file": notice_file[0] if notice_file else None,
                "attachments": attachments
            }
    finally:
        conn.close()


def copy_files_to_temp(notice_id: int, target_dir: str) -> list:
    """
    DB에서 조회한 파일을 임시 폴더로 복사
    """
    import shutil
    
    files = get_notice_files_by_id(notice_id)
    os.makedirs(target_dir, exist_ok=True)
    
    copied = []
    
    # 메인 파일 복사
    if files['notice_file']:
        dest = os.path.join(target_dir, os.path.basename(files['notice_file']))
        shutil.copy(files['notice_file'], dest)
        copied.append(dest)
    
    # 첨부파일 복사
    for att in files['attachments']:
        dest = os.path.join(target_dir, os.path.basename(att))
        shutil.copy(att, dest)
        copied.append(dest)
    
    return copied