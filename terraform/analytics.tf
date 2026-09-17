data "aws_iam_policy_document" "analytics_task_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "analytics_task" {
  name               = "${local.name}-analytics-task"
  assume_role_policy = data.aws_iam_policy_document.analytics_task_assume.json
}

resource "aws_cloudwatch_log_group" "analytics" {
  name              = "/ecs/${local.name}/analytics"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.main.arn
}

locals {
  analytics_environment = [
    { name = "APP_ENV", value = var.environment },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "AWS_DEFAULT_REGION", value = var.aws_region },
    { name = "LOG_LEVEL", value = "INFO" },
    { name = "DATABASE_URL", value = local.database_url },
    { name = "ANALYTICS_PICKUP_DAYS", value = var.analytics_pickup_days },
    { name = "ANALYTICS_STAY_HORIZON_DAYS", value = tostring(var.analytics_stay_horizon_days) }
  ]
}

resource "aws_ecs_task_definition" "analytics" {
  family                   = "${local.name}-analytics"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.analytics_task.arn

  container_definitions = jsonencode([
    {
      name        = "analytics-snapshot-job"
      image       = var.analytics_image_uri
      essential   = true
      environment = local.analytics_environment
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.analytics.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "analytics"
        }
      }
    }
  ])
}

data "aws_iam_policy_document" "analytics_events_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "analytics_events" {
  name               = "${local.name}-analytics-events"
  assume_role_policy = data.aws_iam_policy_document.analytics_events_assume.json
}

data "aws_iam_policy_document" "analytics_events" {
  statement {
    actions   = ["ecs:RunTask"]
    resources = [aws_ecs_task_definition.analytics.arn]
  }

  statement {
    actions = ["iam:PassRole"]
    resources = [
      aws_iam_role.execution.arn,
      aws_iam_role.analytics_task.arn
    ]
  }
}

resource "aws_iam_policy" "analytics_events" {
  name   = "${local.name}-analytics-events"
  policy = data.aws_iam_policy_document.analytics_events.json
}

resource "aws_iam_role_policy_attachment" "analytics_events" {
  role       = aws_iam_role.analytics_events.name
  policy_arn = aws_iam_policy.analytics_events.arn
}

resource "aws_cloudwatch_event_rule" "analytics_daily" {
  name                = "${local.name}-analytics-daily"
  description         = "Run daily PMS analytics snapshot and pickup materialization."
  schedule_expression = var.analytics_schedule_expression
}

resource "aws_cloudwatch_event_target" "analytics_daily" {
  rule      = aws_cloudwatch_event_rule.analytics_daily.name
  target_id = "analytics-snapshot-job"
  arn       = aws_ecs_cluster.main.arn
  role_arn  = aws_iam_role.analytics_events.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.analytics.arn
    launch_type         = "FARGATE"
    task_count          = 1

    network_configuration {
      subnets          = aws_subnet.private[*].id
      security_groups  = [aws_security_group.ecs.id]
      assign_public_ip = false
    }
  }
}
