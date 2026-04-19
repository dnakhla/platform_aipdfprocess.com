output "website_bucket_id" {
  description = "The ID (name) of the S3 bucket used for hosting the static website."
  value       = aws_s3_bucket.website.id
}

output "cloudfront_distribution_id" {
  description = "The ID of the CloudFront distribution."
  value       = aws_cloudfront_distribution.website_cdn.id
}

output "cloudfront_distribution_domain_name" {
  description = "The domain name of the CloudFront distribution."
  value       = aws_cloudfront_distribution.website_cdn.domain_name
}

output "website_endpoint" {
  description = "The final website endpoint (CloudFront domain or custom domain if configured)."
  # If a custom domain and Route 53 zone are provided, use the custom domain, otherwise use the CloudFront domain.
  value = var.domain_name != "" && var.route53_zone_id != "" ? var.domain_name : aws_cloudfront_distribution.website_cdn.domain_name
}
