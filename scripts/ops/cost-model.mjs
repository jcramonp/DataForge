// Planning estimate; USD list rates, us-east-1, reviewed 2026-11-09.
// Run: node scripts/ops/cost-model.mjs
// Sources, assumptions and exclusions: docs/operations/aws-costs.md
const assumptions = {
  "date": "2026-11-09",
  "region": "us-east-1",
  "currency": "USD",
  "hours": 730,
  "days": 30,
  "retention_days": 30,
  "physical_storage_multiplier": 3,
  "monitor_requests_reserve": 1,
  "retained_old_disk_month": 3,
  "scenarios": [
    {
      "scale": 1,
      "ec2": "t3.medium",
      "ec2_hour": 0.0418,
      "rds": "db.t4g.micro",
      "rds_hour": 0.016,
      "ebs_gb": 30,
      "rds_gb": 20
    },
    {
      "scale": 10,
      "ec2": "t3.large",
      "ec2_hour": 0.0835,
      "rds": "db.t4g.small",
      "rds_hour": 0.032,
      "ebs_gb": 50,
      "rds_gb": 20
    },
    {
      "scale": 100,
      "ec2": "t3.xlarge",
      "ec2_hour": 0.167,
      "rds": "db.t4g.medium",
      "rds_hour": 0.065,
      "ebs_gb": 100,
      "rds_gb": 100
    }
  ]
};
const rates = {
  ebs_gp3_gb_month: 0.08, rds_gp3_gb_month: 0.115,
  ipv4_hour: 0.005, alarm_month: 0.10, secret_month: 0.40,
  s3_gb_month: 0.023, s3_put_per_1000: 0.005, s3_get_per_1000: 0.0004,
  egress_gb: 0.09, sns_publish_per_million: 0.50, sns_email_per_100000: 2,
  secrets_per_10000: 0.05, groq_input_per_million: 0.15, groq_output_per_million: 0.60
};
const cents = value => Math.round((value + Number.EPSILON) * 100) / 100;
const results = assumptions.scenarios.map(s => {
  const scale = s.scale;
  const stored_gb = scale * assumptions.retention_days * assumptions.physical_storage_multiplier;
  const fixed = assumptions.hours * (s.ec2_hour + s.rds_hour + rates.ipv4_hour)
    + s.ebs_gb * rates.ebs_gp3_gb_month + s.rds_gb * rates.rds_gp3_gb_month
    + 3 * rates.alarm_month + rates.secret_month;
  const storage_requests = stored_gb * rates.s3_gb_month
    + 1000 * scale * rates.s3_put_per_1000 / 1000
    + 10000 * scale * rates.s3_get_per_1000 / 1000;
  const egress = 10 * scale * rates.egress_gb;
  const groq = 100 * scale * (6000 * rates.groq_input_per_million
    + 600 * rates.groq_output_per_million) / 1000000;
  const notifications = 10 * scale * (rates.sns_publish_per_million / 1000000
    + rates.sns_email_per_100000 / 100000);
  const secrets_api = 30 * scale * rates.secrets_per_10000 / 10000;
  const aws = fixed + storage_requests + egress + notifications + secrets_api
    + assumptions.monitor_requests_reserve;
  return {
    scale, ingress_gb_day: scale, stored_gb, egress_gb_month: 10 * scale,
    proposals_month: 100 * scale, ec2: s.ec2, rds: s.rds,
    fixed_usd: cents(fixed), s3_usd: cents(storage_requests),
    egress_usd: cents(egress), groq_usd: cents(groq),
    sns_usd: cents(notifications), secrets_api_usd: cents(secrets_api),
    monitor_reserve_usd: assumptions.monitor_requests_reserve,
    aws_usd: cents(aws), total_usd: cents(aws + groq),
    account_including_retained_disk_usd: cents(aws + groq + assumptions.retained_old_disk_month)
  };
});
console.log(JSON.stringify({ assumptions, rates, results }, null, 2));
