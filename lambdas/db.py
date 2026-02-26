"""
共享的数据库连接工具 — 3 个 Lambda 都用这个文件
"""

import os
import psycopg2


def get_connection():
    return psycopg2.connect(
        host=os.environ['DB_HOST'],
        dbname=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        port=os.environ.get('DB_PORT', '5432'),
    )
