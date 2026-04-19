variable "project_name" {
  description = "The name of the project (e.g., 'aipdf'). Used as a prefix for resources."
  type        = string
  default     = "aipdf"
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

# Add other dev-specific variables here if needed, e.g.:
# variable "database_billing_mode" {
#   description = "Billing mode for DynamoDB in dev"
#   type = string
#   default = "PAY_PER_REQUEST"
# }
# variable "frontend_domain_name" { ... }
# variable "frontend_zone_id" { ... }
