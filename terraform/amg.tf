resource "aws_grafana_workspace" "this" {
  name = var.grafana_workspace_name

  account_access_type = "CURRENT_ACCOUNT"

  authentication_providers = var.grafana_auth_providers

  permission_type = var.grafana_permission_type

  role_arn = aws_iam_role.grafana.arn

  data_sources = var.grafana_data_sources
}