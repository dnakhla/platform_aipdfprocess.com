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

variable "orchestrator_lambda_invoke_arn" {
  description = "Invoke ARN for the orchestrator Lambda function. Used later for integration."
  type        = string
}

# Add other variables as needed for specific routes, stages, custom domains etc.

# Placeholder for other API module variables
