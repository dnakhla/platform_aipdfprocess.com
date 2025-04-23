resource "aws_lambda_function" "my_lambda" {
  # Note: Terraform requires a valid file path for filename, even if it's a placeholder.
  # We will create a dummy lambda_function.zip later.
  filename      = "lambda_function.zip"
  function_name = "${var.resource_prefix}-function"
  role          = aws_iam_role.lambda_execution_role.arn
  handler       = "lambda_function.lambda_handler" # Placeholder handler
  runtime       = "python3.9"                      # Placeholder runtime

  # Terraform needs a source code hash to detect changes.
  # We'll generate a dummy zip and calculate its hash.
  # For now, using a placeholder hash. This will be updated.
  source_code_hash = filebase64sha256("lambda_function.zip")

  tags = {
    Name = "${var.resource_prefix}-lambda"
  }
}
