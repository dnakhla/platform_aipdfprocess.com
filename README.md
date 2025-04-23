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
