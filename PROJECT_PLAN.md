# AI PDF Processing Platform - Implementation Plan (v2.0)

**Date:** 2026-03-17  
**Status:** Core Backend Engine + Auth Verified (LocalStack)  
**Architecture:** Python 3.12, SQS-backed Async Processing, Containerized Capability-Based Workers

## 1. Foundation Architecture (COMPLETE)

### Infrastructure as Code (Terraform)
- **Modularized Structure:** `/infra/terraform`
- **S3 Storage:** Input, Output, and Artifact buckets with lifecycle rules.
- **DynamoDB:** `jobs` table for state tracking, `users` table for auth/API keys.
- **Messaging:** SQS Job Queue + Dead Letter Queue (DLQ).
- **Compute:** 5x Lambdas (API Router, Job Dispatcher, 3 Workers).
- **ECR:** Repositories for specialized worker container images.
- **API Gateway:** HTTP API with routes for `/upload`, `/process`, `/status`, and `/download`.

### Core Services (COMPLETE)

#### 1. API Router (`services/api-router`)
- **Runtime:** Python 3.12 (FastAPI + Mangum)
- **Role:** Entry point for all client requests.
- **Features:** S3 presigned URL generation, job creation in DynamoDB, SQS message dispatch, status polling, and download link generation.
- **Auth:** Cognito JWT + API Key flow implemented and verified.

#### 2. Job Dispatcher (`services/job-dispatcher`)
- **Runtime:** Python 3.12
- **Role:** Async orchestrator.
- **Features:** Triggered by SQS, fetches job state, sequences operations, invokes specialized workers, and updates job status.

#### 3. Worker: Structural (`services/worker-structural`)
- **Runtime:** Python 3.12 (Container)
- **Engine:** PyMuPDF
- **Capabilities:** Split, Merge, Rotate, Remove Blank Pages, Delete Pages.

#### 4. Worker: Extract (`services/worker-extract`)
- **Runtime:** Python 3.12 (Container)
- **Engine:** PyMuPDF + Tesseract OCR
- **Capabilities:** Extract Text (Native + OCR), Metadata Extraction, ZIP image extraction.

#### 5. Worker: Optimize (`services/worker-optimize`)
- **Runtime:** Python 3.12 (Container)
- **Engine:** pikepdf
- **Capabilities:** Compress, Repair, Linearize, Sanitize.

## 2. Phase 2: AI & Advanced Orchestration (IN PROGRESS)

### AI Planner (`services/ai-planner`)
- **Runtime:** Python 3.12
- **Role:** Translates natural language prompts into deterministic operation chains.
- **Status:** Integrated into API Router (`/v1/process/nl`).

### Next Steps for AI Pipeline:
- [ ] Add advanced layout analysis (Docling/Fargate) for complex table extraction.
- [ ] Implement summarization and redaction tools via LLM.

## 3. Phase 3: Frontend & Billing (IN PROGRESS)

### Frontend Portal (`/portal`)
- **Tech:** Vanilla JS + Tailwind (S3 + CloudFront hosting).
- **Features:** Drag-and-drop upload, operation picker, real-time progress bar, download gallery.
- **Redesign:** Academic research-lab aesthetic (Job #2546 in progress).

### Authentication & API Keys (COMPLETE)
- [x] Implement Amazon Cognito User Pool emulation in LocalStack.
- [x] Implement API key issuance and usage metering in DynamoDB.

### Stripe Integration
- [x] `POST /v1/billing/checkout` -> Stripe Checkout.
- [x] Webhook handler for credit top-ups.

## 4. Development & CI/CD (COMPLETE)

### Local Development
- **Docker Compose:** Stands up Localstack and API services for end-to-end testing.
- **Tools:** `uv` for dependency management, `pytest` for unit/integration tests.
- **Verification:** 100% test pass rate for workers and auth flow.

### GitHub Actions Pipeline
- [ ] `ci.yaml`: Linting, testing, and security scanning.
- [ ] `deploy.yaml`: Build/Push ECR images, Zip Lambdas, and Terraform Apply.

---

## Technical Debt / Known Issues
- [x] `merge` operation in `worker-structural` needs multi-file input handling logic.
- [x] `extract_images` in `worker-extract` needs ZIP packaging for output.
- [x] `compress` in `worker-optimize` needs parameter tuning for quality/size tradeoffs.
