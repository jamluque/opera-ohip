resource "aws_kms_key" "main" {
  description             = "${local.name} application key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

resource "aws_s3_bucket" "raw" {
  bucket_prefix = "${local.name}-raw-"
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.main.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_sqs_queue" "events_dlq" {
  name                        = "${local.name}-events-dlq.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  kms_master_key_id           = aws_kms_key.main.arn
  message_retention_seconds   = 1209600
}

resource "aws_sqs_queue" "events" {
  name                        = "${local.name}-events.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  kms_master_key_id           = aws_kms_key.main.arn
  visibility_timeout_seconds  = 120
  message_retention_seconds   = 345600
  receive_wait_time_seconds   = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.events_dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_secretsmanager_secret" "ohip" {
  name       = "/${var.project_name}/${var.environment}/ohip"
  kms_key_id = aws_kms_key.main.arn
}

resource "aws_secretsmanager_secret_version" "ohip" {
  secret_id     = aws_secretsmanager_secret.ohip.id
  secret_string = var.ohip_secret_json
}
