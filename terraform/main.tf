provider "aws" {
  region = "us-east-1"
}

# Dead Letter Queue — 失败 3 次的消息会被移到这里
resource "aws_sqs_queue" "careplan_dlq" {
  name = "eldermed-careplan-dlq"
}

# 主队列 — 关联 DLQ，最多重试 3 次
resource "aws_sqs_queue" "careplan_queue" {
  name = "eldermed-careplan-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.careplan_dlq.arn
    maxReceiveCount     = 3
  })
}
