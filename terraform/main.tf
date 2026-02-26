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
  name = "eldermed-careplan-queue"

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

# ── Lambda 函数 ──────────────────────────────────────────

# Lambda 1: 创建订单
resource "aws_lambda_function" "create_order" {
  function_name = "eldermed-create-order"
  runtime       = "python3.12"
  handler       = "create_order.lambda_handler"
  role          = aws_iam_role.lambda_role.arn
  timeout       = 10

  filename         = "${path.module}/../lambdas/zips/create_order.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambdas/zips/create_order.zip")
}

# Lambda 2: 生成 CarePlan（调 LLM，耗时长）
resource "aws_lambda_function" "generate_careplan" {
  function_name = "eldermed-generate-careplan"
  runtime       = "python3.12"
  handler       = "generate_careplan.lambda_handler"
  role          = aws_iam_role.lambda_role.arn
  timeout       = 60

  filename         = "${path.module}/../lambdas/zips/generate_careplan.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambdas/zips/generate_careplan.zip")
}

# Lambda 3: 查询订单
resource "aws_lambda_function" "get_order" {
  function_name = "eldermed-get-order"
  runtime       = "python3.12"
  handler       = "get_order.lambda_handler"
  role          = aws_iam_role.lambda_role.arn
  timeout       = 10

  filename         = "${path.module}/../lambdas/zips/get_order.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambdas/zips/get_order.zip")
}
