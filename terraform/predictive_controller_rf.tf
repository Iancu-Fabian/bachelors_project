resource "kubernetes_deployment_v1" "rf_controller" {
  metadata {
    name      = "rf-controller"
    namespace = "default"
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "rf-controller"
      }
    }

    template {
      metadata {
        labels = {
          app = "rf-controller"
        }
      }

      spec {
        service_account_name = kubernetes_service_account_v1.predictive_controller.metadata[0].name

        container {
          name  = "controller"
          image = "fabian1207/predictive-controller-rf:latest"
          image_pull_policy = "Always"

          env {
            name  = "SAGEMAKER_ENDPOINT"
            value = aws_sagemaker_endpoint.rf_endpoint.name
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
            name  = "AWS_REGION"
            value = var.aws_region
          }
          env {
            name  = "MIN_REPLICAS"
            value = "1"
          }
          env {
            name  = "MAX_REPLICAS"
            value = "8"
          }
        }
      }
    }
  }
}