"""
Lambda 1 - Create Order: 验证输入、存数据库、发 SQS
"""

import json


def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'create_order placeholder'})
    }
