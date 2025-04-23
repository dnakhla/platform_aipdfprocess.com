## Project Structure

- `terraform/`: Contains the Terraform configuration for the AWS Lambda function and related resources.
  - `variables.tf`: Defines input variables (e.g., `resource_prefix`, `aws_region`).
  - `providers.tf`: Configures the AWS provider.
  - `iam.tf`: Defines the Lambda execution IAM role.
  - `lambda.tf`: Defines the Lambda function.
  - `outputs.tf`: Defines outputs (e.g., Lambda ARN).
  - `lambda_function.zip`: Placeholder for the Lambda function deployment package.
- `tests/`: Contains tests for the Terraform configuration using Go and Terratest.
  - `terraform_test.go`: Basic tests to validate the Terraform setup.

## Usage

### Prerequisites

- Terraform installed
- AWS credentials configured
- Go installed (for running tests)

### Initialization

Navigate to the `terraform` directory and initialize Terraform:

```bash
cd terraform
terraform init
```

### Planning

You can generate an execution plan:

```bash
# Optionally create a terraform.tfvars file or use -var flag
terraform plan
```

### Applying (Optional - For actual deployment)

```bash
terraform apply
```

### Testing

Navigate to the `tests` directory and run the tests:

```bash
cd tests
go mod tidy # Run once to download dependencies
go test -v
```
=======
# AI PDF Processing Platform

A serverless, AWS-based platform for PDF manipulation with AI orchestration. 

## Overview

This platform provides a comprehensive set of PDF processing tools implemented as AWS Lambda functions, orchestrated by an AI system that chains operations to achieve complex document processing workflows. The system is designed to be highly scalable, cost-effective, and easy to extend.

## Features

### Core PDF Tools
- 📄 **Format Conversion**: PDF ↔ PNG/JPEG, PDF ↔ PDF/A
- 🔍 **Text Extraction**: Extract raw text with OCR fallback
- 🖼️ **Image Extraction**: Extract images per page or entire document
- 🔄 **Page Manipulation**: Resize, rotate, split, merge
- 🗑️ **Clean-up**: Remove blank pages, compress, optimize
- 🔐 **Security**: Add/remove watermarks, redact sensitive text
- 📝 **Content Analysis**: Summarize or describe page content using LLM

### Coming Soon
- 🌐 **Translation**: Translate text to different languages
- 🏷️ **Classification**: Categorize pages by content type
- 📊 **Comparison**: Compare two PDFs for differences
- ✏️ **Annotation**: Add notes, highlights, comments

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│ Client      │────►│ API Gateway  │────►│ Orchestrator  │
└─────────────┘     └──────────────┘     └───────┬───────┘
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────┐
│                    LLM Decision Making                    │
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                     PDF Tool Lambdas                     │
├─────────┬─────────┬──────────┬────────────┬─────────────┤
│ Resize  │ Extract │ Compress │ Summarize  │ Convert     │
└─────────┴─────────┴──────────┴────────────┴─────────────┘
                            │
      ┌───────────────────────────────────────────┐
      │                                           │
      ▼                                           ▼
┌──────────┐                             ┌───────────────┐
│ Input S3 │                             │ Output S3     │
└──────────┘                             └───────────────┘
```

### Key Components
- **Storage**: S3 buckets for input, intermediate artifacts, and final outputs
- **Compute**: AWS Lambda functions (one per tool or single multi-action Lambda)
- **API Layer**: API Gateway to expose services
- **Orchestrator**: Lambda/Fargate service with LLM integration
- **State Management**: DynamoDB for job tracking and state persistence
- **Security**: IAM roles, VPC endpoints, KMS encryption

## Technical Stack
- **Infrastructure**: AWS CDK/CloudFormation
- **Runtime**: Node.js/Python/Java (TBD)
- **CI/CD**: AWS CodePipeline, CodeBuild
- **Monitoring**: CloudWatch, X-Ray
- **LLM Integration**: OpenAI/Azure OpenAI API

## Getting Started

### Prerequisites
- AWS Account
- Node.js and npm (latest LTS)
- AWS CLI configured
- (Optional) Docker for local testing

### Installation
```bash
# Clone repository
git clone https://github.com/yourusername/aipdfprocessing.com.git
cd aipdfprocessing.com

# Install dependencies
npm install

# Deploy to AWS (development)
npm run deploy:dev
```

## Development Workflow

1. Each PDF tool is developed as a separate Lambda function or action
2. Local testing with AWS SAM or LocalStack
3. CI/CD pipeline automatically deploys changes to development environment
4. Integration tests run against sandboxed AWS environment
5. Manual promotion to staging/production

## Roadmap

1. ⏳ Project kickoff & IaC baseline
2. ⏳ Initial tool Lambdas: extract-text, compress, rotate
3. ⏳ API Gateway & orchestrator prototype
4. ⏳ LLM integration for guided workflows
5. ⏳ Expand tool set with OCR, summarize, translate
6. ⏳ Security hardening, cost-optimization, monitoring
7. ⏳ Production rollout

## License

[MIT](LICENSE)
