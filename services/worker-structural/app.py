import os
import fitz # PyMuPDF
import boto3
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
s3_client = boto3.client("s3", endpoint_url=ENDPOINT_URL)

INPUT_BUCKET = os.environ.get("INPUT_BUCKET", "aipdf-input-dev")
ARTIFACTS_BUCKET = os.environ.get("ARTIFACTS_BUCKET", "aipdf-artifacts-dev")

http_app = FastAPI(title="Worker Structural")

class InvokeRequest(BaseModel):
    jobId: str
    inputKey: str
    inputKeys: Optional[List[str]] = None
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
    input_keys = event.get("inputKeys", [])
    operation = event["operation"]
    op_type = operation["type"]
    params = operation.get("params", {})
    
    print(f"Worker structural: {op_type} for job {job_id}")
    
    # If op_type is merge and we have multiple input_keys, use them all
    if op_type == "merge" and len(input_keys) > 1:
        # The first key becomes our local_input, others are additionalKeys
        input_key = input_keys[0]
        params["additionalKeys"] = input_keys[1:]
    
    # Download input
    local_input = f"/tmp/input_{uuid.uuid4().hex}.pdf"
    # Note: If input_key starts with artifacts/, it's from a previous step
    source_bucket = ARTIFACTS_BUCKET if input_key.startswith("artifacts/") else INPUT_BUCKET
    
    try:
        s3_client.download_file(source_bucket, input_key, local_input)
        
        doc = fitz.open(local_input)
        
        if op_type == "split":
            # Just as an example, split returns the first page or a range
            start = params.get("start", 0)
            end = params.get("end", 0)
            doc.select(range(start, end + 1))
            
        elif op_type == "merge":
            additional_keys = params.get("additionalKeys", [])
            if not additional_keys:
                raise ValueError("merge requires 'additionalKeys' param with at least one S3 key")
            failed = []
            for key in additional_keys:
                temp_add = f"/tmp/add_{uuid.uuid4().hex}.pdf"
                add_bucket = ARTIFACTS_BUCKET if key.startswith("artifacts/") else INPUT_BUCKET
                try:
                    s3_client.download_file(add_bucket, key, temp_add)
                    add_doc = fitz.open(temp_add)
                    doc.insert_pdf(add_doc)
                    add_doc.close()
                    os.remove(temp_add)
                except Exception as e:
                    failed.append(f"{key}: {e}")
                    print(f"Error merging {key}: {e}")
            if failed:
                raise ValueError(f"Failed to merge {len(failed)}/{len(additional_keys)} files: {'; '.join(failed)}")
            
        elif op_type == "rotate":
            degrees = params.get("degrees", 90)
            for page in doc:
                page.set_rotation(degrees)
                
        elif op_type == "remove_blank_pages":
            threshold = params.get("threshold", 0.01) # text length or similar
            pages_to_keep = []
            for i in range(len(doc)):
                page = doc[i]
                # A page is kept if it has text OR images OR drawings
                if page.get_text().strip() or len(page.get_images()) > 0 or len(page.get_drawings()) > 0:
                    pages_to_keep.append(i)
            
            if not pages_to_keep:
                # Keep at least one page if all are blank? Or let it be empty?
                # PyMuPDF doc.select([]) might fail or produce empty PDF.
                # For now, let's keep it as is.
                pass
            else:
                doc.select(pages_to_keep)
            
        elif op_type == "watermark":
            text = params.get("text", "WATERMARK")
            fontsize = params.get("fontsize", 48)
            color = params.get("color", [0.8, 0.8, 0.8])
            for page in doc:
                rect = page.rect
                center = fitz.Point(rect.width / 2, rect.height / 2)
                mat = fitz.Matrix(1, 0, 0, 1, 0, 0).prerotate(-45)
                page.insert_text(
                    fitz.Point(rect.width * 0.15, rect.height * 0.6),
                    text,
                    fontsize=fontsize,
                    color=color,
                    overlay=True,
                    morph=(center, mat),
                )

        elif op_type == "delete_pages":
            indices = params.get("indices", [])
            doc.delete_pages(indices)
            
        # Save output
        local_output = f"/tmp/output_{uuid.uuid4().hex}.pdf"
        doc.save(local_output)
        page_count = len(doc)
        doc.close()

        # Upload output to artifacts
        now = datetime.now(timezone.utc)
        date_path = now.strftime("%Y/%m/%d")
        output_key = f"artifacts/{date_path}/{job_id}/step_{uuid.uuid4().hex[:8]}.pdf"

        s3_client.upload_file(local_output, ARTIFACTS_BUCKET, output_key)

        # Cleanup
        os.remove(local_input)
        os.remove(local_output)

        return {
            "jobId": job_id,
            "success": True,
            "outputKey": output_key,
            "metadata": {
                "pages": page_count
            }
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "jobId": job_id,
            "success": False,
            "error": str(e)
        }
