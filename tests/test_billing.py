import copy
import importlib.util
import json
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_module(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class FakeTable:
    def __init__(self, key_name: str):
        self.key_name = key_name
        self.items = {}

    def get_item(self, Key):
        item = self.items.get(Key[self.key_name])
        return {"Item": copy.deepcopy(item)} if item is not None else {}

    def put_item(self, Item):
        self.items[Item[self.key_name]] = copy.deepcopy(Item)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def update_item(self, Key, UpdateExpression=None, ExpressionAttributeValues=None, ExpressionAttributeNames=None):
        item = copy.deepcopy(self.items.get(Key[self.key_name]) or {self.key_name: Key[self.key_name]})
        if UpdateExpression and UpdateExpression.startswith("SET "):
            updates = UpdateExpression[4:].split(", ")
            names = ExpressionAttributeNames or {}
            for update in updates:
                attr_name, value_ref = update.split(" = ")
                attr_name = names.get(attr_name, attr_name)
                item[attr_name] = copy.deepcopy(ExpressionAttributeValues[value_ref])
        self.items[Key[self.key_name]] = item
        return {"Attributes": copy.deepcopy(item)}


class FakeDynamo:
    def __init__(self):
        self.tables = {
            "aipdf-users-dev": FakeTable("user_id"),
            "aipdf-jobs-dev": FakeTable("job_id"),
        }

    def Table(self, name):
        return self.tables[name]


class FakeSQS:
    def __init__(self):
        self.messages = []

    def send_message(self, QueueUrl, MessageBody):
        self.messages.append({"QueueUrl": QueueUrl, "MessageBody": MessageBody})
        return {"MessageId": f"msg_{len(self.messages)}"}


class FakeStripe:
    api_key = None
    last_customer_kwargs = None
    last_session_kwargs = None

    class Customer:
        @staticmethod
        def create(**kwargs):
            FakeStripe.last_customer_kwargs = kwargs
            return {"id": "cus_test_123"}

    class checkout:
        class Session:
            @staticmethod
            def create(**kwargs):
                FakeStripe.last_session_kwargs = kwargs
                return {"id": "cs_test_123", "url": "https://checkout.stripe.test/cs_test_123"}

    class Webhook:
        @staticmethod
        def construct_event(payload, signature, secret):
            return json.loads(payload.decode("utf-8"))


@pytest.fixture
def api_context(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")

    module = load_module(f"api_router_test_{uuid.uuid4().hex}", "services/api-router/app.py")
    fake_dynamo = FakeDynamo()
    fake_sqs = FakeSQS()
    module.dynamodb = fake_dynamo
    module.sqs_client = fake_sqs
    module.RESOLVED_QUEUE_URL = "http://queue.test/aipdf"
    module.stripe = FakeStripe
    module.STRIPE_SECRET_KEY = "sk_test_dummy"
    module.STRIPE_WEBHOOK_SECRET = "whsec_test"
    module.STRIPE_SUCCESS_URL = "https://app.test/success"
    module.STRIPE_CANCEL_URL = "https://app.test/cancel"

    client = TestClient(module.app)
    yield module, fake_dynamo, fake_sqs, client
    module.app.dependency_overrides.clear()


@pytest.fixture
def dispatcher_context(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")

    module = load_module(f"job_dispatcher_test_{uuid.uuid4().hex}", "services/job-dispatcher/app.py")
    fake_dynamo = FakeDynamo()
    module.dynamodb = fake_dynamo
    yield module, fake_dynamo


def override_auth(module, user_id="user_123", auth_type="api_key", api_key_id="ak_test"):
    module.app.dependency_overrides[module.get_current_user] = lambda: {
        "user_id": user_id,
        "auth_type": auth_type,
        "api_key_id": api_key_id,
    }


def test_billing_summary_defaults(api_context):
    module, fake_dynamo, _, client = api_context
    override_auth(module)

    response = client.get("/v1/billing/summary")
    assert response.status_code == 200

    payload = response.json()
    assert payload["billing"]["creditBalance"] == 0
    assert payload["billing"]["freeTier"]["remaining"] == 5
    assert payload["billing"]["currentApiKey"]["completedPdfs"] == 0
    assert payload["billing"]["ledger"] == {"entryCount": 0, "lastEntryAt": None, "recent": []}


def test_process_reserves_mixed_free_and_paid_capacity(api_context):
    module, fake_dynamo, fake_sqs, client = api_context
    override_auth(module)
    month = module.month_key()
    fake_dynamo.Table("aipdf-users-dev").put_item(
        Item={
            "user_id": "user_123",
            "credit_balance": 3,
            "monthly_usage": {
                "month": month,
                "free_reserved": 0,
                "free_completed": 4,
                "paid_completed": 0,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "total_pdfs_completed": 4,
                "last_job_at": None,
            },
        }
    )

    response = client.post(
        "/v1/process",
        json={
            "fileKeys": ["input/a.pdf", "input/b.pdf"],
            "operations": [{"type": "extract_text", "params": {}}],
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["billing"]["reserved"] == {"pdfCount": 2, "free": 1, "paid": 1}
    assert len(fake_sqs.messages) == 1

    user_item = fake_dynamo.Table("aipdf-users-dev").items["user_123"]
    assert user_item["credit_balance"] == 2
    assert user_item["monthly_usage"]["free_reserved"] == 1
    assert user_item["billing_ledger"] == [
        {
            "entryId": f"reserve:{payload['jobId']}",
            "type": "RESERVE",
            "createdAt": user_item["billing_updated_at"],
            "jobId": payload["jobId"],
            "month": month,
            "pdfCount": 2,
            "freeReserved": 1,
            "paidReserved": 1,
            "creditDelta": -1,
            "creditBalanceAfter": 2,
            "freeReservedDelta": 1,
            "freeReservedAfter": 1,
            "freeRemainingAfter": 0,
            "authType": "api_key",
            "apiKeyId": "ak_test",
            "reason": "job_reserved",
        }
    ]

    job_id = payload["jobId"]
    job_item = fake_dynamo.Table("aipdf-jobs-dev").items[job_id]
    assert job_item["billing"]["freeReserved"] == 1
    assert job_item["billing"]["paidReserved"] == 1
    assert job_item["billing"]["apiKeyId"] == "ak_test"


def test_checkout_and_webhook_topup_are_idempotent(api_context):
    module, fake_dynamo, _, client = api_context
    override_auth(module, auth_type="jwt_mock", api_key_id=None)

    checkout = client.post(
        "/v1/billing/checkout",
        json={"pdfCredits": 4, "successUrl": "https://app.test/done", "cancelUrl": "https://app.test/cancel"},
    )
    assert checkout.status_code == 200
    assert checkout.json()["amountTotalCents"] == 400
    assert FakeStripe.last_session_kwargs["metadata"]["pdf_credits"] == "4"

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "customer": "cus_test_123",
                "payment_status": "paid",
                "metadata": {"user_id": "user_123", "pdf_credits": "4"},
            }
        },
    }

    first = client.post("/v1/billing/webhook", json=event, headers={"stripe-signature": "sig"})
    second = client.post("/v1/billing/webhook", json=event, headers={"stripe-signature": "sig"})

    assert first.status_code == 200
    assert first.json()["creditsApplied"] is True
    assert second.status_code == 200
    assert second.json()["creditsApplied"] is False

    user_item = fake_dynamo.Table("aipdf-users-dev").items["user_123"]
    assert user_item["credit_balance"] == 4
    assert user_item["processed_checkout_session_ids"] == {"cs_test_123"}
    assert user_item["billing_ledger"] == [
        {
            "entryId": "topup:cs_test_123",
            "type": "TOPUP",
            "createdAt": user_item["billing_updated_at"],
            "checkoutSessionId": "cs_test_123",
            "customerId": "cus_test_123",
            "pdfCredits": 4,
            "creditDelta": 4,
            "creditBalanceAfter": 4,
            "reason": "stripe_checkout_completed",
        }
    ]


def test_process_release_restores_credits_and_writes_ledger(api_context):
    module, fake_dynamo, _, client = api_context
    override_auth(module)
    month = module.month_key()

    class FailingSQS:
        def send_message(self, QueueUrl, MessageBody):
            raise RuntimeError("queue offline")

    module.sqs_client = FailingSQS()
    fake_dynamo.Table("aipdf-users-dev").put_item(
        Item={
            "user_id": "user_123",
            "credit_balance": 1,
            "monthly_usage": {
                "month": month,
                "free_reserved": 0,
                "free_completed": 5,
                "paid_completed": 0,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "total_pdfs_completed": 5,
                "last_job_at": None,
            },
        }
    )

    response = client.post(
        "/v1/process",
        json={
            "fileKey": "input/a.pdf",
            "operations": [{"type": "extract_text", "params": {}}],
        },
    )

    assert response.status_code == 500

    user_item = fake_dynamo.Table("aipdf-users-dev").items["user_123"]
    assert user_item["credit_balance"] == 1
    assert user_item["monthly_usage"]["free_reserved"] == 0
    assert [entry["type"] for entry in user_item["billing_ledger"]] == ["RESERVE", "RELEASE"]
    reserve_entry, release_entry = user_item["billing_ledger"]
    assert reserve_entry["creditDelta"] == -1
    assert release_entry["creditDelta"] == 1
    assert release_entry["creditBalanceAfter"] == 1
    assert release_entry["freeReservedAfter"] == 0
    assert release_entry["reason"] == "job_enqueue_failed"


def test_checkout_completed_waits_for_paid_status(api_context):
    module, fake_dynamo, _, client = api_context
    override_auth(module, auth_type="jwt_mock", api_key_id=None)

    checkout = client.post(
        "/v1/billing/checkout",
        json={"pdfCredits": 3, "successUrl": "https://app.test/done", "cancelUrl": "https://app.test/cancel"},
    )
    assert checkout.status_code == 200

    pending_event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_pending_123",
                "customer": "cus_test_123",
                "payment_status": "unpaid",
                "metadata": {"user_id": "user_123", "pdf_credits": "3"},
            }
        },
    }
    paid_event = {
        "type": "checkout.session.async_payment_succeeded",
        "data": {
            "object": {
                "id": "cs_pending_123",
                "customer": "cus_test_123",
                "payment_status": "paid",
                "metadata": {"user_id": "user_123", "pdf_credits": "3"},
            }
        },
    }

    pending = client.post("/v1/billing/webhook", json=pending_event, headers={"stripe-signature": "sig"})
    assert pending.status_code == 200
    assert pending.json()["creditsApplied"] is False
    assert pending.json()["reason"] == "payment_not_settled"

    user_item = fake_dynamo.Table("aipdf-users-dev").items.get("user_123")
    assert user_item is not None
    assert user_item.get("credit_balance", 0) == 0

    paid = client.post("/v1/billing/webhook", json=paid_event, headers={"stripe-signature": "sig"})
    assert paid.status_code == 200
    assert paid.json()["creditsApplied"] is True

    user_item = fake_dynamo.Table("aipdf-users-dev").items["user_123"]
    assert user_item["credit_balance"] == 3
    assert user_item["processed_checkout_session_ids"] == {"cs_pending_123"}


def test_dispatcher_finalize_billing_success_and_refund_are_idempotent(dispatcher_context):
    module, fake_dynamo = dispatcher_context
    month = module.month_key()

    fake_dynamo.Table("aipdf-users-dev").put_item(
        Item={
            "user_id": "user_123",
            "credit_balance": 1,
            "monthly_usage": {
                "month": month,
                "free_reserved": 1,
                "free_completed": 0,
                "paid_completed": 0,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "total_pdfs_completed": 0,
                "last_job_at": None,
            },
        }
    )

    success_job = {
        "job_id": "job_success",
        "user_id": "user_123",
        "billing": {
            "month": month,
            "pdfCount": 2,
            "freeReserved": 1,
            "paidReserved": 1,
            "apiKeyId": "ak_test",
        },
    }

    finalized = module.finalize_billing(success_job, success=True)
    finalized_again = module.finalize_billing(success_job, success=True)

    assert finalized["finalState"] == "SUCCEEDED"
    assert finalized_again["finalState"] == "SUCCEEDED"

    user_item = fake_dynamo.Table("aipdf-users-dev").items["user_123"]
    assert user_item["credit_balance"] == 1
    assert user_item["monthly_usage"]["free_reserved"] == 0
    assert user_item["monthly_usage"]["free_completed"] == 1
    assert user_item["monthly_usage"]["paid_completed"] == 1
    assert user_item["monthly_usage"]["completed_jobs"] == 1
    assert user_item["monthly_usage"]["total_pdfs_completed"] == 2
    assert user_item["api_key_usage"]["ak_test"]["completed_pdfs"] == 2
    assert user_item["billing_ledger"] == [
        {
            "entryId": "finalize:job_success:success",
            "type": "FINALIZE_SUCCESS",
            "createdAt": user_item["billing_updated_at"],
            "jobId": "job_success",
            "month": month,
            "pdfCount": 2,
            "freeReservedReleased": 1,
            "paidReservedReleased": 1,
            "creditDelta": 0,
            "creditBalanceAfter": 1,
            "freeReservedDelta": -1,
            "freeReservedAfter": 0,
            "freeCompletedDelta": 1,
            "freeCompletedAfter": 1,
            "paidCompletedDelta": 1,
            "paidCompletedAfter": 1,
            "completedJobsDelta": 1,
            "failedJobsDelta": 0,
            "totalPdfsCompletedDelta": 2,
            "apiKeyId": "ak_test",
            "reason": "job_succeeded",
        }
    ]

    user_item["monthly_usage"]["free_reserved"] = 1
    fake_dynamo.Table("aipdf-users-dev").put_item(Item=user_item)
    refund_job = {
        "job_id": "job_refund",
        "user_id": "user_123",
        "billing": {
            "month": month,
            "pdfCount": 1,
            "freeReserved": 1,
            "paidReserved": 1,
            "apiKeyId": "ak_test",
        },
    }

    refunded = module.finalize_billing(refund_job, success=False)
    refunded_again = module.finalize_billing(refund_job, success=False)

    assert refunded["finalState"] == "REFUNDED"
    assert refunded_again["finalState"] == "REFUNDED"

    user_item = fake_dynamo.Table("aipdf-users-dev").items["user_123"]
    assert user_item["credit_balance"] == 2
    assert user_item["monthly_usage"]["free_reserved"] == 0
    assert user_item["monthly_usage"]["failed_jobs"] == 1
    assert user_item["api_key_usage"]["ak_test"]["failed_jobs"] == 1
    assert [entry["type"] for entry in user_item["billing_ledger"]] == ["FINALIZE_SUCCESS", "FINALIZE_REFUND"]
    assert user_item["billing_ledger"][-1] == {
        "entryId": "finalize:job_refund:refund",
        "type": "FINALIZE_REFUND",
        "createdAt": user_item["billing_updated_at"],
        "jobId": "job_refund",
        "month": month,
        "pdfCount": 1,
        "freeReservedReleased": 1,
        "paidReservedReleased": 1,
        "creditDelta": 1,
        "creditBalanceAfter": 2,
        "freeReservedDelta": -1,
        "freeReservedAfter": 0,
        "freeCompletedDelta": 0,
        "freeCompletedAfter": 1,
        "paidCompletedDelta": 0,
        "paidCompletedAfter": 1,
        "completedJobsDelta": 0,
        "failedJobsDelta": 1,
        "totalPdfsCompletedDelta": 0,
        "apiKeyId": "ak_test",
        "reason": "job_failed",
    }
