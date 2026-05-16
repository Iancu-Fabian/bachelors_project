resource "aws_sagemaker_model" "rf_model" {
  name               = "rf-autoscaler-model"
  execution_role_arn = aws_iam_role.sagemaker_role.arn

  primary_container {
    image          = "683313688378.dkr.ecr.${var.aws_region}.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3"
    model_data_url = "s3://random-forest-bucket/model.tar.gz"
    environment = {
      SAGEMAKER_PROGRAM = "inference.py"
      SAGEMAKER_SUBMIT_DIRECTORY = "/opt/ml/model/code"
    }
  }
}

resource "aws_sagemaker_endpoint_configuration" "rf_serverless" {
  name = "rf-serverless-config"

  production_variants {
    variant_name = "default"
    model_name   = aws_sagemaker_model.rf_model.name

    serverless_config {
      max_concurrency   = 5
      memory_size_in_mb = 1024
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_sagemaker_endpoint" "rf_endpoint" {
  name                 = "rf-autoscaler-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.rf_serverless.name

  depends_on = [aws_sagemaker_endpoint_configuration.rf_serverless]

  lifecycle {
    create_before_destroy = true
  }
}

output "rf_sagemaker_endpoint_name" {
  value = aws_sagemaker_endpoint.rf_endpoint.name
}