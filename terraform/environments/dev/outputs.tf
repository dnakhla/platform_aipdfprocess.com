output "website_url" {
  description = "URL for the deployed frontend website."
  value       = module.frontend.website_endpoint
}

output "api_endpoint" {
  description = "Base endpoint URL for the deployed API Gateway."
  value       = module.api.api_endpoint
}

output "input_bucket_name" {
  description = "Name of the S3 bucket for input files."
  value       = module.storage.input_bucket_id
}

output "output_bucket_name" {
  description = "Name of the S3 bucket for output files."
  value       = module.storage.output_bucket_id
}

output "orchestrator_lambda_name" {
  description = "Name of the orchestrator Lambda function."
  value       = module.orchestrator.function_name
}

# Add other outputs as needed, e.g., CloudFront distribution ID, DynamoDB table names.
