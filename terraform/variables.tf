variable "project_name" {
  type    = string
  default = "opera-ohip"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.40.10.0/24", "10.40.11.0/24"]
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.40.100.0/24", "10.40.101.0/24"]
}

variable "listener_image_uri" {
  type        = string
  description = "ECR image URI for the OHIP listener container."
}

variable "consumer_image_uri" {
  type        = string
  description = "ECR image URI for the OHIP consumer container."
}

variable "ohip_secret_json" {
  type        = string
  sensitive   = true
  description = "JSON secret with OHIP placeholders or real values supplied from a secure tfvars source."
}

variable "database_name" {
  type    = string
  default = "opera_ohip"
}

variable "database_username" {
  type    = string
  default = "app_user"
}

variable "database_password" {
  type      = string
  sensitive = true
}

variable "ecs_cpu" {
  type    = number
  default = 512
}

variable "ecs_memory" {
  type    = number
  default = 1024
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "allowed_database_cidr_blocks" {
  type        = list(string)
  default     = []
  description = "Optional CIDR blocks allowed to connect to Aurora, for bastion/VPN/admin access."
}


variable "enricher_image_uri" {
  type        = string
  description = "ECR image URI for the OHIP event enricher container."
}

variable "enricher_min_capacity" {
  type    = number
  default = 1
}

variable "enricher_max_capacity" {
  type    = number
  default = 6
}

variable "sqs_oldest_message_alarm_seconds" {
  type    = number
  default = 300
}


variable "analytics_image_uri" {
  type        = string
  description = "ECR image URI for the analytics snapshot job container."
}

variable "analytics_schedule_expression" {
  type        = string
  default     = "cron(0 2 * * ? *)"
  description = "EventBridge schedule for the daily analytics snapshot job. Default is 02:00 UTC."
}

variable "analytics_pickup_days" {
  type    = string
  default = "1,3,7,15"
}

variable "analytics_stay_horizon_days" {
  type    = number
  default = 730
}
