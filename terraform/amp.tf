# locals {
#   amp_remote_write_endpoint = "${aws_prometheus_workspace.this.prometheus_endpoint}api/v1/remote_write"
# }


#namespace

resource "kubernetes_namespace_v1" "monitoring" {
  metadata {
    name = var.prometheus_namespace
  }
  depends_on = [
    module.eks
  ]
}

# resource "aws_prometheus_workspace" "this" {
#   alias = var.amp_workspace_alias

#   tags = {
#     Project = var.project_name
#   }
# }

resource "helm_release" "prometheus" {
  name       = "kube-prometheus-stack"
  namespace  = kubernetes_namespace_v1.monitoring.metadata[0].name
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = var.prometheus_chart_version

  values = [
    yamlencode({
      prometheus = {
        serviceAccount = {
          create = false
          name   = var.prometheus_service_account_name
        }

        prometheusSpec = {
          enableAdminAPI = false
          scrapeInterval = "30s"
          retention      = "7d"   # keep 7 days — enough for your sessions

          storageSpec = {
            volumeClaimTemplate = {
              spec = {
                accessModes = ["ReadWriteOnce"]
                resources = {
                  requests = {
                    storage = "10Gi"   # plenty for short load test sessions
                  }
                }
              }
            }
          }
        }
      }

      grafana = {
        enabled = false
      }

      alertmanager = {
        enabled = false
      }
    })
  ]
}

