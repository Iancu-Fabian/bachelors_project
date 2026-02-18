variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "licenta-eks"
}

variable "enable_irsa" {
  description = "enable irsa or not"
  type        = bool
  default     = true
}

variable "node_instance_type" {
  description = "EC2 instance type for worker nodes"
  type        = string
  default     = "t3.xlarge"
}

variable "desired_nodes" {
  type    = number
  default = 1
}


#prometheus

variable "amp_workspace_alias" {
  type        = string
  description = "Human-readable alias for the AMP workspace"
  default     = "licenta-amp"
}

variable "project_name" {
  type        = string
  description = "Project name used for tagging"
  default     = "licenta"
}

variable "prometheus_namespace" {
  type        = string
  description = "Kubernetes namespace where Prometheus is deployed"
  default     = "monitoring"
}

variable "prometheus_service_account_name" {
  type        = string
  description = "Service account name used by Prometheus"
  default     = "prometheus"
}

variable "prometheus_image" {
  type        = string
  description = "Prometheus container image"
  default     = "prom/prometheus:v2.49.1"
}

variable "prometheus_chart_version" {
  type    = string
  default = "56.6.0"
}


#grafana

variable "grafana_workspace_name" {
  type        = string
  description = "Name of AMG workspace"
}

variable "grafana_auth_providers" {
  type        = list(string)
  description = "Authentication providers for Grafana"
}

variable "grafana_permission_type" {
  type        = string
  description = "Workspace permission type"
}

variable "grafana_role_arn" {
  type        = string
  description = "IAM role for AMG workspace"
}

variable "grafana_data_sources" {
  type        = list(string)
  description = "Enabled data sources"
}

variable "grafana_admin_user_id" {
  type        = string
  description = "Grafana admin user id"
}