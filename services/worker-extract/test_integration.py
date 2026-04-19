import os
import time
import uuid
import requests
import boto3
import fitz
import subprocess
import signal
import json

ENDPOINT_URL = "http://aipdf-localstack:4566"
REGION = "us-east-1"
WORKER_PORT = 9102

# Set env vars for the worker and for this test script
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = REGION
os.environ["AWS_ENDPOINT_URL"] = ENDPOINT_URL
os.environ["INPUT_BUCKET"] = "aipdf-input-dev"
os.environ["ARTIFACTS_BUCKET"] = "aipdf-artifacts-dev"

# Load actual .env for LLM if possible, otherwise it will skip LLM test
if os.path.exists("/home/node/.pennybot/workspace/projects/aipdf-platform/.env"):
    with open("/home/node/.pennybot/workspace/projects/aipdf-platform/.env", "r") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                os.environ[k] = v

s3 = boto3.client("s3", endpoint_url=ENDPOINT_URL, region_name=REGION)

def setup_worker():
    # Start the worker in a background process
    cmd = [
        "/home/node/.pennybot/workspace/projects/aipdf-platform/venv/bin/python3",
        "-m", "uvicorn", "app:http_app",
        "--host", "0.0.0.0",
        "--port", str(WORKER_PORT)
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = "/home/node/.pennybot/workspace/projects/aipdf-platform/services/worker-extract"
    proc = subprocess.Popen(cmd, env=env, cwd="/home/node/.pennybot/workspace/projects/aipdf-platform/services/worker-extract")
    # Wait for startup
    time.sleep(3)
    return proc

def test_extract_integration():
    # 1. Create a test PDF
    pdf_path = "/tmp/test_integration_ext_input.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50,50), "Integration Test Text Content")
    doc.save(pdf_path)
    doc.close()
    
    # 2. Upload to S3
    input_key = "test_integration_ext.pdf"
    s3.upload_file(pdf_path, "aipdf-input-dev", input_key)
    print(f"Uploaded input to {input_key}")
    
    # 3. Call worker for extract_text
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    payload = {
        "jobId": job_id,
        "inputKey": input_key,
        "operation": {
            "type": "extract_text",
            "params": {}
        }
    }
    
    print(f"Calling worker at localhost:{WORKER_PORT}")
    resp = requests.post(f"http://localhost:{WORKER_PORT}/invoke", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    output_key = data["outputKey"]
    print(f"Worker success. Output key: {output_key}")
    
    # 4. Verify output exists in S3 and has text
    local_output = "/tmp/test_integration_ext_output.txt"
    s3.download_file("aipdf-artifacts-dev", output_key, local_output)
    
    with open(local_output, "r") as f:
        text = f.read()
    assert "Integration Test Text Content" in text
    print("Integration test PASSED")
    
    # Cleanup
    os.remove(pdf_path)
    os.remove(local_output)

if __name__ == "__main__":
    p = None
    try:
        p = setup_worker()
        test_extract_integration()
    finally:
        if p:
            p.terminate()
            p.wait()
