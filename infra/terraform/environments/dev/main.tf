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
  billing_mode = "PAY_PER_REQUEST"
}

module "auth" {
  source = "../../modules/auth"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags
}

module "ecr" {
  source = "../../modules/ecr"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags
}

module "messaging" {
  source = "../../modules/messaging"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags
}

module "pdf_processing" {
  source = "../../modules/pdf-processing"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags

  input_bucket_arn     = module.storage.input_bucket_arn
  input_bucket_name    = module.storage.input_bucket_id
  output_bucket_arn    = module.storage.output_bucket_arn
  output_bucket_name   = module.storage.output_bucket_id
  artifacts_bucket_arn = module.storage.artifacts_bucket_arn
  artifacts_bucket_name = module.storage.artifacts_bucket_id

  jobs_table_arn  = module.database.jobs_table_arn
  jobs_table_name = module.database.jobs_table_name
  users_table_arn = module.database.users_table_arn
  users_table_name = module.database.users_table_name

  cognito_user_pool_id = module.auth.user_pool_id
  cognito_client_id    = module.auth.client_id

  job_queue_arn = module.messaging.job_queue_arn
  job_queue_url = module.messaging.job_queue_url

  api_router_zip_path     = "../../../services/api-router/lambda.zip"
  job_dispatcher_zip_path = "../../../services/job-dispatcher/lambda.zip"

  worker_structural_image_uri = "${module.ecr.worker_structural_repository_url}:latest"
  worker_extract_image_uri    = "${module.ecr.worker_extract_repository_url}:latest"
  worker_optimize_image_uri   = "${module.ecr.worker_optimize_repository_url}:latest"
}

module "api" {
  source = "../../modules/api"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags

  # Connect API Gateway to the router Lambda
  orchestrator_lambda_invoke_arn = module.pdf_processing.api_router_arn
}

module "frontend" {
  source = "../../modules/frontend"

  project_name = var.project_name
  environment  = local.environment
  tags         = local.common_tags
}
