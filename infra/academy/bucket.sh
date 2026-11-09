#!/bin/bash
set -euo pipefail

action="$1"
bucket="$2"
region="$3"
owner="$4"

account=$(aws sts get-caller-identity --query Account --output text)
test "$account" = "$owner"
[[ "$bucket" == "dataforge-academy-${owner}-"* ]]

if [ "$action" = "ensure" ]; then
  existing=$(aws s3api list-buckets \
    --query "Buckets[?Name=='${bucket}'].Name" --output text)

  if [ -z "$existing" ]; then
    if [ "$region" = "us-east-1" ]; then
      aws s3api create-bucket --bucket "$bucket" --region "$region"
    else
      aws s3api create-bucket --bucket "$bucket" --region "$region" \
        --create-bucket-configuration "LocationConstraint=$region"
    fi
  fi

  aws s3api head-bucket --bucket "$bucket" \
    --expected-bucket-owner "$owner" --region "$region"

  aws s3api put-bucket-tagging --bucket "$bucket" \
    --expected-bucket-owner "$owner" --region "$region" \
    --tagging '{"TagSet":[{"Key":"Project","Value":"DataForge"},{"Key":"Environment","Value":"academy-demo"},{"Key":"ManagedBy","Value":"Terraform"}]}'

elif [ "$action" = "delete" ]; then
  aws s3api head-bucket --bucket "$bucket" \
    --expected-bucket-owner "$owner" --region "$region"
  # AWS rejects deletion of a bucket containing objects.
  aws s3api delete-bucket --bucket "$bucket" \
    --expected-bucket-owner "$owner" --region "$region"
else
  echo "Unknown action" >&2
  exit 1
fi

