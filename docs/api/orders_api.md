# Orders API (v1)

Base URL:
`http://localhost:8000/api/v1/orders/`

---

## CHECKOUT

### Get Final Quote
`POST /checkout/quote/`
**Customer authentication required**

Uses the same request body and server-side calculation as checkout, excluding prescription files. It validates current store availability, products, inventory, modifiers, delivery range, and promo codes without creating an order.

```json
{
  "subtotal": "200.00",
  "delivery_fee": "64.00",
  "service_fee": "10.00",
  "discount_amount": "0.00",
  "total_amount": "274.00",
  "distance_km": "2.40",
  "estimated_minutes": 20
}
```

Checkout always recalculates these values before creating the order. A quote does not reserve inventory or guarantee a stale price.

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
  "delivery_method": "DELIVERY | PICKUP",
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

Do not send `subtotal`, `delivery_fee`, `system_fee`, or `total_amount` from frontend logic. Checkout calculates these server-side. For `DELIVERY`, checkout uses the shared location service route estimate and delivery fee formula. For `PICKUP`, delivery fee is `0.00`.

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

For `PAYMONGO`, the merchant should not treat the order as paid from the frontend redirect alone. The backend waits for PayMongo webhook confirmation before marking the payment transaction as `SUCCESS` and notifying the merchant.

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
- **Payment confirmation**: PayMongo orders remain payment-pending until `/api/v1/payments/webhooks/paymongo/` confirms paid, failed, or expired state.
- **Delivery fee**: Delivery checkout uses `apps.locations` for road-distance estimates with Haversine fallback and rejects addresses outside `DELIVERY_MAX_DISTANCE_KM`.
