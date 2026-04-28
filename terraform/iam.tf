locals {
  oidc_issuer_url = module.eks.cluster_oidc_issuer_url
}

#eks

resource "aws_iam_role" "eks_admin" {
  name = "eks-admin-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        AWS = "arn:aws:iam::905418239147:user/admin"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_admin_attach" {
  role       = aws_iam_role.eks_admin.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_eks_access_entry" "admin" {
  cluster_name  = module.eks.cluster_name
  principal_arn = aws_iam_role.eks_admin.arn
}

resource "aws_eks_access_policy_association" "admin" {
  cluster_name  = module.eks.cluster_name
  principal_arn = aws_iam_role.eks_admin.arn

  policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}


#prometheus

data "aws_iam_policy_document" "amp_write" {
  statement {
    effect = "Allow"

    actions = [
      "aps:RemoteWrite",
      "aps:GetSeries",
      "aps:GetLabels",
      "aps:GetMetricMetadata"
    ]

    resources = [
      aws_prometheus_workspace.this.arn
    ]
  }
}

data "aws_iam_policy_document" "prometheus_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }

    actions = ["sts:AssumeRoleWithWebIdentity"]

    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:sub"
      values   = ["system:serviceaccount:${var.prometheus_namespace}:${var.prometheus_service_account_name}"]
    }
  }
}

resource "aws_iam_role" "prometheus" {
  name               = "${var.project_name}-amp-prometheus-role"
  assume_role_policy = data.aws_iam_policy_document.prometheus_assume_role.json
}

resource "aws_iam_policy" "amp_write" {
  name   = "${var.project_name}-amp-write-policy"
  policy = data.aws_iam_policy_document.amp_write.json
}

resource "aws_iam_role_policy_attachment" "amp_write" {
  role       = aws_iam_role.prometheus.name
  policy_arn = aws_iam_policy.amp_write.arn
}

resource "kubernetes_service_account_v1" "prometheus" {
  metadata {
    name      = var.prometheus_service_account_name
    namespace = kubernetes_namespace_v1.monitoring.metadata[0].name

    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.prometheus.arn
    }
  }
}


#grafana

data "aws_iam_policy_document" "grafana_assume" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["grafana.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "grafana" {
  name               = "${var.project_name}-grafana-role"
  assume_role_policy = data.aws_iam_policy_document.grafana_assume.json
}

data "aws_iam_policy_document" "grafana_amp" {
  statement {
    effect = "Allow"

    actions = [
      "aps:QueryMetrics",
      "aps:GetLabels",
      "aps:GetSeries",
      "aps:GetMetricMetadata"
    ]

    resources = [
      aws_prometheus_workspace.this.arn
    ]
  }
}

resource "aws_iam_policy" "grafana_amp" {
  name   = "${var.project_name}-grafana-amp"
  policy = data.aws_iam_policy_document.grafana_amp.json
}

resource "aws_iam_role_policy_attachment" "grafana_attach" {
  role       = aws_iam_role.grafana.name
  policy_arn = aws_iam_policy.grafana_amp.arn
}

resource "aws_grafana_role_association" "admin" {
  workspace_id = aws_grafana_workspace.this.id
  role         = "ADMIN"

  user_ids = [
    var.grafana_admin_user_id
  ]
}

resource "aws_iam_role" "sagemaker_role" {
  name = "sagemaker-lstm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "sagemaker.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "sagemaker_full" {
  role       = aws_iam_role.sagemaker_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

resource "aws_iam_role_policy_attachment" "sagemaker_s3" {
  role       = aws_iam_role.sagemaker_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}
