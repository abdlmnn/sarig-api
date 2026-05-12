# Payments API (v1)

Base URL:
`http://localhost:8000/api/v1/payments/`

---

## WEBHOOKS

### PayMongo Webhook
`POST /webhooks/paymongo/`
**Public Access** (Verify signature in production)

**Functionality**:
- Listens for `payment.paid` or `checkout_session.payment.paid`.
- Finds the `PaymentTransaction` via `external_transaction_id`.
- Updates `Order` status to `ACCEPTED`.
- Triggers **Real-Time WebSocket** alert to the Merchant.

---

## NOTES
- **Audit Log**: Every webhook request is saved in `provider_raw_response` for debugging.
- **Methods**: `COD`, `STRIPE`, `PAYMONGO`, `WALLET`.
- **Transaction Statuses**: `PENDING`, `AUTHORIZED`, `SUCCESS`, `FAILED`, `REFUNDED`.
