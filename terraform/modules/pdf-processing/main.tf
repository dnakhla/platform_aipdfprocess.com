resource "aws_iam_role" "lambda_execution_role" {
  # Updated name using project and environment variables
  name = "${var.project_name}-pdf-lambda-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = ""
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-pdf-lambda-role-${var.environment}"
    }
  )
}

resource "aws_lambda_function" "resize" {
  filename      = var.lambda_function_zip_path # Use variable
  function_name = "${var.project_name}-resize-${var.environment}" # Function name
  role          = aws_iam_role.lambda_execution_role.arn # Correct role ARN
  handler       = "lambda_function.lambda_handler" # Placeholder handler
  runtime       = var.lambda_runtime               # Use variable

  source_code_hash = filebase64sha256(var.lambda_function_zip_path) # Use variable

  memory_size = var.lambda_memory_size # Use variable
  timeout     = var.lambda_timeout     # Use variable

  layers = [aws_lambda_layer_version.pdf_utils_layer.arn] # Attach layer

  environment {
    variables = {
      INPUT_BUCKET_ARN     = var.input_bucket_arn
      OUTPUT_BUCKET_ARN    = var.output_bucket_arn
      ARTIFACTS_BUCKET_ARN = var.artifacts_bucket_arn
      JOBS_TABLE_ARN       = var.jobs_table_arn
      ENVIRONMENT          = var.environment
      # Add any resize-specific variables if needed
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-resize-${var.environment}" # Tag matches function name
    }
  )
}

# --- Custom IAM Policy for Lambda ---

data "aws_iam_policy_document" "pdf_lambda_policy_doc" {
  statement {
    sid = "Logging"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:*:*:*"]
  }

  statement {
    sid = "S3Access"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = [
      var.input_bucket_arn,
      "${var.input_bucket_arn}/*",
      var.output_bucket_arn,
      "${var.output_bucket_arn}/*",
      var.artifacts_bucket_arn,
      "${var.artifacts_bucket_arn}/*",
    ]
  }

  statement {
    sid = "DynamoDBAccess"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:Query",
    ]
    resources = [
      var.jobs_table_arn,
      # Add users table ARN here if needed later:
      # "${var.jobs_table_arn}/index/*", # If accessing GSIs specifically
    ]
  }
}

resource "aws_iam_policy" "pdf_lambda_policy" {
  name        = "${var.project_name}-pdf-lambda-policy-${var.environment}"
  path        = "/"
  description = "Policy with permissions for PDF processing Lambda functions."
  policy      = data.aws_iam_policy_document.pdf_lambda_policy_doc.json

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-pdf-lambda-policy-${var.environment}"
    }
  )
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  # Ensure this points to the potentially renamed role resource
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# --- Custom Policy Attachment ---

resource "aws_iam_role_policy_attachment" "pdf_lambda_custom" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.pdf_lambda_policy.arn
}

# --- Lambda Layer ---

resource "aws_lambda_layer_version" "pdf_utils_layer" {
  layer_name = "${var.project_name}-pdf-utils-${var.environment}"
  filename   = var.pdf_utils_layer_zip_path # Assumes ../../lambda_layer.zip exists

  # Terraform needs a source code hash to detect changes.
  source_code_hash = filebase64sha256(var.pdf_utils_layer_zip_path)

  compatible_runtimes = [var.lambda_runtime]

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-pdf-utils-layer-${var.environment}"
    }
  )
}

# --- Lambda Functions ---

resource "aws_lambda_function" "extract_text" {
  # Renamed from my_lambda and configuration updated
  filename      = var.lambda_function_zip_path # Use variable
  function_name = "${var.project_name}-extract-text-${var.environment}" # New naming convention
  role          = aws_iam_role.lambda_execution_role.arn # Correct role ARN
  handler       = "lambda_function.lambda_handler" # Placeholder handler
  runtime       = var.lambda_runtime               # Use variable

  source_code_hash = filebase64sha256(var.lambda_function_zip_path) # Use variable

  memory_size = var.lambda_memory_size # Use variable
  timeout     = var.lambda_timeout     # Use variable

  layers = [aws_lambda_layer_version.pdf_utils_layer.arn] # Attach layer

  environment {
    variables = {
      INPUT_BUCKET_ARN     = var.input_bucket_arn
      OUTPUT_BUCKET_ARN    = var.output_bucket_arn
      ARTIFACTS_BUCKET_ARN = var.artifacts_bucket_arn
      JOBS_TABLE_ARN       = var.jobs_table_arn
      ENVIRONMENT          = var.environment
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-extract-text-${var.environment}" # Tag matches function name
    }
  )
}
