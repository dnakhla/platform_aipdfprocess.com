import os
import pytest
import shutil
import uuid
import fitz
from unittest.mock import MagicMock, patch

# Set dummy env vars for the worker import
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"
os.environ["INPUT_BUCKET"] = "aipdf-input-dev"
os.environ["ARTIFACTS_BUCKET"] = "aipdf-artifacts-dev"

# Now we can import the worker handler
# Since the handler depends on s3_client which is created at module level,
# we need to be careful.

@pytest.fixture
def mock_s3(mocker):
    mock = mocker.patch("app.s3_client")
    return mock

@pytest.fixture
def test_pdf():
    path = "/tmp/test_unit.pdf"
    doc = fitz.open()
    # Page 1: with text
    p1 = doc.new_page()
    p1.insert_text((50, 50), "Test Page 1")
    # Page 2: with text
    p2 = doc.new_page()
    p2.insert_text((50, 50), "Test Page 2")
    # Page 3: blank
    p3 = doc.new_page()
    doc.save(path)
    doc.close()
    yield path
    if os.path.exists(path):
        os.remove(path)

def test_handler_rotate(mock_s3, test_pdf):
    from app import handler
    
    # Mock download
    mock_s3.download_file.side_effect = lambda bucket, key, dest: shutil.copy(test_pdf, dest)
    
    event = {
        "jobId": "test-job-1",
        "inputKey": "test.pdf",
        "operation": {
            "type": "rotate",
            "params": {"degrees": 90}
        }
    }
    
    res = handler(event, None)
    
    assert res["success"] is True
    assert "outputKey" in res
    assert mock_s3.upload_file.called
    assert res["metadata"]["pages"] == 3

def test_handler_split(mock_s3, test_pdf):
    from app import handler
    
    mock_s3.download_file.side_effect = lambda bucket, key, dest: shutil.copy(test_pdf, dest)
    
    event = {
        "jobId": "test-job-2",
        "inputKey": "test.pdf",
        "operation": {
            "type": "split",
            "params": {"start": 0, "end": 0} # Get only 1st page
        }
    }
    
    res = handler(event, None)
    
    assert res["success"] is True
    assert res["metadata"]["pages"] == 1

def test_handler_remove_blank_pages(mock_s3, test_pdf):
    from app import handler
    
    mock_s3.download_file.side_effect = lambda bucket, key, dest: shutil.copy(test_pdf, dest)
    
    event = {
        "jobId": "test-job-3",
        "inputKey": "test.pdf",
        "operation": {
            "type": "remove_blank_pages",
            "params": {}
        }
    }
    
    res = handler(event, None)
    
    assert res["success"] is True
    # Initial 3 pages: P1 (text), P2 (text), P3 (blank).
    # Expected: 2 pages left.
    assert res["metadata"]["pages"] == 2

def test_handler_delete_pages(mock_s3, test_pdf):
    from app import handler
    
    mock_s3.download_file.side_effect = lambda bucket, key, dest: shutil.copy(test_pdf, dest)
    
    event = {
        "jobId": "test-job-4",
        "inputKey": "test.pdf",
        "operation": {
            "type": "delete_pages",
            "params": {"indices": [1, 2]} # Delete P2 and P3
        }
    }
    
    res = handler(event, None)
    
    assert res["success"] is True
    assert res["metadata"]["pages"] == 1
