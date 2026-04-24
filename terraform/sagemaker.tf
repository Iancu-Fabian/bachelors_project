resource "aws_sagemaker_model" "lstm_model" {
  name               = "lstm-autoscaler-model"
  execution_role_arn = aws_iam_role.sagemaker_role.arn

  primary_container {
    image          = "763104351884.dkr.ecr.${var.aws_region}.amazonaws.com/pytorch-inference:2.1.0-cpu-py310"
    model_data_url = "s3://${aws_s3_bucket.model_bucket.bucket}/model/model.tar.gz"
    environment = {
      SAGEMAKER_PROGRAM = "inference.py"
    }
  }
}
