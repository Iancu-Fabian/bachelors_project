output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "eks_oidc_provider_url" {
  description = "OIDC issuer URL"
  value       = local.oidc_issuer_url
}