# Billing Notes

## What ships in this pass

- `POST /v1/billing/checkout`
  Creates a Stripe Checkout session for PDF credit top-ups.
- `POST /v1/billing/webhook`
  Verifies Stripe webhook signatures and applies credits only after payment is settled
  (`checkout.session.completed` with `payment_status=paid`, or `checkout.session.async_payment_succeeded`).
- `GET /v1/billing/summary`
  Returns free-tier usage, paid credit balance, current API-key usage counters, and the recent append-only billing ledger.
- `POST /v1/process`
  Reserves free quota or paid credits before queueing a job.
- `services/job-dispatcher`
  Finalizes usage on success and refunds reserved paid credits on failure.

## Ledger events

The billing ledger is append-only and persists on the user record.

- `TOPUP`
  Stripe checkout completed and credits were added.
- `RESERVE`
  Credits and/or free-tier quota were reserved before a job was queued.
- `RELEASE`
  A reservation was released because the job could not be queued.
- `FINALIZE_SUCCESS`
  A queued job succeeded, reserved usage was consumed, and usage counters advanced.
- `FINALIZE_REFUND`
  A queued job failed, reserved paid credits were refunded, and failure counters advanced.

## Default billing model

- Free tier: `5` PDFs per month
- Paid usage: `1` credit per processed PDF
- Default price: `100` cents per PDF credit
- Stripe mode: test keys only (`sk_test_*`)

## Environment variables

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_SUCCESS_URL`
- `STRIPE_CANCEL_URL`
- `FREE_PDFS_PER_MONTH`
- `PRICE_PER_PDF_CENTS`
- `BILLING_CURRENCY`
- `ALLOW_UNVERIFIED_STRIPE_WEBHOOKS=false`

## Local webhook test

```bash
stripe listen --forward-to localhost:9010/v1/billing/webhook
```

Use the returned `whsec_...` value for `STRIPE_WEBHOOK_SECRET`.

## Example checkout request

```json
{
  "pdfCredits": 10,
  "successUrl": "https://aipdfprocessing.946nl.online/app?checkout=success",
  "cancelUrl": "https://aipdfprocessing.946nl.online/app?checkout=cancelled"
}
```
