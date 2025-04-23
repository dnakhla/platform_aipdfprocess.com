output "api_id" {
  description = "The ID of the HTTP API Gateway."
  value       = aws_apigatewayv2_api.http_api.id
}

output "api_endpoint" {
  description = "The invoke URL for the default stage of the HTTP API Gateway."
  value       = aws_apigatewayv2_api.http_api.api_endpoint # Note: This is the base endpoint, stage path needs to be appended if not using $default
}

# The invoke URL for the default stage is directly the api_endpoint
# For named stages, it would be: aws_apigatewayv2_stage.default_stage.invoke_url
