# --- IAM Role for Lambda Functions ---

resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })

  tags = var.tags
}

# --- Policies ---

resource "aws_iam_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy-${var.environment}"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "Logging"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Sid = "S3Access"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.input_bucket_arn,
          "${var.input_bucket_arn}/*",
          var.output_bucket_arn,
          "${var.output_bucket_arn}/*",
          var.artifacts_bucket_arn,
          "${var.artifacts_bucket_arn}/*"
        ]
      },
      {
        Sid = "DynamoDBAccess"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          var.jobs_table_arn,
          "${var.jobs_table_arn}/index/*",
          var.users_table_arn,
          "${var.users_table_arn}/index/*"
        ]
      },
      {
        Sid = "SQSAccess"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [var.job_queue_arn]
      },
      {
        Sid = "LambdaInvoke"
        Action = ["lambda:InvokeFunction"]
        Resource = ["arn:aws:lambda:*:*:function:${var.project_name}-*"]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# --- Functions ---

# API Router
resource "aws_lambda_function" "api_router" {
  function_name = "${var.project_name}-api-router-${var.environment}"
  role          = aws_iam_role.lambda_role.arn
  handler       = "app.handler"
  runtime       = "python3.12"
  filename      = var.api_router_zip_path
  memory_size   = 512
  timeout       = 10

  environment {
    variables = {
      INPUT_BUCKET     = var.input_bucket_name
      OUTPUT_BUCKET    = var.output_bucket_name
      ARTIFACTS_BUCKET = var.artifacts_bucket_name
      JOBS_TABLE       = var.jobs_table_name
      USERS_TABLE      = var.users_table_name
      JOB_QUEUE_URL    = var.job_queue_url
      COGNITO_USER_POOL_ID = var.cognito_user_pool_id
      COGNITO_CLIENT_ID    = var.cognito_client_id
    }
  }

  tags = var.tags
}

# Job Dispatcher
resource "aws_lambda_function" "job_dispatcher" {
  function_name = "${var.project_name}-job-dispatcher-${var.environment}"
  role          = aws_iam_role.lambda_role.arn
  handler       = "app.handler"
  runtime       = "python3.12"
  filename      = var.job_dispatcher_zip_path
  memory_size   = 512
  timeout       = 60

  environment {
    variables = {
      JOBS_TABLE         = var.jobs_table_name
      USERS_TABLE        = var.users_table_name
      WORKER_STRUCTURAL  = aws_lambda_function.worker_structural.function_name
      WORKER_EXTRACT     = aws_lambda_function.worker_extract.function_name
      WORKER_OPTIMIZE    = aws_lambda_function.worker_optimize.function_name
    }
  }

  tags = var.tags
}

resource "aws_lambda_event_source_mapping" "dispatcher_sqs" {
  event_source_arn = var.job_queue_arn
  function_name    = aws_lambda_function.job_dispatcher.arn
  batch_size       = 1
}

# Worker Structural (Image)
resource "aws_lambda_function" "worker_structural" {
  function_name = "${var.project_name}-worker-structural-${var.environment}"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = var.worker_structural_image_uri
  memory_size   = 2048
  timeout       = 180

  environment {
    variables = {
      INPUT_BUCKET     = var.input_bucket_name
      ARTIFACTS_BUCKET = var.artifacts_bucket_name
    }
  }

  tags = var.tags
}

# Worker Extract (Image)
resource "aws_lambda_function" "worker_extract" {
  function_name = "${var.project_name}-worker-extract-${var.environment}"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = var.worker_extract_image_uri
  memory_size   = 3072
  timeout       = 300

  environment {
    variables = {
      INPUT_BUCKET     = var.input_bucket_name
      ARTIFACTS_BUCKET = var.artifacts_bucket_name
    }
  }

  tags = var.tags
}

# Worker Optimize (Image)
resource "aws_lambda_function" "worker_optimize" {
  function_name = "${var.project_name}-worker-optimize-${var.environment}"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = var.worker_optimize_image_uri
  memory_size   = 2048
  timeout       = 180

  environment {
    variables = {
      INPUT_BUCKET     = var.input_bucket_name
      ARTIFACTS_BUCKET = var.artifacts_bucket_name
    }
  }

  tags = var.tags
}

# Outputs
output "api_router_arn" {
  value = aws_lambda_function.api_router.arn
}

output "api_router_name" {
  value = aws_lambda_function.api_router.function_name
}
