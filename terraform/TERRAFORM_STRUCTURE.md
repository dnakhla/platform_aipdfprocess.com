# Terraform Structure for AI PDF Processing Platform

## Directory Organization

The structure organizes Terraform code into reusable modules and environment-specific configurations.

```
terraform/
├── environments/             # Environment-specific configurations
│   ├── dev/                  # Development environment
│   │   ├── main.tf           # Dev environment module instantiations
│   │   ├── variables.tf      # Dev-specific variables (e.g., project_name)
│   │   └── outputs.tf        # Dev environment outputs (e.g., website URL)
│   ├── staging/              # Staging environment (Placeholder)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── prod/                 # Production environment (Placeholder)
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── modules/                  # Reusable infrastructure modules
│   ├── api/                  # API Gateway (HTTP API) module
│   │   ├── main.tf           # aws_apigatewayv2_api, stage, etc.
│   │   ├── variables.tf      # Inputs: project_name, env, tags, orchestrator invoke ARN
│   │   └── outputs.tf        # Outputs: api_id, api_endpoint
│   ├── database/             # Database module (DynamoDB)
│   │   ├── main.tf           # aws_dynamodb_table resources (jobs, users)
│   │   ├── variables.tf      # Inputs: project_name, env, tags, billing_mode, etc.
│   │   └── outputs.tf        # Outputs: table names and ARNs
│   ├── frontend/             # Frontend module (S3, CloudFront)
│   │   ├── main.tf           # aws_s3_bucket, OAI, CloudFront dist, Route53 record
│   │   ├── variables.tf      # Inputs: project_name, env, tags, domain info, etc.
│   │   └── outputs.tf        # Outputs: bucket ID, CF domain, website endpoint
│   ├── orchestrator/         # Orchestrator Lambda module
│   │   ├── main.tf           # aws_lambda_function, IAM role/policy
│   │   ├── variables.tf      # Inputs: project_name, env, tags, pdf function ARNs, etc.
│   │   └── outputs.tf        # Outputs: function name and ARN, role ARN
│   ├── pdf-processing/       # PDF processing Lambda module
│   │   ├── main.tf           # aws_lambda_function (x2), layer, IAM role/policy
│   │   ├── variables.tf      # Inputs: project_name, env, tags, bucket/table ARNs, etc.
│   │   └── outputs.tf        # Outputs: function names/ARNs, layer ARN, role ARN
│   └── storage/              # Storage module (S3)
│       ├── main.tf           # aws_s3_bucket resources (input, output, artifacts)
│       ├── variables.tf      # Inputs: project_name, env, tags
│       └── outputs.tf        # Outputs: bucket IDs and ARNs
├── global/                   # Global resources (e.g., Route53 zones - Placeholder)
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── backend.tf                # Backend configuration (e.g., S3 state)
├── providers.tf              # Provider configuration (e.g., AWS region)
└── versions.tf               # Terraform and provider version constraints
```

## Key Modules Implementation (Examples)

*Note: These examples are illustrative and may omit some details for brevity. Refer to the module source code for the full implementation.*

### Storage Module (`modules/storage/main.tf`)

Creates S3 buckets for input, output, and artifacts.

```hcl
resource "aws_s3_bucket" "input" {
  bucket = "${var.project_name}-input-${var.environment}"
  acl    = "private"

  versioning { enabled = true }
  server_side_encryption_configuration { rule { /* ... AES256 ... */ } }
  lifecycle_rule { /* ... expire noncurrent, abort multipart ... */ }
  tags = merge(var.tags, { Name = "${var.project_name}-input-${var.environment}" })
}

resource "aws_s3_bucket" "output" {
  # ... similar configuration ...
}

resource "aws_s3_bucket" "artifacts" {
  # ... similar configuration ...
}
```

### Database Module (`modules/database/main.tf`)

Creates DynamoDB tables for jobs and users.

```hcl
resource "aws_dynamodb_table" "jobs" {
  name         = "${var.project_name}-jobs-${var.environment}"
  billing_mode = var.billing_mode
  hash_key     = "job_id"

  # Conditional capacity for PROVISIONED mode
  read_capacity  = var.billing_mode == "PROVISIONED" ? var.read_capacity : null
  write_capacity = var.billing_mode == "PROVISIONED" ? var.write_capacity : null

  attribute { name = "job_id"; type = "S" }
  attribute { name = "user_id"; type = "S" } # For GSI

  global_secondary_index {
    name            = "UserIdIndex"
    hash_key        = "user_id"
    projection_type = "ALL"
    # Conditional capacity...
  }

  point_in_time_recovery { enabled = true }
  tags = merge(var.tags, { Name = "${var.project_name}-jobs-${var.environment}" })
}

resource "aws_dynamodb_table" "users" {
  # ... similar configuration with user_id (hash), email (GSI) ...
}
```

### Frontend Module (`modules/frontend/main.tf`)

Creates S3 bucket, CloudFront distribution, OAI, and optional Route 53 record.

```hcl
resource "aws_s3_bucket" "website" {
  bucket = "${var.project_name}-website-${var.environment}"
  acl    = "private"
  website { index_document = var.index_document; error_document = var.error_document }
  tags = merge(var.tags, { Name = "${var.project_name}-website-${var.environment}" })
}

resource "aws_cloudfront_origin_access_identity" "oai" { /* ... */ }

resource "aws_s3_bucket_public_access_block" "website_public_access_block" { /* ... blocks all public access ... */ }

data "aws_iam_policy_document" "s3_policy" { /* ... allows OAI GetObject ... */ }

resource "aws_s3_bucket_policy" "website_policy" {
  bucket = aws_s3_bucket.website.id
  policy = data.aws_iam_policy_document.s3_policy.json
}

resource "aws_cloudfront_distribution" "website_cdn" {
  origin {
    domain_name = aws_s3_bucket.website.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.website.id}"
    s3_origin_config { origin_access_identity = aws_cloudfront_origin_access_identity.oai.cloudfront_access_identity_path }
  }
  enabled             = true
  default_root_object = var.index_document
  default_cache_behavior {
    viewer_protocol_policy = "redirect-to-https"
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6" # Managed-CachingOptimized
    # ... other cache settings ...
  }
  viewer_certificate { cloudfront_default_certificate = true }
  # aliases = var.domain_name != "" ? [var.domain_name] : [] # Handled by Route53 record
  tags = merge(var.tags, { Name = "${var.project_name}-website-cdn-${var.environment}" })
}

resource "aws_route53_record" "website_dns" {
  count = var.domain_name != "" && var.route53_zone_id != "" ? 1 : 0
  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"
  alias {
    name                   = aws_cloudfront_distribution.website_cdn.domain_name
    zone_id                = aws_cloudfront_distribution.website_cdn.hosted_zone_id
    evaluate_target_health = false
  }
}
```

### PDF Processing Module (`modules/pdf-processing/main.tf`)

Creates IAM resources, a Lambda layer, and Lambda functions for specific PDF tasks.

```hcl
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-pdf-lambda-role-${var.environment}"
  assume_role_policy = jsonencode({ /* ... allows lambda.amazonaws.com ... */ })
  tags = merge(var.tags, { Name = "${var.project_name}-pdf-lambda-role-${var.environment}" })
}

data "aws_iam_policy_document" "pdf_lambda_policy_doc" {
  statement { sid = "Logging"; actions = ["logs:*"]; resources = ["*"] }
  statement { sid = "S3Access"; actions = ["s3:GetObject", "s3:PutObject"]; resources = [ /* bucket ARNs */ ] }
  statement { sid = "DynamoDBAccess"; actions = ["dynamodb:*"]; resources = [var.jobs_table_arn] }
}

resource "aws_iam_policy" "pdf_lambda_policy" {
  name   = "${var.project_name}-pdf-lambda-policy-${var.environment}"
  policy = data.aws_iam_policy_document.pdf_lambda_policy_doc.json
  tags = merge(var.tags, { Name = "${var.project_name}-pdf-lambda-policy-${var.environment}" })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "pdf_lambda_custom" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.pdf_lambda_policy.arn
}

resource "aws_lambda_layer_version" "pdf_utils_layer" {
  layer_name        = "${var.project_name}-pdf-utils-${var.environment}"
  filename          = var.pdf_utils_layer_zip_path
  source_code_hash  = filebase64sha256(var.pdf_utils_layer_zip_path)
  compatible_runtimes = [var.lambda_runtime]
  tags = merge(var.tags, { Name = "${var.project_name}-pdf-utils-layer-${var.environment}" })
}

resource "aws_lambda_function" "extract_text" {
  function_name = "${var.project_name}-extract-text-${var.environment}"
  filename      = var.lambda_function_zip_path
  role          = aws_iam_role.lambda_execution_role.arn
  handler       = "lambda_function.lambda_handler" # Placeholder
  runtime       = var.lambda_runtime
  memory_size   = var.lambda_memory_size
  timeout       = var.lambda_timeout
  layers        = [aws_lambda_layer_version.pdf_utils_layer.arn]
  environment { variables = { /* ... bucket ARNs, table ARN, env ... */ } }
  tags = merge(var.tags, { Name = "${var.project_name}-extract-text-${var.environment}" })
}

resource "aws_lambda_function" "resize" {
  # ... similar configuration ...
}
```

### Orchestrator Module (`modules/orchestrator/main.tf`)

Creates the orchestrator Lambda function and its IAM role/policy.

```hcl
resource "aws_iam_role" "orchestrator_lambda_role" {
  name = "${var.project_name}-orchestrator-role-${var.environment}"
  assume_role_policy = jsonencode({ /* ... allows lambda.amazonaws.com ... */ })
  tags = merge(var.tags, { Name = "${var.project_name}-orchestrator-role-${var.environment}" })
}

data "aws_iam_policy_document" "orchestrator_lambda_policy_doc" {
  statement { sid = "Logging"; actions = ["logs:*"]; resources = ["*"] }
  statement { sid = "DynamoDBAccess"; actions = ["dynamodb:*"]; resources = [var.jobs_table_arn] }
  statement { sid = "InvokePDFFunctions"; actions = ["lambda:InvokeFunction"]; resources = values(var.pdf_function_arns) }
}

resource "aws_iam_policy" "orchestrator_lambda_policy" {
  name   = "${var.project_name}-orchestrator-policy-${var.environment}"
  policy = data.aws_iam_policy_document.orchestrator_lambda_policy_doc.json
  tags = merge(var.tags, { Name = "${var.project_name}-orchestrator-policy-${var.environment}" })
}

resource "aws_iam_role_policy_attachment" "orchestrator_basic_execution" { /* ... basic execution role ... */ }
resource "aws_iam_role_policy_attachment" "orchestrator_custom" { /* ... custom policy ... */ }

resource "aws_lambda_function" "orchestrator" {
  function_name = "${var.project_name}-orchestrator-${var.environment}"
  filename      = var.lambda_function_zip_path
  role          = aws_iam_role.orchestrator_lambda_role.arn
  handler       = "lambda_function.lambda_handler" # Placeholder
  runtime       = var.lambda_runtime
  memory_size   = var.lambda_memory_size
  timeout       = var.lambda_timeout
  environment { variables = { JOBS_TABLE_ARN = var.jobs_table_arn, PDF_FUNCTION_ARNS = jsonencode(var.pdf_function_arns) } }
  tags = merge(var.tags, { Name = "${var.project_name}-orchestrator-${var.environment}" })
}
```

### API Module (`modules/api/main.tf`)

Creates the HTTP API Gateway and default stage.

```hcl
resource "aws_apigatewayv2_api" "http_api" {
  name          = "${var.project_name}-http-api-${var.environment}"
  protocol_type = "HTTP"
  tags = merge(var.tags, { Name = "${var.project_name}-http-api-${var.environment}" })
}

resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
  tags = merge(var.tags, { Name = "${var.project_name}-http-api-default-stage-${var.environment}" })
}

# Integration and routes to be added later
# resource "aws_apigatewayv2_integration" "orchestrator_lambda" { ... }
# resource "aws_apigatewayv2_route" "process_pdf" { ... }
```

## Environment Usage Example (`environments/dev/main.tf`)

The `dev` environment instantiates the modules and connects their inputs/outputs.

```hcl
locals {
  environment = "dev"
  common_tags = {
    Environment = local.environment
    Project     = var.project_name
  }
}

module "storage" {
  source = "../../modules/storage"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags
}

module "database" {
  source = "../../modules/database"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags
  billing_mode = "PAY_PER_REQUEST" # Example dev override
}

module "pdf_processing" {
  source = "../../modules/pdf-processing"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags

  input_bucket_arn     = module.storage.input_bucket_arn
  output_bucket_arn    = module.storage.output_bucket_arn
  artifacts_bucket_arn = module.storage.artifacts_bucket_arn
  jobs_table_arn       = module.database.jobs_table_arn
  # Default lambda settings assumed
}

module "orchestrator" {
  source = "../../modules/orchestrator"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags

  pdf_function_arns = module.pdf_processing.function_arns
  jobs_table_arn    = module.database.jobs_table_arn
  # Default lambda settings assumed
}

module "api" {
  source = "../../modules/api"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags

  orchestrator_lambda_invoke_arn = module.orchestrator.function_arn
}

module "frontend" {
  source = "../../modules/frontend"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags
  # No custom domain for dev
}
```
