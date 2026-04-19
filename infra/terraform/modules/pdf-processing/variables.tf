variable "project_name" { type = string }
variable "environment" { type = string }
variable "tags" { type = map(string) }

variable "input_bucket_arn" { type = string }
variable "input_bucket_name" { type = string }
variable "output_bucket_arn" { type = string }
variable "output_bucket_name" { type = string }
variable "artifacts_bucket_arn" { type = string }
variable "artifacts_bucket_name" { type = string }

variable "jobs_table_arn" { type = string }
variable "jobs_table_name" { type = string }
variable "users_table_arn" { type = string }
variable "users_table_name" { type = string }

variable "cognito_user_pool_id" { type = string }
variable "cognito_client_id" { type = string }

variable "job_queue_arn" { type = string }
variable "job_queue_url" { type = string }

variable "api_router_zip_path" { type = string }
variable "job_dispatcher_zip_path" { type = string }

variable "worker_structural_image_uri" { type = string }
variable "worker_extract_image_uri" { type = string }
variable "worker_optimize_image_uri" { type = string }
