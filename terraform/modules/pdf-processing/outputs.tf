output "lambda_role_arn" {
  description = "The ARN of the IAM role created for the Lambda functions."
  value       = aws_iam_role.lambda_execution_role.arn
}

output "pdf_utils_layer_arn" {
  description = "The ARN of the PDF Utils Lambda layer version."
  value       = aws_lambda_layer_version.pdf_utils_layer.arn
}

output "function_arns" {
  description = "A map containing the ARNs of the created Lambda functions."
  value = {
    extract_text = aws_lambda_function.extract_text.arn
    resize       = aws_lambda_function.resize.arn
  }
}

output "function_names" {
  description = "A map containing the names of the created Lambda functions."
  value = {
    extract_text = aws_lambda_function.extract_text.function_name
    resize       = aws_lambda_function.resize.function_name
  }
}
