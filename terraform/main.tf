provider "aws" {
  region = "us-east-1"
}

# ── Variables ────────────────────────────────────────────

variable "db_password" {
  description = "Password for the RDS PostgreSQL database"
  type        = string
  sensitive   = true
}

# Dead Letter Queue — 失败 3 次的消息会被移到这里
resource "aws_sqs_queue" "careplan_dlq" {
  name = "eldermed-careplan-dlq"
}

# 主队列 — 关联 DLQ，最多重试 3 次
resource "aws_sqs_queue" "careplan_queue" {
  name                       = "eldermed-careplan-queue"
  visibility_timeout_seconds = 90

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.careplan_dlq.arn
    maxReceiveCount     = 3
  })
}

# ── Security Group — 允许 PostgreSQL 连接 ────────────────

resource "aws_security_group" "rds_sg" {
  name        = "eldermed-rds-sg"
  description = "Allow PostgreSQL access"

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ── RDS PostgreSQL（免费套餐）────────────────────────────

resource "aws_db_instance" "careplan_db" {
  identifier     = "eldermed-careplan-db"
  engine         = "postgres"
  engine_version = "16.4"
  instance_class = "db.t3.micro"

  allocated_storage = 20
  storage_type      = "gp2"

  db_name  = "careplan"
  username = "careplan_user"
  password = var.db_password

  publicly_accessible    = true
  skip_final_snapshot    = true
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
}

# ── IAM Role — Lambda 执行角色 ───────────────────────────

resource "aws_iam_role" "lambda_role" {
  name = "eldermed-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# 基础权限：写 CloudWatch 日志
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# SQS 权限：发消息 + 收消息
resource "aws_iam_role_policy" "lambda_sqs" {
  name = "eldermed-lambda-sqs"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ]
      Resource = [
        aws_sqs_queue.careplan_queue.arn,
        aws_sqs_queue.careplan_dlq.arn
      ]
    }]
  })
}

# ── Lambda 函数 ──────────────────────────────────────────

# Lambda 共享的环境变量（数据库连接信息）
locals {
  db_env = {
    DB_HOST     = aws_db_instance.careplan_db.address
    DB_NAME     = "careplan"
    DB_USER     = "careplan_user"
    DB_PASSWORD = var.db_password
    DB_PORT     = "5432"
  }
}

# Lambda 1: 创建订单 — 需要连数据库 + 发 SQS
resource "aws_lambda_function" "create_order" {
  function_name = "eldermed-create-order"
  runtime       = "python3.12"
  handler       = "create_order.lambda_handler"
  role          = aws_iam_role.lambda_role.arn
  timeout       = 10

  filename         = "${path.module}/../lambdas/zips/create_order.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambdas/zips/create_order.zip")

  environment {
    variables = merge(local.db_env, {
      SQS_QUEUE_URL = aws_sqs_queue.careplan_queue.url
    })
  }
}

# Lambda 2: 生成 CarePlan — 被 SQS 触发，连数据库 + 调 LLM
resource "aws_lambda_function" "generate_careplan" {
  function_name = "eldermed-generate-careplan"
  runtime       = "python3.12"
  handler       = "generate_careplan.lambda_handler"
  role          = aws_iam_role.lambda_role.arn
  timeout       = 60

  filename         = "${path.module}/../lambdas/zips/generate_careplan.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambdas/zips/generate_careplan.zip")

  environment {
    variables = merge(local.db_env, {
      OPENAI_API_KEY = "placeholder"
    })
  }
}

# Lambda 3: 查询订单 — 只需要连数据库
resource "aws_lambda_function" "get_order" {
  function_name = "eldermed-get-order"
  runtime       = "python3.12"
  handler       = "get_order.lambda_handler"
  role          = aws_iam_role.lambda_role.arn
  timeout       = 10

  filename         = "${path.module}/../lambdas/zips/get_order.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambdas/zips/get_order.zip")

  environment {
    variables = local.db_env
  }
}

# ── SQS 触发 Lambda 2 ───────────────────────────────────

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.careplan_queue.arn
  function_name    = aws_lambda_function.generate_careplan.arn
  batch_size       = 1
}
