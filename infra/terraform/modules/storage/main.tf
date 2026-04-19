resource "aws_s3_bucket" "input" {
  bucket = "${var.project_name}-input-${var.environment}"
  acl    = "private" # Explicitly setting ACL, though default might be private depending on account settings

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  lifecycle_rule {
    id      = "expire-noncurrent-versions"
    enabled = true

    noncurrent_version_expiration {
      days = 30
    }
  }

  lifecycle_rule {
    id      = "abort-incomplete-multipart-uploads"
    enabled = true

    abort_incomplete_multipart_upload_days = 7
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-input-${var.environment}"
      Purpose = "Input files for processing"
    }
  )
}

resource "aws_s3_bucket" "output" {
  bucket = "${var.project_name}-output-${var.environment}"
  acl    = "private"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  lifecycle_rule {
    id      = "expire-noncurrent-versions"
    enabled = true

    noncurrent_version_expiration {
      days = 30
    }
  }

  lifecycle_rule {
    id      = "abort-incomplete-multipart-uploads"
    enabled = true

    abort_incomplete_multipart_upload_days = 7
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-output-${var.environment}"
      Purpose = "Output files after processing"
    }
  )
}

resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.project_name}-artifacts-${var.environment}"
  acl    = "private"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  lifecycle_rule {
    id      = "expire-noncurrent-versions"
    enabled = true

    noncurrent_version_expiration {
      days = 30
    }
  }

  lifecycle_rule {
    id      = "abort-incomplete-multipart-uploads"
    enabled = true

    abort_incomplete_multipart_upload_days = 7
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-artifacts-${var.environment}"
      Purpose = "Storage for build artifacts, Lambda code, etc."
    }
  )
}
