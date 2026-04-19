# --- S3 Bucket for Static Website Hosting ---

resource "aws_s3_bucket" "website" {
  bucket = "${var.project_name}-website-${var.environment}"
  acl    = "private" # Content served via CloudFront OAI, not directly

  website {
    index_document = var.index_document
    error_document = var.error_document
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-website-${var.environment}"
    }
  )
}

# --- Route 53 Record (Optional) ---

resource "aws_route53_record" "website_dns" {
  # Create record only if domain_name and route53_zone_id are provided
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

# --- CloudFront Origin Access Identity (OAI) ---

resource "aws_cloudfront_origin_access_identity" "oai" {
  comment = "OAI for ${aws_s3_bucket.website.id}"
}

# --- S3 Bucket Public Access Block ---

resource "aws_s3_bucket_public_access_block" "website_public_access_block" {
  bucket = aws_s3_bucket.website.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- S3 Bucket Policy for OAI ---

data "aws_iam_policy_document" "s3_policy" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.website.arn}/*"]

    principals {
      type        = "AWS"
      identifiers = [aws_cloudfront_origin_access_identity.oai.iam_arn]
    }
  }
}

resource "aws_s3_bucket_policy" "website_policy" {
  bucket = aws_s3_bucket.website.id
  policy = data.aws_iam_policy_document.s3_policy.json
}

# --- CloudFront Distribution ---

resource "aws_cloudfront_distribution" "website_cdn" {
  origin {
    domain_name = aws_s3_bucket.website.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.website.id}" # Unique origin ID

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.oai.cloudfront_access_identity_path
    }
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = var.index_document

  default_cache_behavior {
    target_origin_id = "S3-${aws_s3_bucket.website.id}" # Match origin_id

    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]

    # Using a managed cache policy for simplicity
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6" # Managed-CachingOptimized

    # Alternatively, define forwarding manually:
    # forwarded_values {
    #   query_string = false
    #   headers      = ["Origin"] # Minimal required headers
    #   cookies {
    #     forward = "none"
    #   }
    # }

    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
    # For custom domain:
    # acm_certificate_arn = var.acm_certificate_arn # Add variable if using custom domain + ACM
    # ssl_support_method  = "sni-only"
  }

  # Add aliases if using custom domain
  # aliases = var.domain_name != "" ? [var.domain_name] : []

  price_class = var.cloudfront_price_class

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-website-cdn-${var.environment}"
    }
  )
}
