# --- IAM Role for Orchestrator Lambda ---

resource "aws_iam_role" "orchestrator_lambda_role" {
  name = "${var.project_name}-orchestrator-role-${var.environment}"

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
      Name = "${var.project_name}-orchestrator-role-${var.environment}"
    }
  )
}

# --- Custom IAM Policy for Orchestrator Lambda ---

data "aws_iam_policy_document" "orchestrator_lambda_policy_doc" {
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
    sid = "DynamoDBAccess"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:Query",
    ]
    resources = [
      var.jobs_table_arn,
      # Add index ARN if needed: "${var.jobs_table_arn}/index/*"
    ]
  }

  statement {
    sid = "InvokePDFFunctions"
    actions = [
      "lambda:InvokeFunction",
    ]
    resources = values(var.pdf_function_arns) # Get list of ARNs from map
  }

  # Add permissions for S3, secrets manager, etc. as needed later
}

resource "aws_iam_policy" "orchestrator_lambda_policy" {
  name        = "${var.project_name}-orchestrator-policy-${var.environment}"
  path        = "/"
  description = "Policy with permissions for the orchestrator Lambda function."
  policy      = data.aws_iam_policy_document.orchestrator_lambda_policy_doc.json

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-orchestrator-policy-${var.environment}"
    }
  )
}

# --- Attach Policies to Role ---

resource "aws_iam_role_policy_attachment" "orchestrator_basic_execution" {
  role       = aws_iam_role.orchestrator_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "orchestrator_custom" {
  role       = aws_iam_role.orchestrator_lambda_role.name
  policy_arn = aws_iam_policy.orchestrator_lambda_policy.arn
}

# --- Orchestrator Lambda Function ---

resource "aws_lambda_function" "orchestrator" {
  filename      = var.lambda_function_zip_path # Use variable
  function_name = "${var.project_name}-orchestrator-${var.environment}" # Function name
  role          = aws_iam_role.orchestrator_lambda_role.arn # Correct role ARN
  handler       = "lambda_function.lambda_handler" # Placeholder handler
  runtime       = var.lambda_runtime               # Use variable

  source_code_hash = filebase64sha256(var.lambda_function_zip_path) # Use variable

  memory_size = var.lambda_memory_size # Use variable
  timeout     = var.lambda_timeout     # Use variable

  environment {
    variables = {
      JOBS_TABLE_ARN     = var.jobs_table_arn
      ENVIRONMENT        = var.environment
      PDF_FUNCTION_ARNS  = jsonencode(var.pdf_function_arns) # Pass map as JSON string
      # Add API keys or other secrets later
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-orchestrator-${var.environment}" # Tag matches function name
    }
  )
}
