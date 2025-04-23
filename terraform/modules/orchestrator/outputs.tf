output "lambda_role_arn" {
  description = "The ARN of the IAM role created for the orchestrator Lambda function."
  value       = aws_iam_role.orchestrator_lambda_role.arn
}

output "function_arn" {
  description = "The ARN of the orchestrator Lambda function."
  value       = aws_lambda_function.orchestrator.arn
}

output "function_name" {
  description = "The name of the orchestrator Lambda function."
  value       = aws_lambda_function.orchestrator.function_name
}
