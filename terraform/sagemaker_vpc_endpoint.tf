
resource "aws_security_group" "sagemaker_vpce_sg" {
  name        = "sagemaker-vpce-sg"
  description = "Permite traficul de la nodul EKS spre SageMaker"
  vpc_id      = module.vpc.vpc_id 

  ingress {
    description = "HTTPS de la EKS Worker Nodes"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    
    cidr_blocks = [module.vpc.vpc_cidr_block] 
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "sagemaker-vpc-endpoint-sg"
  }
}

resource "aws_vpc_endpoint" "sagemaker_runtime" {
  vpc_id            = module.vpc.vpc_id  
  service_name      = "com.amazonaws.${var.aws_region}.sagemaker.runtime"
  vpc_endpoint_type = "Interface"

  subnet_ids = module.vpc.private_subnets[*]

  security_group_ids = [
    aws_security_group.sagemaker_vpce_sg.id
  ]

  private_dns_enabled = true 

  tags = {
    Name = "sagemaker-runtime-endpoint"
  }
}