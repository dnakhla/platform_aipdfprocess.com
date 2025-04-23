variable "project_name" {
  description = "The name of the project (e.g., 'aipdf'). Used to prefix resource names."
  type        = string
}

variable "environment" {
  description = "The deployment environment (e.g., 'dev', 'prod'). Used in resource names."
  type        = string
}

variable "tags" {
  description = "A map of tags to apply to the resources."
  type        = map(string)
  default     = {}
}

variable "domain_name" {
  description = "The custom domain name for the website, e.g., app.example.com. Leave empty if not using a custom domain."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "The Route 53 Hosted Zone ID if using a custom domain."
  type        = string
  default     = ""
}

variable "cloudfront_price_class" {
  description = "CloudFront price class (PriceClass_All, PriceClass_200, PriceClass_100)."
  type        = string
  default     = "PriceClass_100"

  validation {
    condition     = contains(["PriceClass_All", "PriceClass_200", "PriceClass_100"], var.cloudfront_price_class)
    error_message = "CloudFront price class must be one of: PriceClass_All, PriceClass_200, PriceClass_100."
  }
}

variable "index_document" {
  description = "Default index document for the website."
  type        = string
  default     = "index.html"
}

variable "error_document" {
  description = "Default error document for the website."
  type        = string
  default     = "error.html"
}

# Placeholder for other Frontend module variables
