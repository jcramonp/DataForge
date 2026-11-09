terraform {
  required_version = ">= 1.12.2, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = {
      Project     = "DataForge"
      Environment = "academy-demo"
      ManagedBy   = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-kernel-*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

variable "operator_cidr" {
  description = "Public IPv4 address of the demo operator in /32 notation."
  type        = string

  validation {
    condition     = can(cidrnetmask(var.operator_cidr)) && endswith(var.operator_cidr, "/32")
    error_message = "Set operator_cidr to one public IPv4 address with a /32 mask."
  }
}

locals {
  zones = {
    first  = { name = data.aws_availability_zones.available.names[0], cidr = "10.42.10.0/24" }
    second = { name = data.aws_availability_zones.available.names[1], cidr = "10.42.20.0/24" }
  }
}

resource "aws_vpc" "demo" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
}

resource "aws_internet_gateway" "demo" {
  vpc_id = aws_vpc.demo.id
}

resource "aws_subnet" "app" {
  vpc_id            = aws_vpc.demo.id
  cidr_block        = "10.42.1.0/24"
  availability_zone = local.zones.first.name
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.demo.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.demo.id
  }
}

resource "aws_route_table_association" "app" {
  subnet_id      = aws_subnet.app.id
  route_table_id = aws_route_table.public.id
}

resource "aws_subnet" "database" {
  for_each          = local.zones
  vpc_id            = aws_vpc.demo.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.name
}

resource "aws_security_group" "app" {
  name   = "dataforge-academy-app"
  vpc_id = aws_vpc.demo.id
}

resource "aws_vpc_security_group_ingress_rule" "web" {
  security_group_id = aws_security_group.app.id
  cidr_ipv4         = var.operator_cidr
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_egress_rule" "app" {
  security_group_id = aws_security_group.app.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "database" {
  name   = "dataforge-academy-database"
  vpc_id = aws_vpc.demo.id
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_instance" "app" {
  ami                         = data.aws_ami.linux.id
  instance_type               = "t3.medium"
  subnet_id                   = aws_subnet.app.id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.app.id]
  iam_instance_profile        = "LabInstanceProfile"
  user_data                   = file("${path.module}/bootstrap.sh")
  user_data_replace_on_change = true

  depends_on = [aws_route_table_association.app, aws_vpc_security_group_egress_rule.app]

  credit_specification {
    cpu_credits = "standard"
  }

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    encrypted             = true
    delete_on_termination = true
  }

  tags = { Name = "dataforge-academy-app" }
}

resource "aws_db_subnet_group" "demo" {
  name       = "dataforge-academy"
  subnet_ids = [for subnet in aws_subnet.database : subnet.id]
}

resource "aws_db_instance" "metadata" {
  identifier                  = "dataforge-academy"
  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = "db.t4g.micro"
  allocated_storage           = 20
  storage_type                = "gp3"
  storage_encrypted           = true
  db_name                     = "dataforge"
  username                    = "dataforge_admin"
  manage_master_user_password = true
  publicly_accessible         = false
  multi_az                    = false
  db_subnet_group_name        = aws_db_subnet_group.demo.name
  vpc_security_group_ids      = [aws_security_group.database.id]
  backup_retention_period     = 1
  skip_final_snapshot         = true
}

resource "terraform_data" "bucket" {
  for_each = toset(["input", "bronze", "silver", "gold", "quarantine"])

  input = {
    name   = "dataforge-academy-${data.aws_caller_identity.current.account_id}-${each.key}"
    region = "us-east-1"
    owner  = data.aws_caller_identity.current.account_id
  }

  triggers_replace = [
    "dataforge-academy-${data.aws_caller_identity.current.account_id}-${each.key}",
    "us-east-1",
  ]

  provisioner "local-exec" {
    command = "bash \"${path.module}/bucket.sh\" ensure \"${self.input.name}\" \"${self.input.region}\" \"${self.input.owner}\""
  }

  provisioner "local-exec" {
    when    = destroy
    command = "bash \"${path.module}/bucket.sh\" delete \"${self.input.name}\" \"${self.input.region}\" \"${self.input.owner}\""
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  for_each                = terraform_data.bucket
  bucket                  = each.value.input.name
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

output "instance_id" {
  value = aws_instance.app.id
}

output "database_endpoint" {
  value = aws_db_instance.metadata.endpoint
}

output "buckets" {
  value = { for layer, bucket in terraform_data.bucket : layer => bucket.input.name }
}

