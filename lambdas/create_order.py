"""
Lambda 1 - Create Order: 验证输入 → 存数据库 → 发 SQS
路由: POST /orders
"""

import json
import os
import boto3
from db import get_connection


sqs = boto3.client('sqs')


def lambda_handler(event, context):
    # 1. 解析请求体
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return response(400, {'error': 'Invalid JSON'})

    # 2. 验证必填字段
    required = ['patient_first_name', 'patient_last_name', 'date_of_birth', 'medications']
    missing = [f for f in required if not body.get(f)]
    if missing:
        return response(400, {'error': f'Missing fields: {", ".join(missing)}'})

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 3. 查找或创建 Patient
        cur.execute(
            "SELECT id FROM patient WHERE first_name=%s AND last_name=%s AND date_of_birth=%s",
            (body['patient_first_name'], body['patient_last_name'], body['date_of_birth'])
        )
        row = cur.fetchone()

        if row:
            patient_id = row[0]
            cur.execute(
                "UPDATE patient SET medications=%s, allergies=%s, health_conditions=%s WHERE id=%s",
                (body['medications'], body.get('allergies', ''), body.get('health_conditions', ''), patient_id)
            )
        else:
            cur.execute(
                "INSERT INTO patient (first_name, last_name, date_of_birth, medications, allergies, health_conditions) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (body['patient_first_name'], body['patient_last_name'], body['date_of_birth'],
                 body['medications'], body.get('allergies', ''), body.get('health_conditions', ''))
            )
            patient_id = cur.fetchone()[0]

        # 4. 检查是否有重复的 pending/processing 订单
        cur.execute(
            "SELECT id FROM careplan WHERE patient_id=%s AND status IN ('pending','processing')",
            (patient_id,)
        )
        if cur.fetchone():
            conn.rollback()
            return response(409, {'error': 'A care plan is already being generated for this patient.'})

        # 5. 创建 CarePlan
        cur.execute(
            "INSERT INTO careplan (patient_id, status) VALUES (%s, 'pending') RETURNING id",
            (patient_id,)
        )
        careplan_id = cur.fetchone()[0]
        conn.commit()

        # 6. 发 SQS 消息，触发 Lambda 2
        sqs.send_message(
            QueueUrl=os.environ['SQS_QUEUE_URL'],
            MessageBody=json.dumps({'careplan_id': careplan_id}),
        )

        return response(201, {
            'id': careplan_id,
            'status': 'pending',
            'message': 'Received, generating your medication guide.',
        })

    except Exception as e:
        if conn:
            conn.rollback()
        return response(500, {'error': str(e)})
    finally:
        if conn:
            conn.close()


def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(body),
    }
