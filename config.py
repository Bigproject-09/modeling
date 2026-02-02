# config.py

# MySQL 접속 정보
DB_CONFIG = {
    'host': '127.0.0.1',       # 나중에 AWS RDS 주소로 교체
    'user': 'root',            # MySQL 아이디
    'password': 'rootpw', # 실제 비밀번호 입력
    'db': 'randi_db',        # 스키마 이름
    'charset': 'utf8mb4'
}

# API 정보
API_KEY = "O5T1ww"
BASE_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"