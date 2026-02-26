"""
Lambda 3 - Get Order: 查数据库、返回结果
"""

import json


def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'get_order placeholder'})
    }
