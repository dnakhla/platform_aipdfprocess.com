import os
import json
import boto3
import time
import requests
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == int(o) else float(o)
        return super().default(o)

localstack_host = os.environ.get("LOCALSTACK_HOST", "localstack")
# AWS Clients
ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", f"http://{localstack_host}:4566")
dynamodb = boto3.resource("dynamodb", endpoint_url=ENDPOINT_URL)
sqs_client = boto3.client("sqs", endpoint_url=ENDPOINT_URL)

# Environment Variables
JOBS_TABLE = os.environ.get("JOBS_TABLE", "aipdf-jobs-dev")
USERS_TABLE = os.environ.get("USERS_TABLE", "aipdf-users-dev")
JOB_QUEUE_URL = os.environ.get("JOB_QUEUE_URL", f"http://{localstack_host}:4566/000000000000/aipdf-job-queue-dev")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))

# Worker URLs (HTTP endpoints for local dev)
WORKER_STRUCTURAL_URL = os.environ.get("WORKER_STRUCTURAL_URL", "http://worker-structural:9001")
WORKER_EXTRACT_URL = os.environ.get("WORKER_EXTRACT_URL", "http://worker-extract:9002")
WORKER_OPTIMIZE_URL = os.environ.get("WORKER_OPTIMIZE_URL", "http://worker-optimize:9003")

# Mapping operations to worker URLs
WORKER_MAPPING = {
    "split": WORKER_STRUCTURAL_URL,
    "merge": WORKER_STRUCTURAL_URL,
    "rotate": WORKER_STRUCTURAL_URL,
    "watermark": WORKER_STRUCTURAL_URL,
    "remove_blank_pages": WORKER_STRUCTURAL_URL,
    "delete_pages": WORKER_STRUCTURAL_URL,
    "extract_text": WORKER_EXTRACT_URL,
    "ocr": WORKER_EXTRACT_URL,
    "extract_images": WORKER_EXTRACT_URL,
    "page_to_image": WORKER_EXTRACT_URL,
    "metadata": WORKER_EXTRACT_URL,
    "extract_table": WORKER_EXTRACT_URL,
    "extract_structured": WORKER_EXTRACT_URL,
    "compress": WORKER_OPTIMIZE_URL,
    "repair": WORKER_OPTIMIZE_URL,
    "linearize": WORKER_OPTIMIZE_URL,
    "sanitize": WORKER_OPTIMIZE_URL,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def month_key(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now(timezone.utc)).strftime("%Y-%m")


def as_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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


def normalize_billing_ledger(raw: Any) -> list[Dict[str, Any]]:
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


def finalize_billing(job: Dict[str, Any], success: bool) -> Optional[Dict[str, Any]]:
    reservation = dict(job.get("billing") or {})
    if not reservation:
        return None
    if reservation.get("finalizedAt"):
        return reservation

    user_item = load_user_item(job["user_id"])
    ledger_entry_id = f"finalize:{job['job_id']}:{'success' if success else 'refund'}"
    processed_jobs = set(user_item.get("processed_billing_job_ids") or [])
    if job["job_id"] in processed_jobs:
        reservation["finalizedAt"] = reservation.get("finalizedAt") or now_iso()
        reservation["finalState"] = reservation.get("finalState") or ("SUCCEEDED" if success else "REFUNDED")
        return reservation
    if has_billing_ledger_entry(user_item, ledger_entry_id):
        reservation["finalizedAt"] = reservation.get("finalizedAt") or now_iso()
        reservation["finalState"] = reservation.get("finalState") or ("SUCCEEDED" if success else "REFUNDED")
        return reservation

    finalized_at = now_iso()
    month = reservation.get("month")
    monthly_usage = normalize_monthly_usage(user_item.get("monthly_usage"), month)
    free_reserved = as_int(reservation.get("freeReserved"))
    paid_reserved = as_int(reservation.get("paidReserved"))
    pdf_count = as_int(reservation.get("pdfCount"))

    monthly_usage["free_reserved"] = max(0, monthly_usage["free_reserved"] - free_reserved)
    if success:
        monthly_usage["free_completed"] += free_reserved
        monthly_usage["paid_completed"] += paid_reserved
        monthly_usage["completed_jobs"] += 1
        monthly_usage["total_pdfs_completed"] += pdf_count
    else:
        user_item["credit_balance"] = as_int(user_item.get("credit_balance")) + paid_reserved
        monthly_usage["failed_jobs"] += 1
    monthly_usage["last_job_at"] = finalized_at
    user_item["monthly_usage"] = monthly_usage

    api_key_id = reservation.get("apiKeyId")
    if api_key_id:
        usage_map = dict(user_item.get("api_key_usage") or {})
        api_key_usage = normalize_api_key_usage(usage_map.get(api_key_id), month)
        if success:
            api_key_usage["completed_jobs"] += 1
            api_key_usage["completed_pdfs"] += pdf_count
        else:
            api_key_usage["failed_jobs"] += 1
        api_key_usage["last_job_id"] = job["job_id"]
        api_key_usage["last_job_at"] = finalized_at
        usage_map[api_key_id] = api_key_usage
        user_item["api_key_usage"] = usage_map

    append_billing_ledger_entry(
        user_item,
        {
            "entryId": ledger_entry_id,
            "type": "FINALIZE_SUCCESS" if success else "FINALIZE_REFUND",
            "createdAt": finalized_at,
            "jobId": job["job_id"],
            "month": monthly_usage["month"],
            "pdfCount": pdf_count,
            "freeReservedReleased": free_reserved,
            "paidReservedReleased": paid_reserved,
            "creditDelta": 0 if success else paid_reserved,
            "creditBalanceAfter": as_int(user_item.get("credit_balance")),
            "freeReservedDelta": -free_reserved,
            "freeReservedAfter": monthly_usage["free_reserved"],
            "freeCompletedDelta": free_reserved if success else 0,
            "freeCompletedAfter": monthly_usage["free_completed"],
            "paidCompletedDelta": paid_reserved if success else 0,
            "paidCompletedAfter": monthly_usage["paid_completed"],
            "completedJobsDelta": 1 if success else 0,
            "failedJobsDelta": 0 if success else 1,
            "totalPdfsCompletedDelta": pdf_count if success else 0,
            "apiKeyId": api_key_id,
            "reason": "job_succeeded" if success else "job_failed",
        },
    )
    processed_jobs.add(job["job_id"])
    user_item["processed_billing_job_ids"] = processed_jobs
    user_item["billing_updated_at"] = finalized_at
    persist_user_item(user_item)

    reservation["finalizedAt"] = finalized_at
    reservation["finalState"] = "SUCCEEDED" if success else "REFUNDED"
    return reservation


def process_job(job_id):
    table = dynamodb.Table(JOBS_TABLE)

    response = table.get_item(Key={"job_id": job_id})
    if "Item" not in response:
        print(f"Job {job_id} not found")
        return

    job = response["Item"]
    if job["status"] not in ["PENDING", "PROCESSING"]:
        billing = job.get("billing") or {}
        if billing and not billing.get("finalizedAt"):
            finalized = finalize_billing(job, success=(job["status"] == "SUCCEEDED"))
            table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET billing = :b, updated_at = :u",
                ExpressionAttributeValues={
                    ":b": finalized,
                    ":u": now_iso(),
                },
            )
        print(f"Job {job_id} already in final state: {job['status']}")
        return

    # Update status to PROCESSING
    table.update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #s = :s, updated_at = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "PROCESSING",
            ":u": now_iso()
        }
    )

    current_input_key = job["input_key"]
    input_keys = job.get("input_keys", [current_input_key])
    operations = job.get("operations", [])
    success = True
    error_msg = ""

    for i, op in enumerate(operations):
        op_type = op["type"]
        worker_url = WORKER_MAPPING.get(op_type)

        if not worker_url:
            print(f"Unknown operation type: {op_type}")
            success = False
            error_msg = f"Unknown operation: {op_type}"
            break

        # Update current step
        table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET current_step = :c, updated_at = :u",
            ExpressionAttributeValues={
                ":c": i + 1,
                ":u": now_iso()
            }
        )

        # Call worker via HTTP
        payload = {
            "jobId": job_id,
            "inputKey": current_input_key,
            "operation": op
        }
        
        # If it's a batch operation or first operation with multiple inputs
        if i == 0 and len(input_keys) > 1:
            payload["inputKeys"] = input_keys

        print(f"Calling worker {worker_url} for {op_type}")
        try:
            resp = requests.post(
                f"{worker_url}/invoke",
                data=json.dumps(payload, cls=DecimalEncoder),
                headers={"Content-Type": "application/json"},
                timeout=120
            )
            resp.raise_for_status()
            result = resp.json()
        except Exception as e:
            print(f"Worker call failed: {e}")
            success = False
            error_msg = f"Worker call failed: {e}"
            break

        if not result.get("success"):
            print(f"Worker failed: {result.get('error')}")
            success = False
            error_msg = result.get("error", "Worker failed")
            break

        current_input_key = result["outputKey"]

    # Finalize job
    finalized_billing = finalize_billing(job, success=success)
    if success:
        update_expression = "SET #s = :s, output_key = :o, updated_at = :u"
        expression_values = {
            ":s": "SUCCEEDED",
            ":o": current_input_key,
            ":u": now_iso(),
        }
        if finalized_billing is not None:
            update_expression += ", billing = :b"
            expression_values[":b"] = finalized_billing
        table.update_item(
            Key={"job_id": job_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues=expression_values,
        )
        print(f"Job {job_id} SUCCEEDED")
    else:
        update_expression = "SET #s = :s, error_message = :e, updated_at = :u"
        expression_values = {
            ":s": "FAILED",
            ":e": error_msg,
            ":u": now_iso(),
        }
        if finalized_billing is not None:
            update_expression += ", billing = :b"
            expression_values[":b"] = finalized_billing
        table.update_item(
            Key={"job_id": job_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues=expression_values,
        )
        print(f"Job {job_id} FAILED: {error_msg}")


def resolve_queue_url(queue_name="aipdf-job-queue-dev"):
    """Discover the actual SQS queue URL from LocalStack (handles URL format differences)."""
    try:
        resp = sqs_client.get_queue_url(QueueName=queue_name)
        url = resp["QueueUrl"]
        # Replace localhost or special localstack domains with our configured host
        for target in ["localhost.localstack.cloud", "localhost", "127.0.0.1"]:
            url = url.replace(target, localstack_host)
        return url
    except Exception:
        return JOB_QUEUE_URL


def poll_loop():
    # Resolve actual queue URL (LocalStack v3 uses different URL formats)
    actual_queue_url = None
    while not actual_queue_url:
        try:
            actual_queue_url = resolve_queue_url()
            print(f"Job dispatcher starting — polling {actual_queue_url} every {POLL_INTERVAL}s")
        except Exception as e:
            print(f"Waiting for SQS queue... ({e})")
            time.sleep(POLL_INTERVAL)

    while True:
        try:
            resp = sqs_client.receive_message(
                QueueUrl=actual_queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10
            )

            messages = resp.get("Messages", [])
            for msg in messages:
                job_id = msg["Body"]
                print(f"Received job: {job_id}")

                try:
                    process_job(job_id)
                finally:
                    sqs_client.delete_message(
                        QueueUrl=actual_queue_url,
                        ReceiptHandle=msg["ReceiptHandle"]
                    )

        except Exception as e:
            print(f"Poll error: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    poll_loop()
