import os
import fitz # PyMuPDF
import boto3
import uuid
import json
import subprocess
import zipfile
import requests
from datetime import datetime, timezone
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
s3_client = boto3.client("s3", endpoint_url=ENDPOINT_URL)

INPUT_BUCKET = os.environ.get("INPUT_BUCKET", "aipdf-input-dev")
ARTIFACTS_BUCKET = os.environ.get("ARTIFACTS_BUCKET", "aipdf-artifacts-dev")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL", "google/gemini-2.0-flash-exp:free")

http_app = FastAPI(title="Worker Extract")

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

def ocr_page(page):
    """Simple OCR using tesseract binary"""
    pix = page.get_pixmap()
    temp_img = f"/tmp/page_{uuid.uuid4().hex}.png"
    pix.save(temp_img)
    
    output_base = f"/tmp/ocr_{uuid.uuid4().hex}"
    try:
        subprocess.run(["tesseract", temp_img, output_base], check=True)
        with open(f"{output_base}.txt", "r") as f:
            text = f.read()
        
        # Cleanup
        os.remove(temp_img)
        os.remove(f"{output_base}.txt")
        return text
    except Exception as e:
        print(f"OCR Error: {str(e)}")
        return ""

def llm_structured_extract(text, schema=None, prompt_type="table"):
    if not OPENROUTER_API_KEY:
        return f"ERROR: OPENROUTER_API_KEY not set. Prompt: {prompt_type}"
    
    if prompt_type == "extract_table":
        system_prompt = "You are an expert at extracting tables from text. Return the table in CSV format. Only return the CSV, no other text. If there are multiple tables, separate them with a blank line."
        user_prompt = f"Extract the tables from the following text and convert them to CSV:\n\n{text}"
    else:
        system_prompt = f"You are an expert at extracting structured data from text. Extract data according to this schema: {json.dumps(schema) if schema else 'Identify key entities and values'}. Return as JSON."
        user_prompt = f"Extract structured data from the following text:\n\n{text}"

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aipdfprocessing.946nl.online",
                "X-Title": "AIPDF Processing"
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        
        # Clean markdown if LLM adds it
        if "```" in content:
            if "```csv" in content:
                content = content.split("```csv")[1].split("```")[0].strip()
            elif "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            else:
                content = content.split("```")[1].split("```")[0].strip()
                
        return content
    except Exception as e:
        return f"LLM Error: {str(e)}"

def handler(event, context):
    job_id = event["jobId"]
    input_key = event["inputKey"]
    input_keys = event.get("inputKeys", [])
    operation = event["operation"]
    op_type = operation["type"]
    params = operation.get("params", {})
    
    print(f"Worker extract: {op_type} for job {job_id}")
    
    # Batch mode: if input_keys are provided, loop through them
    is_batch = len(input_keys) > 1
    process_keys = input_keys if is_batch else [input_key]
    
    # We'll collect multiple outputs in a ZIP if batch
    batch_results = []
    downloaded_files = []
    
    try:
        for key in process_keys:
            local_input = f"/tmp/input_{uuid.uuid4().hex}.pdf"
            source_bucket = ARTIFACTS_BUCKET if key.startswith("artifacts/") else INPUT_BUCKET
            
            s3_client.download_file(source_bucket, key, local_input)
            downloaded_files.append(local_input)
            doc = fitz.open(local_input)
            
            result_content = ""
            output_format = "txt"
            skip_write = False
            
            pages = params.get("pages", [])
            page_indices = [p - 1 for p in pages if 0 < p <= len(doc)] if pages else range(len(doc))
                
            if op_type == "extract_text":
                use_ocr = params.get("ocr", False)
                for idx in page_indices:
                    page = doc[idx]
                    text = page.get_text()
                    if not text.strip() and use_ocr:
                        text = ocr_page(page)
                    result_content += f"--- Page {idx+1} ---\n{text}\n"
                    
            elif op_type == "ocr":
                for idx in page_indices:
                    page = doc[idx]
                    result_content += f"--- Page {idx+1} ---\n{ocr_page(page)}\n"
                    
            elif op_type == "metadata":
                result_content = json.dumps(doc.metadata, indent=2)
                output_format = "json"
                
            elif op_type in ["extract_table", "extract_structured"]:
                full_text = ""
                use_ocr = params.get("ocr", True)
                for idx in page_indices:
                    page = doc[idx]
                    text = page.get_text()
                    if not text.strip() and use_ocr:
                        text = ocr_page(page)
                    full_text += text + "\n"
                schema = params.get("schema")
                result_content = llm_structured_extract(full_text, schema, op_type)
                output_format = "csv" if op_type == "extract_table" else "json"
                
            elif op_type == "page_to_image":
                dpi = params.get("dpi", 150)
                img_format = params.get("format", "png")
                # Handled below if is_batch

            elif op_type == "extract_images":
                # Handled below if is_batch
                pass

            if is_batch:
                filename = os.path.basename(key).replace(".pdf", "")
                batch_results.append({
                    "name": f"{filename}.{output_format}",
                    "content": result_content,
                    "doc": doc,
                    "indices": page_indices
                })
            else:
                # Single file logic
                if op_type in ["page_to_image", "extract_images"]:
                    output_format = "zip"
                    local_output = f"/tmp/extract_{uuid.uuid4().hex}.zip"
                    with zipfile.ZipFile(local_output, 'w') as zf:
                        if op_type == "page_to_image":
                            dpi = params.get("dpi", 150)
                            img_format = params.get("format", "png")
                            for idx in page_indices:
                                page = doc[idx]
                                pix = page.get_pixmap(dpi=dpi)
                                zf.writestr(f"page_{idx+1}.{img_format}", pix.tobytes(output=img_format))
                        else: # extract_images
                            for idx in page_indices:
                                page = doc[idx]
                                for img_index, img in enumerate(page.get_images()):
                                    base_image = doc.extract_image(img[0])
                                    zf.writestr(f"page_{idx+1}_img_{img_index+1}.{base_image['ext']}", base_image["image"])
                else:
                    local_output = f"/tmp/output_{uuid.uuid4().hex}.{output_format}"
                    with open(local_output, "w") as f:
                        f.write(result_content)
                doc.close()

        # Final Batch Assembly
        if is_batch:
            output_format = "zip"
            local_output = f"/tmp/batch_{uuid.uuid4().hex}.zip"
            with zipfile.ZipFile(local_output, 'w') as bzf:
                for res in batch_results:
                    if op_type in ["extract_text", "ocr", "metadata", "extract_table", "extract_structured"]:
                        bzf.writestr(res["name"], res["content"])
                    elif op_type == "page_to_image":
                        dpi = params.get("dpi", 150)
                        img_format = params.get("format", "png")
                        base = res["name"].replace(f".{output_format}", "")
                        for idx in res["indices"]:
                            page = res["doc"][idx]
                            pix = page.get_pixmap(dpi=dpi)
                            bzf.writestr(f"{base}/page_{idx+1}.{img_format}", pix.tobytes(output=img_format))
                    elif op_type == "extract_images":
                        base = res["name"].replace(f".{output_format}", "")
                        for idx in res["indices"]:
                            page = res["doc"][idx]
                            for img_index, img in enumerate(page.get_images()):
                                base_image = res["doc"].extract_image(img[0])
                                bzf.writestr(f"{base}/page_{idx+1}_img_{img_index+1}.{base_image['ext']}", base_image["image"])
                    res["doc"].close()

        now = datetime.now(timezone.utc)
        date_path = now.strftime("%Y/%m/%d")
        file_suffix = f"batch_{uuid.uuid4().hex[:8]}" if is_batch else f"extract_{uuid.uuid4().hex[:8]}"
        output_key = f"artifacts/{date_path}/{job_id}/{file_suffix}.{output_format}"
        
        s3_client.upload_file(local_output, ARTIFACTS_BUCKET, output_key)
        
        # Cleanup
        os.remove(local_output)
        for f in downloaded_files:
            if os.path.exists(f): os.remove(f)
        
        return {
            "jobId": job_id,
            "success": True,
            "outputKey": output_key,
            "metadata": {
                "format": output_format,
                "batch": is_batch,
                "fileCount": len(process_keys)
            }
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        # Cleanup on error
        for f in downloaded_files:
            if os.path.exists(f): os.remove(f)
        return {
            "jobId": job_id,
            "success": False,
            "error": str(e)
        }
