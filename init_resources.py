import boto3
import time
import os

ENDPOINT_URL = "http://aipdf-localstack:4566"
REGION = "us-east-1"

# Set credentials to avoid boto3 errors
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = REGION

s3 = boto3.client("s3", endpoint_url=ENDPOINT_URL, region_name=REGION)
dynamodb = boto3.client("dynamodb", endpoint_url=ENDPOINT_URL, region_name=REGION)
sqs = boto3.client("sqs", endpoint_url=ENDPOINT_URL, region_name=REGION)

def init():
    # S3 Buckets
    for bucket in ["aipdf-input-dev", "aipdf-output-dev", "aipdf-artifacts-dev"]:
        try:
            s3.create_bucket(Bucket=bucket)
            print(f"Bucket {bucket} created")
        except Exception as e:
            print(f"Error creating bucket {bucket}: {e}")

    # DynamoDB Table
    try:
        dynamodb.create_table(
            TableName="aipdf-jobs-dev",
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST"
        )
        print("Table aipdf-jobs-dev created")
    except Exception as e:
        print(f"Error creating table: {e}")

    # SQS Queue
    try:
        sqs.create_queue(QueueName="aipdf-job-queue-dev")
        print("Queue aipdf-job-queue-dev created")
    except Exception as e:
        print(f"Error creating queue: {e}")

if __name__ == "__main__":
    init()
