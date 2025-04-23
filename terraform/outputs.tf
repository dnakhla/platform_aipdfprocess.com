output "lambda_function_arn" {
  description = "The ARN of the created Lambda function"
  value       = aws_lambda_function.my_lambda.arn
}

output "lambda_iam_role_arn" {
  description = "The ARN of the IAM role created for the Lambda function"
  value       = aws_iam_role.lambda_execution_role.arn
}
