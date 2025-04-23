variable "project_name" {
  description = "The name of the project (e.g., 'aipdf'). Used to prefix table names."
  type        = string
}

variable "environment" {
  description = "The deployment environment (e.g., 'dev', 'prod'). Used in table names."
  type        = string
}

variable "tags" {
  description = "A map of tags to apply to the DynamoDB tables."
  type        = map(string)
  default     = {}
}

variable "billing_mode" {
  description = "Billing mode for DynamoDB tables (PROVISIONED or PAY_PER_REQUEST)"
  type        = string
  default     = "PAY_PER_REQUEST"

  validation {
    condition     = contains(["PROVISIONED", "PAY_PER_REQUEST"], var.billing_mode)
    error_message = "Billing mode must be either PROVISIONED or PAY_PER_REQUEST."
  }
}

variable "read_capacity" {
  description = "Read capacity units for PROVISIONED billing mode"
  type        = number
  default     = 5
}

variable "write_capacity" {
  description = "Write capacity units for PROVISIONED billing mode"
  type        = number
  default     = 5
}

# Placeholder for other Database module variables
