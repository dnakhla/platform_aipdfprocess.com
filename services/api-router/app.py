import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
import requests
from boto3.dynamodb.conditions import Key
from fastapi import Depends, FastAPI, File, HTTPException, Request, Security, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from mangum import Mangum
from pydantic import BaseModel, Field

try:
    import stripe
except ImportError:  # pragma: no cover - exercised indirectly in tests via monkeypatch.
    stripe = None

app = FastAPI(title="AIPDF API Router", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# AWS Clients — endpoint_url wired for LocalStack
ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

s3_client = boto3.client("s3", endpoint_url=ENDPOINT_URL)
dynamodb = boto3.resource("dynamodb", endpoint_url=ENDPOINT_URL)
sqs_client = boto3.client("sqs", endpoint_url=ENDPOINT_URL)

# Environment Variables
INPUT_BUCKET = os.environ.get("INPUT_BUCKET", "aipdf-input-dev")
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET", "aipdf-output-dev")
ARTIFACTS_BUCKET = os.environ.get("ARTIFACTS_BUCKET", "aipdf-artifacts-dev")
JOBS_TABLE = os.environ.get("JOBS_TABLE", "aipdf-jobs-dev")
USERS_TABLE = os.environ.get("USERS_TABLE", "aipdf-users-dev")
JOB_QUEUE_URL = os.environ.get("JOB_QUEUE_URL", "")
FREE_PDFS_PER_MONTH = int(os.environ.get("FREE_PDFS_PER_MONTH", "5"))
PRICE_PER_PDF_CENTS = int(os.environ.get("PRICE_PER_PDF_CENTS", "100"))
BILLING_CURRENCY = os.environ.get("BILLING_CURRENCY", "usd")
BILLING_LEDGER_RECENT_LIMIT = int(os.environ.get("BILLING_LEDGER_RECENT_LIMIT", "10"))
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_SUCCESS_URL = os.environ.get("STRIPE_SUCCESS_URL", "")
STRIPE_CANCEL_URL = os.environ.get("STRIPE_CANCEL_URL", "")
ALLOW_UNVERIFIED_STRIPE_WEBHOOKS = os.environ.get("ALLOW_UNVERIFIED_STRIPE_WEBHOOKS", "false").lower() == "true"

def resolve_queue_url():
    """Discover actual SQS queue URL (handles LocalStack v3 URL format)."""
    try:
        resp = sqs_client.get_queue_url(QueueName="aipdf-job-queue-dev")
        url = resp["QueueUrl"]
        # Replace localhost.localstack.cloud with localstack for Docker networking
        url = url.replace("localhost.localstack.cloud", "localstack")
        return url
    except Exception:
        return JOB_QUEUE_URL

RESOLVED_QUEUE_URL = None

async def verify_api_key(api_key: str):
    """Verify API key against DynamoDB users table."""
    try:
        table = dynamodb.Table(USERS_TABLE)
        # Use Global Secondary Index for efficient lookup
        response = table.query(
            IndexName="ApiKeyIndex",
            KeyConditionExpression=Key("api_key").eq(api_key)
        )
        items = response.get("Items", [])
        if items:
            return {
                "user_id": items[0]["user_id"],
                "auth_type": "api_key",
                "api_key_id": api_key_fingerprint(api_key),
            }
    except Exception as e:
        print(f"API Key verification error: {e}")
    return None

async def verify_cognito_token(token: str):
    """Verify JWT from Cognito."""
    if os.environ.get("SKIP_AUTH_VERIFY") == "true":
        return {"user_id": "usr_dev_test", "auth_type": "jwt_mock", "api_key_id": None}
        
    try:
        # For LocalStack, we skip full signature verification as JWKS setup is complex
        unverified_claims = jwt.get_unverified_claims(token)
        user_id = unverified_claims.get("sub") or unverified_claims.get("username")
        if user_id:
            return {"user_id": user_id, "auth_type": "jwt", "api_key_id": None}
    except Exception as e:
        print(f"JWT verification error: {e}")
    return None

async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Security(api_key_header)
):
    if api_key:
        user = await verify_api_key(api_key)
        if user: return user

    if auth:
        user = await verify_cognito_token(auth.credentials)
        if user: return user

    raise HTTPException(status_code=401, detail="Missing or invalid authentication credentials")

class UploadRequest(BaseModel):
    filename: str
    contentType: str = "application/pdf"
    sizeBytes: int

class BatchUploadRequest(BaseModel):
    filenames: List[str]
    contentType: str = "application/pdf"

class ProcessOperation(BaseModel):
    type: str
    params: Dict[str, Any] = {}

class ProcessRequest(BaseModel):
    fileKey: Optional[str] = None
    fileKeys: Optional[List[str]] = None
    operations: List[ProcessOperation]


class BillingCheckoutRequest(BaseModel):
    pdfCredits: int = Field(default=10, ge=1, le=1000)
    successUrl: Optional[str] = None
    cancelUrl: Optional[str] = None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def month_key(dt: Optional[datetime] = None) -> str:
    return (dt or now_utc()).strftime("%Y-%m")


def as_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def api_key_fingerprint(api_key: str) -> str:
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    return f"ak_{digest[:12]}"


def stripe_value(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    getter = getattr(obj, "get", None)
    if callable(getter):
        try:
            value = getter(key, default)
        except TypeError:
            value = getter(key)
        return default if value is None else value
    return getattr(obj, key, default)


def load_user_item(user_id: str) -> Dict[str, Any]:
    table = dynamodb.Table(USERS_TABLE)
    response = table.get_item(Key={"user_id": user_id})
    item = response.get("Item") or {"user_id": user_id, "created_at": now_iso()}
    if "created_at" not in item:
        item["created_at"] = now_iso()
    return item


def persist_user_item(user_item: Dict[str, Any]) -> None:
    dynamodb.Table(USERS_TABLE).put_item(Item=user_item)


def normalize_monthly_usage(raw: Optional[Dict[str, Any]], month: Optional[str] = None) -> Dict[str, Any]:
    target_month = month or month_key()
    source = raw or {}
    if source.get("month") != target_month:
        return {
            "month": target_month,
            "free_reserved": 0,
            "free_completed": 0,
            "paid_completed": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "total_pdfs_completed": 0,
            "last_job_at": None,
        }
    return {
        "month": target_month,
        "free_reserved": as_int(source.get("free_reserved")),
        "free_completed": as_int(source.get("free_completed")),
        "paid_completed": as_int(source.get("paid_completed")),
        "completed_jobs": as_int(source.get("completed_jobs")),
        "failed_jobs": as_int(source.get("failed_jobs")),
        "total_pdfs_completed": as_int(source.get("total_pdfs_completed")),
        "last_job_at": source.get("last_job_at"),
    }


def normalize_api_key_usage(raw: Optional[Dict[str, Any]], month: Optional[str] = None) -> Dict[str, Any]:
    target_month = month or month_key()
    source = raw or {}
    if source.get("month") != target_month:
        return {
            "month": target_month,
            "completed_jobs": 0,
            "completed_pdfs": 0,
            "failed_jobs": 0,
            "last_job_id": None,
            "last_job_at": None,
        }
    return {
        "month": target_month,
        "completed_jobs": as_int(source.get("completed_jobs")),
        "completed_pdfs": as_int(source.get("completed_pdfs")),
        "failed_jobs": as_int(source.get("failed_jobs")),
        "last_job_id": source.get("last_job_id"),
        "last_job_at": source.get("last_job_at"),
    }


def normalize_billing_ledger(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    normalized = []
    for entry in raw:
        if isinstance(entry, dict) and entry.get("entryId"):
            normalized.append(dict(entry))
    return normalized


def has_billing_ledger_entry(user_item: Dict[str, Any], entry_id: str) -> bool:
    return any(entry.get("entryId") == entry_id for entry in normalize_billing_ledger(user_item.get("billing_ledger")))


def append_billing_ledger_entry(user_item: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    entry_id = entry.get("entryId")
    if not entry_id:
        raise ValueError("billing ledger entry requires entryId")

    ledger = normalize_billing_ledger(user_item.get("billing_ledger"))
    if any(existing.get("entryId") == entry_id for existing in ledger):
        user_item["billing_ledger"] = ledger
        return False

    ledger.append(entry)
    user_item["billing_ledger"] = ledger
    return True


def build_billing_ledger_summary(user_item: Dict[str, Any]) -> Dict[str, Any]:
    ledger = normalize_billing_ledger(user_item.get("billing_ledger"))
    recent = [dict(entry) for entry in reversed(ledger[-BILLING_LEDGER_RECENT_LIMIT:])]
    return {
        "entryCount": len(ledger),
        "lastEntryAt": recent[0]["createdAt"] if recent else None,
        "recent": recent,
    }


def build_billing_summary(user_item: Dict[str, Any], api_key_id: Optional[str] = None) -> Dict[str, Any]:
    monthly_usage = normalize_monthly_usage(user_item.get("monthly_usage"))
    free_consumed = monthly_usage["free_completed"] + monthly_usage["free_reserved"]
    free_remaining = max(0, FREE_PDFS_PER_MONTH - free_consumed)

    summary = {
        "creditBalance": as_int(user_item.get("credit_balance")),
        "freeTier": {
            "month": monthly_usage["month"],
            "limit": FREE_PDFS_PER_MONTH,
            "used": monthly_usage["free_completed"],
            "reserved": monthly_usage["free_reserved"],
            "remaining": free_remaining,
        },
        "usage": {
            "completedJobs": monthly_usage["completed_jobs"],
            "failedJobs": monthly_usage["failed_jobs"],
            "completedPdfs": monthly_usage["total_pdfs_completed"],
            "paidCompleted": monthly_usage["paid_completed"],
            "lastJobAt": monthly_usage["last_job_at"],
        },
        "ledger": build_billing_ledger_summary(user_item),
    }

    if api_key_id:
        api_key_usage = normalize_api_key_usage((user_item.get("api_key_usage") or {}).get(api_key_id))
        summary["currentApiKey"] = {
            "id": api_key_id,
            "month": api_key_usage["month"],
            "completedJobs": api_key_usage["completed_jobs"],
            "completedPdfs": api_key_usage["completed_pdfs"],
            "failedJobs": api_key_usage["failed_jobs"],
            "lastJobId": api_key_usage["last_job_id"],
            "lastJobAt": api_key_usage["last_job_at"],
        }

    return summary


def get_stripe_client():
    if stripe is None:
        raise HTTPException(status_code=503, detail="Stripe SDK is not installed")
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    if not STRIPE_SECRET_KEY.startswith("sk_test_"):
        raise HTTPException(status_code=503, detail="Stripe live mode is disabled for this environment")
    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


def ensure_stripe_customer(user_id: str, user_item: Dict[str, Any]) -> str:
    existing_customer_id = user_item.get("stripe_customer_id")
    if existing_customer_id:
        return existing_customer_id

    stripe_client = get_stripe_client()
    customer = stripe_client.Customer.create(
        metadata={"user_id": user_id},
        description=f"AIPDF customer {user_id}",
    )
    customer_id = customer["id"] if isinstance(customer, dict) else customer.id
    user_item["stripe_customer_id"] = customer_id
    user_item["billing_updated_at"] = now_iso()
    persist_user_item(user_item)
    return customer_id


def resolve_checkout_urls(request: Request, req: BillingCheckoutRequest) -> tuple[str, str]:
    origin = request.headers.get("origin", "").rstrip("/")
    success_url = req.successUrl or STRIPE_SUCCESS_URL
    cancel_url = req.cancelUrl or STRIPE_CANCEL_URL

    if not success_url and origin:
        success_url = f"{origin}/app?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
    if not cancel_url and origin:
        cancel_url = f"{origin}/app?checkout=cancelled"
    if not success_url or not cancel_url:
        raise HTTPException(status_code=400, detail="successUrl and cancelUrl are required when Stripe URLs are not configured")

    if "{CHECKOUT_SESSION_ID}" not in success_url:
        separator = "&" if "?" in success_url else "?"
        success_url = f"{success_url}{separator}session_id={{CHECKOUT_SESSION_ID}}"

    return success_url, cancel_url


def apply_credit_topup(user_id: str, checkout_session_id: str, credits: int, customer_id: Optional[str] = None) -> bool:
    user_item = load_user_item(user_id)
    processed_sessions = set(user_item.get("processed_checkout_session_ids") or [])
    if checkout_session_id in processed_sessions:
        return False

    credited_at = now_iso()
    processed_sessions.add(checkout_session_id)
    user_item["processed_checkout_session_ids"] = processed_sessions
    user_item["credit_balance"] = as_int(user_item.get("credit_balance")) + credits
    user_item["billing_updated_at"] = credited_at
    user_item["last_checkout_session_id"] = checkout_session_id
    user_item["last_credit_purchase"] = {
        "sessionId": checkout_session_id,
        "credits": credits,
        "creditedAt": credited_at,
    }
    if customer_id and not user_item.get("stripe_customer_id"):
        user_item["stripe_customer_id"] = customer_id
    append_billing_ledger_entry(
        user_item,
        {
            "entryId": f"topup:{checkout_session_id}",
            "type": "TOPUP",
            "createdAt": credited_at,
            "checkoutSessionId": checkout_session_id,
            "customerId": customer_id,
            "pdfCredits": credits,
            "creditDelta": credits,
            "creditBalanceAfter": user_item["credit_balance"],
            "reason": "stripe_checkout_completed",
        },
    )
    persist_user_item(user_item)
    return True


def reserve_billing_for_job(user: Dict[str, Any], pdf_count: int, job_id: str) -> Dict[str, Any]:
    user_item = load_user_item(user["user_id"])
    monthly_usage = normalize_monthly_usage(user_item.get("monthly_usage"))
    credit_balance = as_int(user_item.get("credit_balance"))
    free_remaining = max(
        0,
        FREE_PDFS_PER_MONTH - monthly_usage["free_completed"] - monthly_usage["free_reserved"],
    )
    free_reserved = min(pdf_count, free_remaining)
    paid_reserved = pdf_count - free_reserved

    if credit_balance < paid_reserved:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "billing_insufficient_credits",
                "message": "Free monthly quota is exhausted. Purchase more PDF credits to continue.",
                "requiredCredits": paid_reserved,
                "billing": build_billing_summary(user_item, user.get("api_key_id")),
            },
        )

    monthly_usage["free_reserved"] += free_reserved
    user_item["monthly_usage"] = monthly_usage
    user_item["credit_balance"] = credit_balance - paid_reserved
    reserved_at = now_iso()
    user_item["billing_updated_at"] = reserved_at
    free_remaining_after_reserve = max(
        0,
        FREE_PDFS_PER_MONTH - monthly_usage["free_completed"] - monthly_usage["free_reserved"],
    )
    append_billing_ledger_entry(
        user_item,
        {
            "entryId": f"reserve:{job_id}",
            "type": "RESERVE",
            "createdAt": reserved_at,
            "jobId": job_id,
            "month": monthly_usage["month"],
            "pdfCount": pdf_count,
            "freeReserved": free_reserved,
            "paidReserved": paid_reserved,
            "creditDelta": -paid_reserved,
            "creditBalanceAfter": user_item["credit_balance"],
            "freeReservedDelta": free_reserved,
            "freeReservedAfter": monthly_usage["free_reserved"],
            "freeRemainingAfter": free_remaining_after_reserve,
            "authType": user["auth_type"],
            "apiKeyId": user.get("api_key_id"),
            "reason": "job_reserved",
        },
    )
    persist_user_item(user_item)

    return {
        "jobId": job_id,
        "month": monthly_usage["month"],
        "status": "RESERVED",
        "pdfCount": pdf_count,
        "freeReserved": free_reserved,
        "paidReserved": paid_reserved,
        "authType": user["auth_type"],
        "apiKeyId": user.get("api_key_id"),
        "reservedAt": reserved_at,
        "creditBalanceAfterReserve": user_item["credit_balance"],
        "freeRemainingAfterReserve": free_remaining_after_reserve,
    }


def release_billing_reservation(user_id: str, reservation: Optional[Dict[str, Any]]) -> None:
    if not reservation:
        return

    entry_id = f"release:{reservation.get('jobId', '')}"
    user_item = load_user_item(user_id)
    if has_billing_ledger_entry(user_item, entry_id):
        return

    monthly_usage = normalize_monthly_usage(user_item.get("monthly_usage"), reservation.get("month"))
    free_released = as_int(reservation.get("freeReserved"))
    paid_released = as_int(reservation.get("paidReserved"))
    monthly_usage["free_reserved"] = max(0, monthly_usage["free_reserved"] - free_released)
    user_item["monthly_usage"] = monthly_usage
    user_item["credit_balance"] = as_int(user_item.get("credit_balance")) + paid_released
    released_at = now_iso()
    user_item["billing_updated_at"] = released_at
    append_billing_ledger_entry(
        user_item,
        {
            "entryId": entry_id,
            "type": "RELEASE",
            "createdAt": released_at,
            "jobId": reservation.get("jobId"),
            "month": monthly_usage["month"],
            "pdfCount": as_int(reservation.get("pdfCount")),
            "freeReleased": free_released,
            "paidReleased": paid_released,
            "creditDelta": paid_released,
            "creditBalanceAfter": user_item["credit_balance"],
            "freeReservedDelta": -free_released,
            "freeReservedAfter": monthly_usage["free_reserved"],
            "apiKeyId": reservation.get("apiKeyId"),
            "reason": "job_enqueue_failed",
        },
    )
    persist_user_item(user_item)


def should_apply_checkout_credits(event_type: Optional[str], session: Any) -> bool:
    if event_type == "checkout.session.async_payment_succeeded":
        return True
    if event_type != "checkout.session.completed":
        return False
    return stripe_value(session, "payment_status", "") == "paid"

@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-router"}

@app.post("/v1/upload")
async def get_upload_url(req: UploadRequest, user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    job_id = f"job_{uuid.uuid4().hex[:12]}"

    now = datetime.now(timezone.utc)
    date_path = now.strftime("%Y/%m/%d")
    file_key = f"input/{date_path}/{user_id}/{job_id}/{req.filename}"

    try:
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': INPUT_BUCKET,
                'Key': file_key,
                'ContentType': req.contentType
            },
            ExpiresIn=3600
        )

        return {
            "fileKey": file_key,
            "uploadUrl": presigned_url,
            "expiresAt": (now.timestamp() + 3600),
            "maxSizeBytes": 52428800
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/batch/upload")
async def get_batch_upload_urls(req: BatchUploadRequest, user: dict = Depends(get_current_user)):
    """Generate multiple presigned URLs for batch uploading 100+ files."""
    user_id = user["user_id"]
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    date_path = now.strftime("%Y/%m/%d")
    
    results = []
    for filename in req.filenames:
        file_key = f"input/{date_path}/{user_id}/{batch_id}/{filename}"
        try:
            url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': INPUT_BUCKET,
                    'Key': file_key,
                    'ContentType': req.contentType
                },
                ExpiresIn=7200 # Longer for batch
            )
            results.append({
                "filename": filename,
                "fileKey": file_key,
                "uploadUrl": url
            })
        except Exception as e:
            results.append({"filename": filename, "error": str(e)})
            
    return {
        "batchId": batch_id,
        "files": results,
        "expiresAt": (now.timestamp() + 7200)
    }

@app.post("/v1/upload/direct")
async def direct_upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Direct file upload for local dev — bypasses presigned URLs."""
    user_id = user["user_id"]
    job_id = f"job_{uuid.uuid4().hex[:12]}"

    now = datetime.now(timezone.utc)
    date_path = now.strftime("%Y/%m/%d")
    file_key = f"input/{date_path}/{user_id}/{job_id}/{file.filename}"

    try:
        contents = await file.read()
        s3_client.put_object(
            Bucket=INPUT_BUCKET,
            Key=file_key,
            Body=contents,
            ContentType=file.content_type or "application/pdf"
        )
        return {
            "fileKey": file_key,
            "sizeBytes": len(contents),
            "message": "File uploaded directly to S3"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Worker/Service URLs
AI_PLANNER_URL = os.environ.get("AI_PLANNER_URL", "http://ai-planner:8000")

class NLProcessRequest(BaseModel):
    fileKey: str
    prompt: str

@app.post("/v1/process/nl")
async def process_nl(req: NLProcessRequest, user: dict = Depends(get_current_user)):
    """Translate natural language to operations using ai-planner, then start the job."""
    try:
        # 1. Get plan from ai-planner
        print(f"Calling AI Planner at {AI_PLANNER_URL}/v1/process/nl")
        resp = requests.post(
            f"{AI_PLANNER_URL}/v1/process/nl",
            json={"fileKey": req.fileKey, "prompt": req.prompt},
            timeout=30
        )
        resp.raise_for_status()
        plan_data = resp.json()
        operations = plan_data.get("plan", [])
        
        if not operations:
            raise HTTPException(status_code=400, detail="Could not generate a plan for this request")
            
        # 2. Start the processing job using the generated operations
        process_req = ProcessRequest(fileKey=req.fileKey, operations=[
            ProcessOperation(type=op["type"], params=op.get("params", {})) for op in operations
        ])
        
        return await start_processing(process_req, user)
        
    except Exception as e:
        print(f"AI Process NL Error: {e}")
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=f"AI Planning + Processing failed: {str(e)}")

@app.post("/v1/process")
async def start_processing(req: ProcessRequest, user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    pdf_count = len(req.fileKeys) if req.fileKeys else 1

    if not req.fileKey and not req.fileKeys:
        raise HTTPException(status_code=400, detail="Must provide either fileKey or fileKeys")

    jobs_table = dynamodb.Table(JOBS_TABLE)
    billing_reservation = reserve_billing_for_job(user, pdf_count=pdf_count, job_id=job_id)

    job_item = {
        "job_id": job_id,
        "user_id": user_id,
        "status": "PENDING",
        "input_key": req.fileKey if req.fileKey else (req.fileKeys[0] if req.fileKeys else None),
        "input_keys": req.fileKeys if req.fileKeys else ([req.fileKey] if req.fileKey else []),
        "operations": [op.model_dump() for op in req.operations],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "total_steps": len(req.operations),
        "current_step": 0,
        "billing": billing_reservation,
    }

    try:
        jobs_table.put_item(Item=job_item)

        global RESOLVED_QUEUE_URL
        if not RESOLVED_QUEUE_URL:
            RESOLVED_QUEUE_URL = resolve_queue_url()
        
        if RESOLVED_QUEUE_URL:
            sqs_client.send_message(
                QueueUrl=RESOLVED_QUEUE_URL,
                MessageBody=str(job_id)
            )
        else:
            raise HTTPException(status_code=500, detail="Job queue is not configured")

        return {
            "jobId": job_id,
            "status": "PENDING",
            "queuedAt": job_item["created_at"],
            "billing": {
                "reserved": {
                    "pdfCount": billing_reservation["pdfCount"],
                    "free": billing_reservation["freeReserved"],
                    "paid": billing_reservation["paidReserved"],
                },
                "summary": build_billing_summary(load_user_item(user_id), user.get("api_key_id")),
            },
        }
    except Exception as e:
        release_billing_reservation(user_id, billing_reservation)
        try:
            jobs_table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET #s = :s, error_message = :e, updated_at = :u",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": "FAILED",
                    ":e": str(e),
                    ":u": now_iso(),
                },
            )
        except Exception:
            pass
        print(f"Start processing error: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/billing/summary")
async def billing_summary(user: dict = Depends(get_current_user)):
    user_item = load_user_item(user["user_id"])
    return {
        "userId": user["user_id"],
        "billing": build_billing_summary(user_item, user.get("api_key_id")),
        "pricing": {
            "currency": BILLING_CURRENCY,
            "pricePerPdfCents": PRICE_PER_PDF_CENTS,
            "freePdfsPerMonth": FREE_PDFS_PER_MONTH,
        },
    }


@app.post("/v1/billing/checkout")
async def create_billing_checkout(
    req: BillingCheckoutRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    stripe_client = get_stripe_client()
    user_item = load_user_item(user["user_id"])
    customer_id = ensure_stripe_customer(user["user_id"], user_item)
    success_url, cancel_url = resolve_checkout_urls(request, req)

    session = stripe_client.checkout.Session.create(
        mode="payment",
        customer=customer_id,
        client_reference_id=user["user_id"],
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[
            {
                "price_data": {
                    "currency": BILLING_CURRENCY,
                    "product_data": {
                        "name": "AIPDF PDF credits",
                        "description": f"{req.pdfCredits} PDF processing credits",
                    },
                    "unit_amount": PRICE_PER_PDF_CENTS,
                },
                "quantity": req.pdfCredits,
            }
        ],
        metadata={
            "user_id": user["user_id"],
            "pdf_credits": str(req.pdfCredits),
            "unit_price_cents": str(PRICE_PER_PDF_CENTS),
        },
    )

    return {
        "sessionId": session["id"] if isinstance(session, dict) else session.id,
        "checkoutUrl": session["url"] if isinstance(session, dict) else session.url,
        "pdfCredits": req.pdfCredits,
        "unitPriceCents": PRICE_PER_PDF_CENTS,
        "amountTotalCents": req.pdfCredits * PRICE_PER_PDF_CENTS,
        "currency": BILLING_CURRENCY,
    }


@app.post("/v1/billing/webhook")
async def stripe_billing_webhook(request: Request):
    stripe_client = get_stripe_client()
    payload = await request.body()

    if STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe_client.Webhook.construct_event(
                payload,
                request.headers.get("stripe-signature"),
                STRIPE_WEBHOOK_SECRET,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid Stripe webhook signature: {exc}")
    else:
        if not ALLOW_UNVERIFIED_STRIPE_WEBHOOKS:
            raise HTTPException(status_code=503, detail="STRIPE_WEBHOOK_SECRET is required for webhook handling")
        event = json.loads(payload.decode("utf-8"))

    event_type = stripe_value(event, "type")
    session = stripe_value(stripe_value(event, "data", {}), "object", {}) or {}

    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        if not should_apply_checkout_credits(event_type, session):
            return {
                "received": True,
                "eventType": event_type,
                "creditsApplied": False,
                "reason": "payment_not_settled",
            }

        metadata = stripe_value(session, "metadata", {}) or {}
        user_id = stripe_value(metadata, "user_id")
        credits = as_int(stripe_value(metadata, "pdf_credits"))
        if not user_id or credits < 1:
            raise HTTPException(status_code=400, detail="Stripe checkout session is missing billing metadata")

        credits_applied = apply_credit_topup(
            user_id=user_id,
            checkout_session_id=stripe_value(session, "id", ""),
            credits=credits,
            customer_id=stripe_value(session, "customer"),
        )
        return {"received": True, "eventType": event_type, "creditsApplied": credits_applied}

    return {"received": True, "eventType": event_type}

@app.get("/v1/status/{jobId}")
async def get_status(jobId: str):
    table = dynamodb.Table(JOBS_TABLE)

    try:
        response = table.get_item(Key={"job_id": jobId})
        if "Item" not in response:
            raise HTTPException(status_code=404, detail="Job not found")

        item = response["Item"]
        result = {
            "jobId": item["job_id"],
            "status": item["status"],
            "currentStep": int(item.get("current_step", 0)),
            "totalSteps": int(item.get("total_steps", 0)),
            "operations": item.get("operations", []),
            "startedAt": item.get("created_at"),
            "updatedAt": item.get("updated_at")
        }
        if item.get("error_message"):
            result["error"] = item["error_message"]
        return result
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@app.get("/v1/download/{jobId}")
async def get_download_url(jobId: str):
    table = dynamodb.Table(JOBS_TABLE)

    try:
        response = table.get_item(Key={"job_id": jobId})
        if "Item" not in response:
            raise HTTPException(status_code=404, detail="Job not found")

        item = response["Item"]
        if item["status"] != "SUCCEEDED":
            return {
                "jobId": jobId,
                "status": item["status"],
                "message": "Job is not yet complete or has failed"
            }

        output_key = item.get("output_key")
        if not output_key:
            raise HTTPException(status_code=500, detail="Output key missing in job record")

        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': ARTIFACTS_BUCKET,
                'Key': output_key
            },
            ExpiresIn=3600
        )

        return {
            "jobId": jobId,
            "status": "SUCCEEDED",
            "downloadUrl": presigned_url,
            "expiresAt": (datetime.now(timezone.utc).timestamp() + 3600),
            "outputKey": output_key
        }
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=f"Download URL generation failed: {str(e)}")

# Entry point for Lambda
handler = Mangum(app)
