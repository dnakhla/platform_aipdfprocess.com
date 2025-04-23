# --- HTTP API Gateway ---

resource "aws_apigatewayv2_api" "http_api" {
  name          = "${var.project_name}-http-api-${var.environment}"
  protocol_type = "HTTP"
  description   = "HTTP API for ${var.project_name} (${var.environment})"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-http-api-${var.environment}"
    }
  )
}

# --- Default Stage ---

resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true

  # Access logs can be configured here later
  # access_log_settings { ... }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-http-api-default-stage-${var.environment}"
    }
  )
}

# Placeholder Comment: Add aws_apigatewayv2_integration for orchestrator lambda later.
# Placeholder Comment: Add aws_apigatewayv2_route for specific paths (e.g., /process) later.
# Placeholder Comment: Add aws_api_gateway_domain_name and aws_apigatewayv2_api_mapping for custom domain later.
