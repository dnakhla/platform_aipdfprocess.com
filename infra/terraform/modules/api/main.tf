resource "aws_apigatewayv2_api" "http_api" {
  name          = "${var.project_name}-http-api-${var.environment}"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "router_lambda" {
  api_id           = aws_apigatewayv2_api.http_api.id
  integration_type = "AWS_PROXY"

  integration_method = "POST"
  integration_uri    = var.orchestrator_lambda_invoke_arn
  payload_format_version = "2.0"
}

# Routes
resource "aws_apigatewayv2_route" "upload" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /v1/upload"
  target    = "integrations/${aws_apigatewayv2_integration.router_lambda.id}"
}

resource "aws_apigatewayv2_route" "process" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /v1/process"
  target    = "integrations/${aws_apigatewayv2_integration.router_lambda.id}"
}

resource "aws_apigatewayv2_route" "status" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /v1/status/{jobId}"
  target    = "integrations/${aws_apigatewayv2_integration.router_lambda.id}"
}

resource "aws_apigatewayv2_route" "download" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /v1/download/{jobId}"
  target    = "integrations/${aws_apigatewayv2_integration.router_lambda.id}"
}

# Permission for API Gateway to invoke Lambda
resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = var.orchestrator_lambda_invoke_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}
