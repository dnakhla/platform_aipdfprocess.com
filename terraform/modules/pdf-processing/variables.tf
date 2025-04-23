variable "project_name" {
  description = "The name of the project (e.g., 'aipdf'). Used to prefix resource names."
  type        = string
}

variable "environment" {
  description = "The deployment environment (e.g., 'dev', 'prod'). Used in resource names."
  type        = string
}

variable "tags" {
  description = "A map of tags to apply to the resources."
  type        = map(string)
  default     = {}
}

variable "input_bucket_arn" {
  description = "ARN of the input S3 bucket."
  type        = string
}

variable "output_bucket_arn" {
  description = "ARN of the output S3 bucket."
  type        = string
}

variable "artifacts_bucket_arn" {
  description = "ARN of the artifacts S3 bucket."
  type        = string
}

variable "jobs_table_arn" {
  description = "ARN of the DynamoDB jobs table."
  type        = string
}

variable "lambda_runtime" {
  description = "Runtime for the Lambda functions."
  type        = string
  default     = "python3.9"
}

variable "lambda_memory_size" {
  description = "Memory size (MB) for the Lambda functions."
  type        = number
  default     = 512
}

variable "lambda_timeout" {
  description = "Timeout in seconds for PDF processing functions."
  type        = number
  default     = 60
}

variable "pdf_utils_layer_zip_path" {
  description = "Path to the PDF Utils Lambda layer zip file. Placeholder for now."
  type        = string
  default     = "../../lambda_layer.zip" # Relative to module
}

variable "lambda_function_zip_path" {
  description = "Path to the Lambda function code zip file. Placeholder for now."
  type        = string
  default     = "../../lambda_function.zip" # Relative to module
}

# Note: The old 'service_name' variable is no longer needed and has been removed.
