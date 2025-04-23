# Terraform Structure for AI PDF Processing Platform

## Directory Organization

```
terraform/
├── environments/
│   ├── dev/
│   │   ├── main.tf           # Dev environment configuration
│   │   ├── variables.tf      # Dev-specific variables
│   │   └── outputs.tf        # Dev-specific outputs
│   ├── staging/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── prod/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── modules/
│   ├── frontend/
│   │   ├── main.tf           # S3 bucket, CloudFront, etc.
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── api/
│   │   ├── main.tf           # API Gateway, routes, etc.
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── pdf-processing/
│   │   ├── main.tf           # Lambda functions for PDF processing
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── orchestrator/
│   │   ├── main.tf           # AI orchestration Lambda
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── storage/
│   │   ├── main.tf           # S3 buckets for storage
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── database/
│       ├── main.tf           # DynamoDB tables
│       ├── variables.tf
│       └── outputs.tf
├── global/
│   ├── main.tf               # Shared global resources
│   ├── variables.tf          # Global variables
│   └── outputs.tf            # Global outputs
├── providers.tf              # AWS provider configuration
├── backend.tf                # Remote state configuration
└── versions.tf               # Terraform version constraints
```

## Key Modules Implementation

### Frontend Module

```hcl
# modules/frontend/main.tf

resource "aws_s3_bucket" "website" {
  bucket = "${var.project_name}-website-${var.environment}"
  acl    = "private"
  
  website {
    index_document = "index.html"
    error_document = "error.html"
  }
  
  tags = var.tags
}

resource "aws_cloudfront_distribution" "website_cdn" {
  origin {
    domain_name = aws_s3_bucket.website.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.website.bucket}"
    
    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.oai.cloudfront_access_identity_path
    }
  }
  
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  
  # Additional CloudFront configuration...
}

resource "aws_route53_record" "website" {
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

### PDF Processing Module

```hcl
# modules/pdf-processing/main.tf

# Lambda layer for shared PDF utilities
resource "aws_lambda_layer_version" "pdf_utils" {
  layer_name = "${var.project_name}-pdf-utils"
  description = "PDF utility libraries and dependencies"
  
  filename   = var.pdf_utils_layer_zip
  
  compatible_runtimes = ["nodejs16.x"]
}

# IAM role for the PDF processing Lambda functions
resource "aws_iam_role" "pdf_lambda_role" {
  name = "${var.project_name}-pdf-lambda-role-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Policy for PDF Lambda permissions (S3, DynamoDB, CloudWatch, etc.)
resource "aws_iam_policy" "pdf_lambda_policy" {
  name        = "${var.project_name}-pdf-lambda-policy-${var.environment}"
  description = "Policy for PDF processing Lambda functions"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
        ]
        Resource = [
          var.input_bucket_arn,
          "${var.input_bucket_arn}/*",
          var.output_bucket_arn,
          "${var.output_bucket_arn}/*",
          var.artifacts_bucket_arn,
          "${var.artifacts_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = var.jobs_table_arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "pdf_lambda_policy_attachment" {
  role       = aws_iam_role.pdf_lambda_role.name
  policy_arn = aws_iam_policy.pdf_lambda_policy.arn
}

# Example Lambda function for text extraction
resource "aws_lambda_function" "extract_text" {
  function_name = "${var.project_name}-extract-text-${var.environment}"
  description   = "Extracts text from PDF documents"
  
  handler       = "index.handler"
  runtime       = "nodejs16.x"
  timeout       = 30
  memory_size   = 512
  
  role          = aws_iam_role.pdf_lambda_role.arn
  
  filename      = var.extract_text_zip
  
  layers        = [aws_lambda_layer_version.pdf_utils.arn]
  
  environment {
    variables = {
      INPUT_BUCKET    = var.input_bucket_name
      OUTPUT_BUCKET   = var.output_bucket_name
      ARTIFACTS_BUCKET = var.artifacts_bucket_name
      JOBS_TABLE      = var.jobs_table_name
      ENVIRONMENT     = var.environment
    }
  }
  
  tags = var.tags
}

# Repeat for other PDF functions (resize, compress, etc.)
```

### Orchestrator Module

```hcl
# modules/orchestrator/main.tf

resource "aws_lambda_function" "orchestrator" {
  function_name = "${var.project_name}-orchestrator-${var.environment}"
  description   = "LLM-powered PDF processing orchestrator"
  
  handler       = "index.handler"
  runtime       = "nodejs16.x"
  timeout       = 30
  memory_size   = 1024
  
  role          = aws_iam_role.orchestrator_lambda_role.arn
  
  filename      = var.orchestrator_zip
  
  environment {
    variables = {
      INPUT_BUCKET     = var.input_bucket_name
      OUTPUT_BUCKET    = var.output_bucket_name
      ARTIFACTS_BUCKET = var.artifacts_bucket_name
      JOBS_TABLE       = var.jobs_table_name
      ENVIRONMENT      = var.environment
      OPENAI_API_KEY   = var.openai_api_key_parameter
      PDF_FUNCTIONS    = jsonencode(var.pdf_function_arns)
    }
  }
  
  tags = var.tags
}

# IAM role with permissions to invoke PDF functions
resource "aws_iam_role" "orchestrator_lambda_role" {
  name = "${var.project_name}-orchestrator-role-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Policy with Lambda invocation permissions
resource "aws_iam_policy" "orchestrator_lambda_policy" {
  name        = "${var.project_name}-orchestrator-policy-${var.environment}"
  description = "Policy for orchestrator Lambda function"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = var.pdf_function_arns
      },
      # Additional permissions for S3, DynamoDB, etc.
    ]
  })
}

resource "aws_iam_role_policy_attachment" "orchestrator_lambda_policy_attachment" {
  role       = aws_iam_role.orchestrator_lambda_role.name
  policy_arn = aws_iam_policy.orchestrator_lambda_policy.arn
}
```

### Environment Usage

```hcl
# environments/dev/main.tf

module "global" {
  source = "../../global"
}

module "storage" {
  source      = "../../modules/storage"
  environment = "dev"
  project_name = var.project_name
  tags        = var.tags
}

module "database" {
  source      = "../../modules/database"
  environment = "dev"
  project_name = var.project_name
  tags        = var.tags
}

module "pdf_processing" {
  source            = "../../modules/pdf-processing"
  environment       = "dev"
  project_name      = var.project_name
  input_bucket_arn  = module.storage.input_bucket_arn
  output_bucket_arn = module.storage.output_bucket_arn
  artifacts_bucket_arn = module.storage.artifacts_bucket_arn
  jobs_table_arn    = module.database.jobs_table_arn
  input_bucket_name = module.storage.input_bucket_name
  output_bucket_name = module.storage.output_bucket_name
  artifacts_bucket_name = module.storage.artifacts_bucket_name
  jobs_table_name   = module.database.jobs_table_name
  pdf_utils_layer_zip = var.pdf_utils_layer_zip
  extract_text_zip  = var.extract_text_zip
  # Other function zip files
  tags              = var.tags
}

module "orchestrator" {
  source             = "../../modules/orchestrator"
  environment        = "dev"
  project_name       = var.project_name
  input_bucket_name  = module.storage.input_bucket_name
  output_bucket_name = module.storage.output_bucket_name
  artifacts_bucket_name = module.storage.artifacts_bucket_name
  jobs_table_name    = module.database.jobs_table_name
  pdf_function_arns  = module.pdf_processing.function_arns
  orchestrator_zip   = var.orchestrator_zip
  openai_api_key_parameter = module.global.openai_api_key_parameter
  tags               = var.tags
}

module "api" {
  source           = "../../modules/api"
  environment      = "dev"
  project_name     = var.project_name
  orchestrator_arn = module.orchestrator.function_arn
  tags             = var.tags
}

module "frontend" {
  source          = "../../modules/frontend"
  environment     = "dev"
  project_name    = var.project_name
  api_endpoint    = module.api.api_endpoint
  domain_name     = "dev.aipdfprocessing.com"
  route53_zone_id = module.global.route53_zone_id
  tags            = var.tags
}
```