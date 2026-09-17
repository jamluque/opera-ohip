output "listener_repository_url" {
  value = aws_ecr_repository.listener.repository_url
}

output "consumer_repository_url" {
  value = aws_ecr_repository.consumer.repository_url
}

output "enricher_repository_url" {
  value = aws_ecr_repository.enricher.repository_url
}

output "analytics_repository_url" {
  value = aws_ecr_repository.analytics.repository_url
}

output "sqs_events_queue_url" {
  value = aws_sqs_queue.events.url
}

output "sqs_dlq_url" {
  value = aws_sqs_queue.events_dlq.url
}

output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "aurora_endpoint" {
  value = aws_rds_cluster.postgres.endpoint
}

output "ohip_secret_name" {
  value = aws_secretsmanager_secret.ohip.name
}
