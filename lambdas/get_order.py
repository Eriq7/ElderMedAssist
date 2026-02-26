"""
Lambda 3 - Get Order: 查数据库、返回结果
"""

import json
import os
import psycopg2


def lambda_handler(event, context):
    try:
        conn = psycopg2.connect(
            host=os.environ['DB_HOST'],
            dbname=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD'],
            port=os.environ.get('DB_PORT', '5432'),
        )
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.close()
        conn.close()

        return {
            'statusCode': 200,
            'body': json.dumps({'db_connected': True, 'version': version})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'db_connected': False, 'error': str(e)})
        }
