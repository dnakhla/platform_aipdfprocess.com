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

variable "lambda_runtime" {
  description = "Runtime for the Lambda function."
  type        = string
  default     = "python3.9"
}

variable "lambda_memory_size" {
  description = "Memory size (MB) for the Lambda function."
  type        = number
  default     = 1024 # Orchestrator might need more memory
}

variable "lambda_timeout" {
  description = "Timeout in seconds for the orchestrator function."
  type        = number
  default     = 30
}

variable "lambda_function_zip_path" {
  description = "Path to the Lambda function code zip file. Placeholder for now."
  type        = string
  default     = "../../lambda_function.zip" # Relative to module
}

variable "pdf_function_arns" {
  description = "Map of PDF function names to their ARNs, passed from pdf-processing module"
  type        = map(string)
}

variable "jobs_table_arn" {
  description = "ARN of the DynamoDB jobs table."
  type        = string
}

# Add variables for API keys or other secrets later (e.g., using SSM Parameter Store)

# Placeholder for other Orchestrator module variables
