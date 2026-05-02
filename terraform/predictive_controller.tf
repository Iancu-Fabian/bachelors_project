resource "kubernetes_deployment_v1" "predictive_controller" {
  metadata {
    name      = "predictive-controller"
    namespace = "default"
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "predictive-controller"
      }
    }

    template {
      metadata {
        labels = {
          app = "predictive-controller"
        }
      }

      spec {
        service_account_name = "predictive-controller-sa"

        container {
          name  = "controller"
          image = "fabian1207/predictive_controller:latest"

          env {
            name  = "AMP_WORKSPACE_ID"
            value = aws_prometheus_workspace.this.id
          }
          env {
            name  = "DEPLOYMENT_NAME"
            value = "api-deployment"
          }
          env {
            name  = "NAMESPACE"
            value = "default"
          }
          env {
            name  = "SAGEMAKER_ENDPOINT"
            value = aws_sagemaker_endpoint.lstm_endpoint.name
          }
          env {
            name  = "AWS_REGION"
            value = var.aws_region
          }
          env {
            name  = "MIN_REPLICAS"
            value = "1"
          }
          env {
            name  = "MAX_REPLICAS"
            value = "10"
          }
          env {
            name  = "CPU_TARGET"
            value = "65.0"
          }
        }
      }
    }
  }
}


resource "kubernetes_service_account_v1" "predictive_controller" {
  metadata {
    name      = "predictive-controller-sa"
    namespace = "default"
    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.predictive_controller_irsa.arn
    }
  }
}

resource "kubernetes_role_v1" "predictive_controller" {
  metadata {
    name      = "predictive-controller-role"
    namespace = "default"
  }

  rule {
    api_groups = ["apps"]
    resources  = ["deployments", "deployments/scale"]
    verbs      = ["get", "patch", "update"]
  }
}

resource "kubernetes_role_binding_v1" "predictive_controller" {
  metadata {
    name      = "predictive-controller-rb"
    namespace = "default"
  }

  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account_v1.predictive_controller.metadata[0].name
    namespace = "default"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.predictive_controller.metadata[0].name
  }
}