resource "aws_sagemaker_model" "lstm_model" {
  name               = "lstm-autoscaler-model-v3"
  execution_role_arn = aws_iam_role.sagemaker_role.arn

  primary_container {
    image          = "763104351884.dkr.ecr.${var.aws_region}.amazonaws.com/pytorch-inference:2.1.0-cpu-py310"
    model_data_url = "s3://lstm-model-905418239147-us-east-1-an/model.tar.gz"
    environment = {
      SAGEMAKER_PROGRAM = "inference.py"
    }
  }
}

resource "aws_sagemaker_endpoint_configuration" "lstm_serverless" {
  name = "lstm-serverless-config-v3"

  production_variants {
    variant_name  = "default"
    model_name    = aws_sagemaker_model.lstm_model.name

    serverless_config {
      max_concurrency   = 5
      memory_size_in_mb = 2048
    }
  }
  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_sagemaker_endpoint" "lstm_endpoint" {
  name                 = "lstm-autoscaler-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.lstm_serverless.name

  depends_on = [aws_sagemaker_endpoint_configuration.lstm_serverless]

  lifecycle {
    create_before_destroy = true
  }
}

output "sagemaker_endpoint_name" {
  value = aws_sagemaker_endpoint.lstm_endpoint.name
}