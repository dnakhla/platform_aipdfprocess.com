#!/bin/bash
set -euo pipefail

echo "=== Initializing LocalStack resources ==="

ENDPOINT="http://localhost:4566"
REGION="us-east-1"

# S3 Buckets
for BUCKET in aipdf-input-dev aipdf-output-dev aipdf-artifacts-dev; do
  awslocal s3 mb "s3://$BUCKET" --region "$REGION" 2>/dev/null || true
  echo "Bucket: $BUCKET"
done

# DynamoDB Table
awslocal dynamodb create-table \
  --table-name aipdf-jobs-dev \
  --attribute-definitions AttributeName=job_id,AttributeType=S \
  --key-schema AttributeName=job_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION" 2>/dev/null || true
echo "Table: aipdf-jobs-dev"

# Users Table (for Auth/API Keys)
awslocal dynamodb create-table \
  --table-name aipdf-users-dev \
  --attribute-definitions AttributeName=user_id,AttributeType=S AttributeName=api_key,AttributeType=S \
  --key-schema AttributeName=user_id,KeyType=HASH \
  --global-secondary-indexes \
      "[{\"IndexName\": \"ApiKeyIndex\", \"KeySchema\": [{\"AttributeName\": \"api_key\", \"KeyType\": \"HASH\"}], \"Projection\": {\"ProjectionType\": \"ALL\"}}]" \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION" 2>/dev/null || true
echo "Table: aipdf-users-dev"

# SQS Queue
awslocal sqs create-queue \
  --queue-name aipdf-job-queue-dev \
  --region "$REGION" 2>/dev/null || true
echo "Queue: aipdf-job-queue-dev"

# Cognito User Pool
POOL_ID=$(awslocal cognito-idp create-user-pool --pool-name aipdf-users-dev --region "$REGION" --query "UserPool.Id" --output text)
echo "UserPoolId: $POOL_ID"

# Cognito Client
CLIENT_ID=$(awslocal cognito-idp create-user-pool-client --user-pool-id "$POOL_ID" --client-name aipdf-client-dev --region "$REGION" --query "UserPoolClient.UserPoolClientId" --output text)
echo "UserPoolClientId: $CLIENT_ID"

# Save IDs for other services to pick up if needed (optional, but good for local dev)
echo "COGNITO_USER_POOL_ID=$POOL_ID" > /tmp/cognito_ids.env
echo "COGNITO_CLIENT_ID=$CLIENT_ID" >> /tmp/cognito_ids.env

echo "=== LocalStack init complete ==="
