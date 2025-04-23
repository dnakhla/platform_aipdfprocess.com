output "input_bucket_id" {
  description = "The ID (name) of the input S3 bucket."
  value       = aws_s3_bucket.input.id
}

output "input_bucket_arn" {
  description = "The ARN of the input S3 bucket."
  value       = aws_s3_bucket.input.arn
}

output "output_bucket_id" {
  description = "The ID (name) of the output S3 bucket."
  value       = aws_s3_bucket.output.id
}

output "output_bucket_arn" {
  description = "The ARN of the output S3 bucket."
  value       = aws_s3_bucket.output.arn
}

output "artifacts_bucket_id" {
  description = "The ID (name) of the artifacts S3 bucket."
  value       = aws_s3_bucket.artifacts.id
}

output "artifacts_bucket_arn" {
  description = "The ARN of the artifacts S3 bucket."
  value       = aws_s3_bucket.artifacts.arn
}
