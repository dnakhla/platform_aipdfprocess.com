import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from mangum import Mangum
import requests

app = FastAPI(title="AIPDF AI Planner", version="1.0.0")

# Environment
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "google/gemini-2.0-flash-exp:free")

SYSTEM_PROMPT = """
You are the AIPDF AI Planner. Your job is to translate a user's natural language request into a sequence of PDF operations.
Available operations:
- split(pages): list of 1-based page numbers to extract
- merge(additionalKeys): list of S3 keys to merge with
- rotate(angle, pages): rotate specific pages by angle (90, 180, 270)
- remove_blank_pages(): remove empty pages
- delete_pages(pages): list of 1-based page numbers to delete
- extract_text(ocr=True/False, pages): get text from PDF
- ocr(pages): perform OCR on specific pages
- compress(quality): reduce file size (low, medium, high)
- repair(): fix broken PDF
- sanitize(): remove metadata and sensitive info
- extract_table(pages): extract tables from pages to CSV
- extract_structured(schema, pages): extract structured data from pages according to schema (JSON)

IMPORTANT:
- Always use the 'pages' parameter (list of 1-based integers) if the user mentions specific pages or a range.
- For extraction tasks (text, table, structured), use 'ocr': true if the document might be scanned.
- If the user's request is vague, pick the most likely operations.

Return ONLY a JSON array of operations. Example:
[{"type": "remove_blank_pages", "params": {}}, {"type": "extract_table", "params": {"pages": [1, 2], "ocr": true}}]
"""

class NLProcessRequest(BaseModel):
    fileKey: str
    prompt: str

@app.post("/v1/process/nl")
async def process_nl(req: NLProcessRequest):
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")
        
    # 1. Call LLM to plan
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aipdfprocessing.946nl.online",
                "X-Title": "AIPDF AI Planner"
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": req.prompt}
                ]
            }
        )
        response.raise_for_status()
        plan_text = response.json()["choices"][0]["message"]["content"]
        
        # Extract JSON if LLM added markdown
        if "```json" in plan_text:
            plan_text = plan_text.split("```json")[1].split("```")[0].strip()
        elif "```" in plan_text:
            plan_text = plan_text.split("```")[1].split("```")[0].strip()
            
        operations = json.loads(plan_text)
    except Exception as e:
        print(f"Planning Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Planning failed: {str(e)}")
        
    return {
        "plan": operations,
        "message": "Plan generated successfully."
    }

handler = Mangum(app)
