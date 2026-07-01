# Payments API (v1)

Base URL:
`http://localhost:8000/api/v1/payments/`

## PayMongo MVP Scope

PayMongo is used as Sarig's external payment gateway for customer checkout. Sarig still owns order creation, merchant approval, inventory deduction, rider dispatch, refunds, and internal audit records.

Current MVP payment methods:
- `COD`: order is created immediately and merchant is notified immediately.
- `PAYMONGO`: order is created with a pending payment transaction, then merchant notification waits for PayMongo webhook confirmation.

Payment transaction statuses:
- `PENDING`
- `AUTHORIZED`
- `SUCCESS`
- `FAILED`
- `EXPIRED`
- `REFUNDED`

## Environment

Use PayMongo test mode for local and development testing.

```env
PAYMONGO_SECRET_KEY=sk_test_...
PAYMONGO_WEBHOOK_SECRET=whsk_...
PAYMONGO_SUCCESS_URL=http://localhost:3000/orders/payment/success
PAYMONGO_CANCEL_URL=http://localhost:3000/orders/payment/cancelled
PAYMONGO_USE_MOCK=False
```

Rules:
- Use `sk_test_...` for development.
- Do not use `sk_live_...` until production.
- Keep secret keys in `.env`; do not commit them.
- `PAYMONGO_USE_MOCK=True` skips PayMongo and returns a fake checkout URL.
- `PAYMONGO_USE_MOCK=False` calls PayMongo's test API when using `sk_test_...`.

## Checkout Flow

PayMongo checkout is created from:

`POST /api/v1/orders/checkout/`

Required request field:

```json
{
  "payment_method": "PAYMONGO"
}
```

Successful response:

```json
{
  "status": "pending",
  "checkout_url": "https://checkout.paymongo.com/...",
  "order": {}
}
```

Backend behavior:
- Creates the Sarig `Order`.
- Creates a `PaymentTransaction` with `payment_method=PAYMONGO` and `status=PENDING`.
- Creates a PayMongo checkout session.
- Stores the PayMongo checkout session ID in `external_transaction_id`.
- Stores provider metadata in `provider_raw_response`.
- Returns `checkout_url` to web/mobile.

## Webhook Endpoint

Endpoint:

`POST /api/v1/payments/webhooks/paymongo/`

Local development requires a public HTTPS tunnel because PayMongo cannot call `127.0.0.1`.

Example ngrok endpoint:

```text
https://your-ngrok-domain.ngrok-free.dev/api/v1/payments/webhooks/paymongo/
```

When using ngrok, add the ngrok host to `.env`:

```env
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,your-ngrok-domain.ngrok-free.dev
```

PayMongo webhook events to enable:
- `checkout_session.payment.paid`
- `payment.paid`
- `payment.failed`
- `payment.refunded`
- `payment.refund.updated`

Current backend handling:
- `checkout_session.payment.paid` or `payment.paid`:
  - marks `PaymentTransaction.status=SUCCESS`
  - stores `payment_id` when present
  - deducts inventory
  - notifies merchant
  - keeps order `PENDING` for merchant approval unless store auto-accept is enabled
- `payment.failed` or `checkout_session.payment.failed`:
  - marks `PaymentTransaction.status=FAILED`
  - cancels the order
- `checkout_session.expired` or `checkout_session.payment.expired`:
  - marks `PaymentTransaction.status=EXPIRED`
  - cancels the order

Webhook security:
- Uses `PAYMONGO_WEBHOOK_SECRET` to verify `Paymongo-Signature`.
- Saves raw webhook payload in `provider_raw_response`.
- Ignores duplicate successful/refunded webhooks safely.
- Resolves transactions by checkout session ID, payment ID, or order metadata.

## Refund Behavior

Refund calls are supported through `PayMongoService.create_refund`.

Current refund triggers:
- merchant rejects a paid PayMongo order
- stale paid PayMongo order is auto-cancelled
- paid webhook succeeds but inventory deduction fails

When refund succeeds, the payment transaction becomes:

```text
REFUNDED
```

## Local Verification

Run migrations:

```bash
python manage.py migrate
```

Run focused tests:

```bash
python manage.py test apps.payments tests.orders.test_checkout tests.orders.test_auto_cancel_refund tests.orders.test_merchant_actions --keepdb
```

Verified development behavior:
- test PayMongo API creates a real checkout session when `PAYMONGO_USE_MOCK=False`
- ngrok webhook URL reaches local Django
- signed webhook updates `PaymentTransaction` and `Order` status correctly
