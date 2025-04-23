variable "project_name" {
  description = "The name of the project (e.g., 'aipdf'). Used to prefix bucket names."
  type        = string
}

variable "environment" {
  description = "The deployment environment (e.g., 'dev', 'prod'). Used in bucket names."
  type        = string
}

variable "tags" {
  description = "A map of tags to apply to the S3 buckets."
  type        = map(string)
  default     = {}
}

# Placeholder for other Storage module variables
