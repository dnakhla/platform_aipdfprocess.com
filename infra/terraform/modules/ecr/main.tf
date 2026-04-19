resource "aws_ecr_repository" "worker_structural" {
  name                 = "${var.project_name}-worker-structural-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}

resource "aws_ecr_repository" "worker_extract" {
  name                 = "${var.project_name}-worker-extract-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}

resource "aws_ecr_repository" "worker_optimize" {
  name                 = "${var.project_name}-worker-optimize-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}

output "worker_structural_repository_url" {
  value = aws_ecr_repository.worker_structural.repository_url
}

output "worker_extract_repository_url" {
  value = aws_ecr_repository.worker_extract.repository_url
}

output "worker_optimize_repository_url" {
  value = aws_ecr_repository.worker_optimize.repository_url
}
