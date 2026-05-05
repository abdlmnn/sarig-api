# Catalog API (v1)

Base URL:
`http://localhost:8000/api/v1/catalog/`

---

## CATEGORIES

### List Categories
`GET /categories/`
- **Query Params**: `store_id` (optional) - Filter by store UUID.

### Get Category Detail
`GET /categories/{id}/`

---

## PRODUCTS

### List Products
`GET /products/`
- **Query Params**: `category_id` (optional) - Filter by category UUID.

### Get Product Detail
`GET /products/{id}/`

---

## NOTES
- All IDs are **UUIDv4**.
- `is_active` and `is_available` flags are respected (hidden if false).
- Categories are sorted by the `order` field.
- **Inventory**: Products now return `track_inventory`, `stock_quantity`, and a dynamic `in_stock` property.
- **Modifiers**: Products include `modifier_groups` containing customization options (e.g., "Size", "Add-ons") with their `items` and `extra_price`.
