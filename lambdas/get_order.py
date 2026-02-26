"""
Lambda 3 - Get Order: 查询 CarePlan 状态和内容
路由: GET /orders/{id}
"""

import json
from db import get_connection


def lambda_handler(event, context):
    # 从 API Gateway 路径参数拿到 id
    path_params = event.get('pathParameters') or {}
    order_id = path_params.get('id')

    if not order_id:
        return response(400, {'error': 'Missing order id'})

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 联表查询: careplan + patient
        cur.execute("""
            SELECT c.id, c.status, c.care_plan_text, c.created_at,
                   p.first_name, p.last_name, p.medications,
                   p.allergies, p.health_conditions
            FROM careplan c
            JOIN patient p ON c.patient_id = p.id
            WHERE c.id = %s
        """, (order_id,))

        row = cur.fetchone()
        cur.close()

        if not row:
            return response(404, {'error': f'Order {order_id} not found'})

        return response(200, {
            'id': row[0],
            'status': row[1],
            'care_plan_text': row[2] if row[1] == 'completed' else '',
            'created_at': row[3].isoformat() if row[3] else '',
            'patient_name': f"{row[4]} {row[5]}",
            'medications': row[6],
            'allergies': row[7],
            'health_conditions': row[8],
        })

    except Exception as e:
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
