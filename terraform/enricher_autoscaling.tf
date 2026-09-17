resource "aws_appautoscaling_target" "enricher" {
  max_capacity       = var.enricher_max_capacity
  min_capacity       = var.enricher_min_capacity
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.enricher.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "enricher_queue_depth" {
  name               = "${local.name}-enricher-queue-depth"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.enricher.resource_id
  scalable_dimension = aws_appautoscaling_target.enricher.scalable_dimension
  service_namespace  = aws_appautoscaling_target.enricher.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 50
    scale_in_cooldown  = 120
    scale_out_cooldown = 60

    customized_metric_specification {
      metric_name = "ApproximateNumberOfMessagesVisible"
      namespace   = "AWS/SQS"
      statistic   = "Average"
      unit        = "Count"

      dimensions {
        name  = "QueueName"
        value = aws_sqs_queue.events.name
      }
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "enricher_dlq_visible" {
  alarm_name          = "${local.name}-enricher-dlq-visible"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "Messages are present in the OHIP enrichment DLQ."

  dimensions = {
    QueueName = aws_sqs_queue.events_dlq.name
  }
}

resource "aws_cloudwatch_metric_alarm" "enricher_oldest_message" {
  alarm_name          = "${local.name}-enricher-oldest-message"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = var.sqs_oldest_message_alarm_seconds
  alarm_description   = "OHIP enrichment queue has old unprocessed messages."

  dimensions = {
    QueueName = aws_sqs_queue.events.name
  }
}
