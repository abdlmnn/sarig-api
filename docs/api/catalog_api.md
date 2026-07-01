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
- **Product Types**: Products support `product_type`: `food`, `medicine`, `grocery`, or `general`.
- **Availability**: Every product uses `is_available` as the merchant-facing on/off switch.
- **Inventory**: Products return `inventory_mode`, `track_inventory`, `stock_quantity`, and a dynamic `in_stock` property.
- **MVP Inventory Rule**: Use `inventory_mode=none` for food, medicine, and groceries unless the merchant explicitly wants stock tracking. Use `inventory_mode=simple_stock` only when `stock_quantity` should be enforced.
- **Medicine**: Medicine products can set `requires_prescription`, `generic_name`, `brand_name`, `dosage`, and `medicine_form`. Non-medicine products cannot require prescription.
- **Groceries**: Grocery products should use `unit_type` such as `piece`, `pack`, `bottle`, `can`, `kilo`, `gram`, `liter`, `sachet`, `box`, or `dozen`.
- **Modifiers**: Products include `modifier_groups` containing customization options (e.g., "Size", "Add-ons") with their `items` and `extra_price`.

### MVP Product Examples

Food:
```json
{
  "product_type": "food",
  "name": "Chicken Pastil",
  "price": "65.00",
  "is_available": true,
  "inventory_mode": "none",
  "stock_quantity": null
}
```

Medicine:
```json
{
  "product_type": "medicine",
  "name": "Amoxicillin",
  "dosage": "500mg",
  "medicine_form": "Capsule",
  "price": "15.00",
  "requires_prescription": true,
  "is_available": true,
  "inventory_mode": "none",
  "stock_quantity": null
}
```

Grocery:
```json
{
  "product_type": "grocery",
  "name": "Rice",
  "price": "55.00",
  "unit_type": "kilo",
  "is_available": true,
  "inventory_mode": "none",
  "stock_quantity": null
}
```
