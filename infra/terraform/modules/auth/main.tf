resource "aws_cognito_user_pool" "user_pool" {
  name = "${var.project_name}-users-${var.environment}"

  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  auto_verified_attributes = ["email"]

  schema {
    attribute_data_type = "String"
    name                = "email"
    required            = true
    mutable             = true
  }

  tags = var.tags
}

resource "aws_cognito_user_pool_client" "client" {
  name         = "${var.project_name}-client-${var.environment}"
  user_pool_id = aws_cognito_user_pool.user_pool.id

  explicit_auth_flows = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_CUSTOM_AUTH", "ALLOW_USER_SRP_AUTH"]

  prevent_user_existence_errors = "ENABLED"
}

output "user_pool_id" {
  value = aws_cognito_user_pool.user_pool.id
}

output "user_pool_arn" {
  value = aws_cognito_user_pool.user_pool.arn
}

output "client_id" {
  value = aws_cognito_user_pool_client.client.id
}

variable "project_name" { type = string }
variable "environment" { type = string }
variable "tags" { type = map(string) }
