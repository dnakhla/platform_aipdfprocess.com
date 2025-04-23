package test

import (
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
)

func TestTerraformBasic(t *testing.T) {
	t.Parallel() // Run tests in parallel if multiple test functions are added later

	// Define the path to the Terraform code
	terraformOptions := &terraform.Options{
		// The path to where our Terraform code is located
		TerraformDir: "../terraform",

		// Variables to pass to our Terraform code using -var options
		// Vars: map[string]interface{}{
		//	"resource_prefix": "test-prefix", // Optional: override default prefix for testing
		// },

		// Environment variables to set when running Terraform
		// EnvVars: map[string]string{
		//	"AWS_DEFAULT_REGION": "us-west-2", // Optional: override default region for testing
		// },
	}

	// At the end of the test, run `terraform destroy` to clean up any resources that were created
	// defer terraform.Destroy(t, terraformOptions) // Not needed for validate/plan tests

	// Run `terraform init` and `terraform validate`. Fail the test if there are any errors.
	_, errInitValidate := terraform.InitAndValidateE(t, terraformOptions)
	assert.NoError(t, errInitValidate, "Terraform init or validate failed")
	if errInitValidate != nil {
		t.Errorf("Terraform init or validate failed: %v", errInitValidate)
		return // Stop further execution if init/validate fails
	}
	t.Log("Terraform init and validate successful")


	// Run `terraform plan`. Fail the test if there are any errors.
	_, errPlan := terraform.PlanE(t, terraformOptions)
	assert.NoError(t, errPlan, "Terraform plan failed")
	if errPlan != nil {
		t.Errorf("Terraform plan failed: %v", errPlan)
	} else {
		t.Log("Terraform plan successful")
	}

	// Note: We are not running terraform apply or checking specific resources in this basic test.
	// More advanced tests could run `terraform apply`, get outputs, and make assertions
	// about the created infrastructure, followed by `terraform destroy`.
}
