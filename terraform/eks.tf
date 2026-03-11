module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.29"

  enable_irsa                              = var.enable_irsa
  cluster_endpoint_public_access           = true
  cluster_endpoint_private_access          = true
  enable_cluster_creator_admin_permissions = true

  cluster_endpoint_public_access_cidrs = [
    "${chomp(data.http.my_ip.response_body)}/32"
    ]


  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.public_subnets

  eks_managed_node_groups = {
    default = {
      instance_types = [var.node_instance_type]
      desired_size   = var.desired_nodes
      min_size       = 1
      max_size       = 6
    }
  }
}

data "http" "my_ip" {
  url = "https://checkip.amazonaws.com"
}

