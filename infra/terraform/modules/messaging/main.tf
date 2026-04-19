resource "aws_sqs_queue" "job_queue" {
  name                      = "${var.project_name}-job-queue-${var.environment}"
  message_retention_seconds = 86400 # 1 day
  visibility_timeout_seconds = 60 # Matches dispatcher timeout

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.job_queue_dlq.arn
    maxReceiveCount     = 3
  })

  tags = var.tags
}

resource "aws_sqs_queue" "job_queue_dlq" {
  name = "${var.project_name}-job-queue-dlq-${var.environment}"
  tags = var.tags
}

output "job_queue_url" {
  value = aws_sqs_queue.job_queue.url
}

output "job_queue_arn" {
  value = aws_sqs_queue.job_queue.arn
}
