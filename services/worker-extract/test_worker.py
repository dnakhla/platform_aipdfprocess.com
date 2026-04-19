import os
import pytest
import shutil
import uuid
import fitz
import json
from unittest.mock import MagicMock, patch

# Set dummy env vars for the worker import
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"
os.environ["INPUT_BUCKET"] = "aipdf-input-dev"
os.environ["ARTIFACTS_BUCKET"] = "aipdf-artifacts-dev"
os.environ["OPENROUTER_API_KEY"] = "sk-test"

@pytest.fixture
def mock_s3(mocker):
    mock = mocker.patch("app.s3_client")
    return mock

@pytest.fixture
def test_pdf():
    path = "/tmp/test_extract.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Sample Text for Extraction")
    doc.save(path)
    doc.close()
    yield path
    if os.path.exists(path):
        os.remove(path)

def test_handler_extract_text(mock_s3, test_pdf):
    from app import handler
    
    mock_s3.download_file.side_effect = lambda bucket, key, dest: shutil.copy(test_pdf, dest)
    
    event = {
        "jobId": "test-job-ext-1",
        "inputKey": "test.pdf",
        "operation": {
            "type": "extract_text",
            "params": {}
        }
    }
    
    res = handler(event, None)
    
    assert res["success"] is True
    assert "outputKey" in res
    assert res["metadata"]["format"] == "txt"

def test_handler_metadata(mock_s3, test_pdf):
    from app import handler
    
    mock_s3.download_file.side_effect = lambda bucket, key, dest: shutil.copy(test_pdf, dest)
    
    event = {
        "jobId": "test-job-ext-2",
        "inputKey": "test.pdf",
        "operation": {
            "type": "metadata",
            "params": {}
        }
    }
    
    res = handler(event, None)
    
    assert res["success"] is True
    assert res["metadata"]["format"] == "json"

def test_handler_page_to_image(mock_s3, test_pdf):
    from app import handler
    
    mock_s3.download_file.side_effect = lambda bucket, key, dest: shutil.copy(test_pdf, dest)
    
    event = {
        "jobId": "test-job-ext-3",
        "inputKey": "test.pdf",
        "operation": {
            "type": "page_to_image",
            "params": {"dpi": 72, "format": "png"}
        }
    }
    
    res = handler(event, None)
    
    assert res["success"] is True
    assert res["metadata"]["format"] == "zip"

@patch("requests.post")
def test_handler_extract_table(mock_post, mock_s3, test_pdf):
    from app import handler
    
    # Mock LLM response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "col1,col2\nval1,val2"}}]
    }
    mock_post.return_value = mock_response
    
    mock_s3.download_file.side_effect = lambda bucket, key, dest: shutil.copy(test_pdf, dest)
    
    event = {
        "jobId": "test-job-ext-4",
        "inputKey": "test.pdf",
        "operation": {
            "type": "extract_table",
            "params": {}
        }
    }
    
    res = handler(event, None)
    
    assert res["success"] is True
    assert res["metadata"]["format"] == "csv"
    assert mock_post.called
