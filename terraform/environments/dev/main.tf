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
  billing_mode = "PAY_PER_REQUEST" # Specific to dev
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

  # Using defaults for lambda runtime, memory, timeout, zip paths
}

module "orchestrator" {
  source = "../../modules/orchestrator"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags

  pdf_function_arns = module.pdf_processing.function_arns
  jobs_table_arn    = module.database.jobs_table_arn

  # Using defaults for lambda runtime, memory, timeout, zip paths
}

module "api" {
  source = "../../modules/api"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags

  # Pass function ARN for direct Lambda integration with HTTP API
  orchestrator_lambda_invoke_arn = module.orchestrator.function_arn
}

module "frontend" {
  source = "../../modules/frontend"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags

  # No custom domain for dev by default
  # domain_name     = ""
  # route53_zone_id = ""
}
