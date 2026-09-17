locals {
  database_url = "postgresql://${var.database_username}:${var.database_password}@${aws_rds_cluster.postgres.endpoint}:5432/${var.database_name}"

  common_environment = [
    { name = "APP_ENV", value = var.environment },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "AWS_DEFAULT_REGION", value = var.aws_region },
    { name = "LOG_LEVEL", value = "INFO" },
    { name = "METRICS_PORT", value = "9100" },
    { name = "HEALTH_PORT", value = "8080" },
    { name = "OHIP_SECRET_ID", value = aws_secretsmanager_secret.ohip.name },
    { name = "SQS_EVENTS_QUEUE_URL", value = aws_sqs_queue.events.url },
    { name = "RAW_BUCKET", value = aws_s3_bucket.raw.bucket },
    { name = "RAW_PREFIX", value = "ohip/events" },
    { name = "OFFSET_PREFIX", value = "ohip/offsets" }
  ]

  listener_environment = concat(local.common_environment, [
    { name = "DATABASE_URL", value = local.database_url },
    { name = "SQS_MESSAGE_GROUP_ID", value = "opera-ohip-stream" }
  ])

  consumer_environment = concat(local.common_environment, [
    { name = "DATABASE_URL", value = local.database_url }
  ])
}

resource "aws_cloudwatch_log_group" "listener" {
  name              = "/ecs/${local.name}/listener"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.main.arn
}

resource "aws_cloudwatch_log_group" "consumer" {
  name              = "/ecs/${local.name}/consumer"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.main.arn
}

resource "aws_cloudwatch_log_group" "enricher" {
  name              = "/ecs/${local.name}/enricher"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.main.arn
}

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_task_definition" "listener" {
  family                   = "${local.name}-listener"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.listener_task.arn

  container_definitions = jsonencode([
    {
      name      = "listener"
      image     = var.listener_image_uri
      essential = true
      portMappings = [
        { containerPort = 8080, protocol = "tcp" },
        { containerPort = 9100, protocol = "tcp" }
      ]
      environment = local.listener_environment
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.listener.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "listener"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=2)\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    }
  ])
}

resource "aws_ecs_task_definition" "consumer" {
  family                   = "${local.name}-consumer"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.consumer_task.arn

  container_definitions = jsonencode([
    {
      name      = "consumer"
      image     = var.consumer_image_uri
      essential = true
      portMappings = [
        { containerPort = 8080, protocol = "tcp" },
        { containerPort = 9100, protocol = "tcp" }
      ]
      environment = local.consumer_environment
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.consumer.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "consumer"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=2)\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    }
  ])
}

resource "aws_ecs_service" "listener" {
  name            = "${local.name}-listener"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.listener.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}

resource "aws_ecs_service" "consumer" {
  name            = "${local.name}-consumer"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.consumer.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}


locals {
  enricher_environment = concat(local.common_environment, [
    { name = "DATABASE_URL", value = local.database_url },
    { name = "ENRICHER_ROUTER_CONFIG", value = "config/event-router.yaml" },
    { name = "ENRICHER_MAX_ATTEMPTS", value = "5" },
    { name = "SQS_ENRICHER_DLQ_URL", value = aws_sqs_queue.events_dlq.url },
    { name = "CLOUDWATCH_METRICS_NAMESPACE", value = "Opera/OHIP/Enrichment" },
    { name = "CLOUDWATCH_METRICS_ENABLED", value = "true" }
  ])
}

resource "aws_ecs_task_definition" "enricher" {
  family                   = "${local.name}-enricher"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.enricher_task.arn

  container_definitions = jsonencode([
    {
      name      = "enricher"
      image     = var.enricher_image_uri
      essential = true
      portMappings = [
        { containerPort = 8080, protocol = "tcp" },
        { containerPort = 9100, protocol = "tcp" }
      ]
      environment = local.enricher_environment
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.enricher.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "enricher"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=2)\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    }
  ])
}

resource "aws_ecs_service" "enricher" {
  name            = "${local.name}-enricher"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.enricher.arn
  desired_count   = var.enricher_min_capacity
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}
