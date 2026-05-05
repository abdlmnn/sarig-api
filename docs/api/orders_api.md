# Orders API (v1)

Base URL:
`http://localhost:8000/api/v1/orders/`

---

## CHECKOUT

### Process Checkout
`POST /checkout/`
**Auth required**

**Request Body**:
```json
{
  "store_id": "UUID",
  "address_text": "string",
  "latitude": 0.0,
  "longitude": 0.0,
  "subtotal": 0.0,
  "delivery_fee": 0.0,
  "system_fee": 0.0,
  "total_amount": 0.0,
  "payment_method": "COD | PAYMONGO",
  "items": [
    {
      "product_id": "UUID",
      "quantity": 1,
      "special_instructions": "string"
    }
  ]
}
```

**Response (COD)**:
```json
{
  "status": "success",
  "message": "Order placed via COD.",
  "order": { ... }
}
```

**Response (PAYMONGO)**:
```json
{
  "status": "pending",
  "checkout_url": "https://...",
  "order": { ... }
}
```

---

## ORDER TRACKING (Upcoming)

### List My Orders
`GET /` (planned)

### Get Order Detail
`GET /{id}/` (planned)

---

## NOTES
- **Atomicity**: Checkout is wrapped in a database lock. If payment session creation fails, the order is not saved.
- **Statuses**: `PENDING`, `ACCEPTED`, `PREPARING`, `READY`, `ON_THE_WAY`, `DELIVERED`, `CANCELLED`.
