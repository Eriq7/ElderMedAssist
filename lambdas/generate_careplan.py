"""
Lambda 2 - Generate CarePlan: 被 SQS 触发，调 LLM，更新数据库
"""

import json


def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'generate_careplan placeholder'})
    }
