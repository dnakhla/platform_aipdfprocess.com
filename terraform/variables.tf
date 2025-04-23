variable "resource_prefix" {
  description = "Prefix for all created resources"
  type        = string
  default     = "my-lambda-app"
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}
