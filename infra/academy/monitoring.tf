locals {
  infrastructure_alarms = {
    ec2_status = {
      namespace   = "AWS/EC2"
      metric      = "StatusCheckFailed"
      dimension   = "InstanceId"
      target      = aws_instance.app.id
      statistic   = "Maximum"
      period      = 60
      periods     = 2
      threshold   = 1
      comparison  = "GreaterThanOrEqualToThreshold"
      description = "EC2 status checks failed for two consecutive minutes."
    }
    ec2_cpu = {
      namespace   = "AWS/EC2"
      metric      = "CPUUtilization"
      dimension   = "InstanceId"
      target      = aws_instance.app.id
      statistic   = "Average"
      period      = 300
      periods     = 3
      threshold   = 80
      comparison  = "GreaterThanThreshold"
      description = "EC2 average CPU above 80 percent for three five-minute periods."
    }
    rds_storage = {
      namespace   = "AWS/RDS"
      metric      = "FreeStorageSpace"
      dimension   = "DBInstanceIdentifier"
      target      = aws_db_instance.metadata.identifier
      statistic   = "Minimum"
      period      = 300
      periods     = 3
      threshold   = 2147483648
      comparison  = "LessThanThreshold"
      description = "RDS free storage below 2 GiB for three five-minute periods."
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "infrastructure" {
  for_each = local.infrastructure_alarms

  alarm_name          = "dataforge-academy-${each.key}"
  alarm_description   = each.value.description
  namespace           = each.value.namespace
  metric_name         = each.value.metric
  statistic           = each.value.statistic
  period              = each.value.period
  evaluation_periods  = each.value.periods
  datapoints_to_alarm = each.value.periods
  threshold           = each.value.threshold
  comparison_operator = each.value.comparison

  dimensions = {
    (each.value.dimension) = each.value.target
  }

  treat_missing_data = "missing"
  alarm_actions      = [aws_sns_topic.alerts.arn]
  ok_actions         = [aws_sns_topic.alerts.arn]

  depends_on = [aws_sns_topic_policy.alerts]
}

output "infrastructure_alarm_names" {
  value = {
    for key, alarm in aws_cloudwatch_metric_alarm.infrastructure :
    key => alarm.alarm_name
  }
}
