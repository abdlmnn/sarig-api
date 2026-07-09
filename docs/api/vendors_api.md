# Merchant API (v1)

Base URL:
`http://localhost:8000/api/v1/merchant/`

---

## BUSINESS VERTICALS

### List Verticals
`GET /business-verticals/`
- Example: "Restaurant", "Pharmacy", "Transport".

---

## STORES

### List Stores
`GET /stores/`
- **Query Params**: `city` (optional) - Filter by city.

### Create Store
`POST /stores/`
**Auth Required** (Merchant role recommended)
- Key fields: `vertical`, `name`, `branch_name`, `company_email`, `contact_number`, `delivery_time`, `latitude`, `longitude`, `street_address`, `city`, `barangay`, `province`, `postal_code`, `pinned_address`, `image`.

### Store Detail
`GET /stores/{id}/`
`PATCH /stores/{id}/`

---

## NOTES
- **IDs**: All primary keys are **UUIDv4**.
- **Images**: Stores now support an `image` field.
- **Ratings**: Initial rating defaults to `5.00`.
- **Geo**: `latitude` and `longitude` populate `location_wkt`, and `location_point` when PostGIS is enabled.
