import os
import requests
import json
import boto3
import pytest
from datetime import datetime

# Configure AWS clients for LocalStack
ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = REGION

cognito = boto3.client("cognito-idp", endpoint_url=ENDPOINT_URL)
dynamodb = boto3.resource("dynamodb", endpoint_url=ENDPOINT_URL)

API_ROUTER_URL = os.environ.get("API_ROUTER_URL", "http://localhost:9010")

def test_unauthenticated_access():
    """Verify that unauthenticated requests are rejected."""
    resp = requests.post(f"{API_ROUTER_URL}/v1/upload", json={"filename": "test.pdf", "sizeBytes": 100})
    assert resp.status_code == 401

def test_api_key_auth():
    """Verify that valid API key authentication works."""
    # 1. Create a user with an API key in DynamoDB
    user_id = "user_api_test"
    api_key = "sk_test_12345"
    table = dynamodb.Table("aipdf-users-dev")
    table.put_item(Item={
        "user_id": user_id,
        "api_key": api_key,
        "created_at": datetime.now().isoformat()
    })

    # 2. Call API with the key
    headers = {"X-API-Key": api_key}
    resp = requests.post(
        f"{API_ROUTER_URL}/v1/upload", 
        json={"filename": "test.pdf", "sizeBytes": 100},
        headers=headers
    )
    
    assert resp.status_code == 200
    assert "fileKey" in resp.json()
    assert user_id in resp.json()["fileKey"]

def test_cognito_mock_auth():
    """Verify that JWT auth works (using mock mode for local dev)."""
    # Use a dummy token. Since SKIP_AUTH_VERIFY=true is set on the server,
    # it won't actually check the signature or claims deeply.
    mock_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c3JfZGV2X3Rlc3QiLCJ1c2VybmFtZSI6ImRldnVzZXIifQ.dummy-sig"
    
    headers = {"Authorization": f"Bearer {mock_token}"}
    resp = requests.post(
        f"{API_ROUTER_URL}/v1/upload", 
        json={"filename": "test.pdf", "sizeBytes": 100},
        headers=headers
    )
    
    assert resp.status_code == 200
    assert "fileKey" in resp.json()
    assert "usr_dev_test" in resp.json()["fileKey"]
