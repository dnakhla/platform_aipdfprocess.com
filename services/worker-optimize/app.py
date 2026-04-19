import os
import pikepdf
import boto3
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Dict, Any

ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
s3_client = boto3.client("s3", endpoint_url=ENDPOINT_URL)

INPUT_BUCKET = os.environ.get("INPUT_BUCKET", "aipdf-input-dev")
ARTIFACTS_BUCKET = os.environ.get("ARTIFACTS_BUCKET", "aipdf-artifacts-dev")

http_app = FastAPI(title="Worker Optimize")

class InvokeRequest(BaseModel):
    jobId: str
    inputKey: str
    operation: Dict[str, Any]

@http_app.post("/invoke")
async def invoke(req: InvokeRequest):
    return handler(req.model_dump(), None)

@http_app.get("/health")
async def health():
    return {"status": "ok"}

def handler(event, context):
    job_id = event["jobId"]
    input_key = event["inputKey"]
    operation = event["operation"]
    op_type = operation["type"]
    params = operation.get("params", {})
    
    print(f"Worker optimize: {op_type} for job {job_id}")
    
    local_input = f"/tmp/input_{uuid.uuid4().hex}.pdf"
    source_bucket = ARTIFACTS_BUCKET if input_key.startswith("artifacts/") else INPUT_BUCKET
    
    try:
        s3_client.download_file(source_bucket, input_key, local_input)
        
        doc = pikepdf.open(local_input)
        
        input_size = os.path.getsize(local_input)

        if op_type == "compress":
            doc.remove_unreferenced_resources()
            
        elif op_type == "repair":
            # Opening and saving with pikepdf often repairs broken PDFs
            pass
            
        elif op_type == "linearize":
            # Handled in save
            pass
            
        elif op_type == "sanitize":
            # Remove metadata, annotations, etc.
            with doc.open_metadata() as meta:
                meta.clear()
            # More sanitization could be added here
            
        # Save output
        local_output = f"/tmp/output_{uuid.uuid4().hex}.pdf"
        save_kwargs = {}
        if op_type == "linearize":
            save_kwargs["linearize"] = True
        if op_type == "compress":
            save_kwargs["compress_streams"] = True
            save_kwargs["object_stream_mode"] = pikepdf.ObjectStreamMode.generate
        doc.save(local_output, **save_kwargs)
        doc.close()
        
        now = datetime.now(timezone.utc)
        date_path = now.strftime("%Y/%m/%d")
        output_key = f"artifacts/{date_path}/{job_id}/opt_{uuid.uuid4().hex[:8]}.pdf"
        
        s3_client.upload_file(local_output, ARTIFACTS_BUCKET, output_key)

        output_size = os.path.getsize(local_output)
        os.remove(local_input)
        os.remove(local_output)
        return {
            "jobId": job_id,
            "success": True,
            "outputKey": output_key,
            "metadata": {
                "optimized": True,
                "inputSize": input_size,
                "outputSize": output_size,
                "savedBytes": input_size - output_size,
            }
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "jobId": job_id,
            "success": False,
            "error": str(e)
        }
