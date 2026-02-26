provider "aws" {
  region = "us-east-1"
}

# ── Variables ────────────────────────────────────────────

variable "db_password" {
  description = "Password for the RDS PostgreSQL database"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key for LLM calls"
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
      OPENAI_API_KEY = var.openai_api_key
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

# ── API Gateway (HTTP API) ────────────────────────────────

resource "aws_apigatewayv2_api" "careplan_api" {
  name          = "eldermed-careplan-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.careplan_api.id
  name        = "$default"
  auto_deploy = true
}

output "api_url" {
  value = aws_apigatewayv2_stage.default.invoke_url
}

output "rds_address" {
  value = aws_db_instance.careplan_db.address
}

# ── API Gateway → Lambda 连接 ─────────────────────────────

# Lambda 1: POST /orders → create_order
resource "aws_apigatewayv2_integration" "create_order" {
  api_id                 = aws_apigatewayv2_api.careplan_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.create_order.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "post_orders" {
  api_id    = aws_apigatewayv2_api.careplan_api.id
  route_key = "POST /orders"
  target    = "integrations/${aws_apigatewayv2_integration.create_order.id}"
}

resource "aws_lambda_permission" "apigw_create_order" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.create_order.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.careplan_api.execution_arn}/*/*"
}

# Lambda 3: GET /orders/{id} → get_order
resource "aws_apigatewayv2_integration" "get_order" {
  api_id                 = aws_apigatewayv2_api.careplan_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.get_order.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_orders" {
  api_id    = aws_apigatewayv2_api.careplan_api.id
  route_key = "GET /orders/{id}"
  target    = "integrations/${aws_apigatewayv2_integration.get_order.id}"
}

resource "aws_lambda_permission" "apigw_get_order" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.get_order.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.careplan_api.execution_arn}/*/*"
}
