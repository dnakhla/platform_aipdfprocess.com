import os
import pytest
import json
from unittest.mock import MagicMock, patch

# Set dummy env vars
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

@pytest.fixture
def mock_dynamo(mocker):
    mock = mocker.patch("app.dynamodb")
    table = MagicMock()
    mock.Table.return_value = table
    return table

@pytest.fixture
def mock_requests(mocker):
    mock = mocker.patch("requests.post")
    return mock

def test_process_job_success(mock_dynamo, mock_requests):
    from app import process_job
    
    job_id = "job-123"
    # Mock job item
    mock_dynamo.get_item.return_value = {
        "Item": {
            "job_id": job_id,
            "status": "PENDING",
            "input_key": "input.pdf",
            "operations": [
                {"type": "split", "params": {"start": 0, "end": 0}},
                {"type": "compress", "params": {}}
            ]
        }
    }
    
    # Mock worker responses
    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {"success": True, "outputKey": "out1.pdf"}
    
    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.json.return_value = {"success": True, "outputKey": "out2.pdf"}
    
    mock_requests.side_effect = [mock_resp1, mock_resp2]
    
    process_job(job_id)
    
    # Check if DynamoDB was updated correctly
    # 1st call: status to PROCESSING
    # 2nd call: current_step to 1
    # 3rd call: current_step to 2
    # 4th call: status to SUCCEEDED
    assert mock_dynamo.update_item.call_count == 4
    
    last_call = mock_dynamo.update_item.call_args_list[-1]
    assert ":s" in last_call.kwargs["ExpressionAttributeValues"]
    assert last_call.kwargs["ExpressionAttributeValues"][":s"] == "SUCCEEDED"
    assert last_call.kwargs["ExpressionAttributeValues"][":o"] == "out2.pdf"

def test_process_job_worker_failure(mock_dynamo, mock_requests):
    from app import process_job
    
    job_id = "job-failed"
    mock_dynamo.get_item.return_value = {
        "Item": {
            "job_id": job_id,
            "status": "PENDING",
            "input_key": "input.pdf",
            "operations": [{"type": "split"}]
        }
    }
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": False, "error": "Split failed"}
    mock_requests.return_value = mock_resp
    
    process_job(job_id)
    
    # Last call should be status to FAILED
    last_call = mock_dynamo.update_item.call_args_list[-1]
    assert last_call.kwargs["ExpressionAttributeValues"][":s"] == "FAILED"
    assert last_call.kwargs["ExpressionAttributeValues"][":e"] == "Split failed"
