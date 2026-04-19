# AIPDF Processing Platform

A high-performance, serverless PDF processing engine built with AWS Lambda, S3, and Python 3.12.

## 🚀 Overview

AIPDF is a distributed PDF processing engine designed for scale, speed, and reliability. It decomposes complex document tasks into deterministic, asynchronous pipelines powered by specialized capability-based workers.

- **Fast & Lightweight:** API Router built on Python 3.12 + FastAPI.
- **Asynchronous by Default:** SQS-backed job dispatch with automatic retries and DLQ.
- **Specialized Workers:** Containerized workers using `PyMuPDF` and `pikepdf`.
- **AI-Powered (Phase 2):** Natural-language orchestration to plan and execute complex document cleanup tasks.

## 🏗 Architecture

### 1. Control Plane
- **API Router:** Handles auth, file uploads (presigned URLs), and job creation.
- **Job Dispatcher:** Reads the SQS queue and sequences worker calls.
- **DynamoDB:** Manages job state, user quotas, and API key permissions.

### 2. Processing Layer (Capability Workers)
- **Structural:** Split, merge, rotate, blank-page removal.
- **Extract:** Native text extraction, OCR (Tesseract), image extraction.
- **Optimize:** Compression, repair, linearization, sanitization.

### 3. AI Layer
- **AI Planner:** Uses LLMs to translate "clean this scanned packet" into worker chains.

## 🛠 Project Structure

```text
├── infra/
│   └── terraform/           # Infrastructure as Code (ECR, SQS, Lambda, S3, DDB, API Gateway)
├── services/
│   ├── api-router/          # FastAPI entry point
│   ├── job-dispatcher/      # Async orchestrator
│   ├── worker-structural/   # PDF structural operations (Container)
│   ├── worker-extract/      # Text & OCR extraction (Container)
│   ├── worker-optimize/     # PDF optimization (Container)
│   └── ai-planner/          # NL-to-Operation translator
├── portal/                  # Vanilla JS frontend (Static S3/CloudFront)
└── docker-compose.yml       # Local development with Localstack
```

## 🚦 Getting Started

### Prerequisites
- Python 3.12
- Docker & Docker Compose
- AWS CLI (for Localstack interaction)

### Local Development
```bash
# Build and start the engine
docker-compose up --build

# Run tests
pytest
```

## 🔒 Security
- Hashed API keys in DynamoDB.
- Cognito-managed user authentication.
- Least-privilege IAM roles for all Lambdas.
- S3 server-side encryption and lifecycle rules.

## 📜 License
MIT
