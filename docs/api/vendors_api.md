# Vendors API (v1)

Base URL:
`http://localhost:8000/api/v1/vendors/`

---

## BUSINESS VERTICALS

### List Verticals
`GET /verticals/`
- Example: "Restaurant", "Pharmacy", "Transport".

---

## STORES

### List Stores
`GET /stores/`
- **Query Params**: `city` (optional) - Filter by city.

### Create Store
`POST /stores/`
**Auth Required** (Merchant role recommended)

### Store Detail
`GET /stores/{id}/`
`PATCH /stores/{id}/`

---

## NOTES
- **IDs**: All primary keys are **UUIDv4**.
- **Images**: Stores now support an `image` field.
- **Ratings**: Initial rating defaults to `5.00`.
- **Optimization**: Coordinate fields (`latitude`, `longitude`) are indexed for future geospatial queries.
