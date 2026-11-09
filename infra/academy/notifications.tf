variable "alert_email" {
  description = "Operator email for DataForge infrastructure alerts."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "Enter a valid notification email address."
  }
}

resource "aws_sns_topic" "alerts" {
  name = "dataforge-academy-alerts"
}

resource "aws_sns_topic_policy" "alerts" {
  arn = aws_sns_topic.alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowDataForgeCloudWatch"
      Effect    = "Allow"
      Principal = { Service = "cloudwatch.amazonaws.com" }
      Action    = "sns:Publish"
      Resource  = aws_sns_topic.alerts.arn
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
        ArnLike = {
          "aws:SourceArn" = "arn:aws:cloudwatch:us-east-1:${data.aws_caller_identity.current.account_id}:alarm:dataforge-academy-*"
        }
      }
    }]
  })
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email

  depends_on = [aws_sns_topic_policy.alerts]
}

output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
