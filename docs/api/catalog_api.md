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

## MEDICINE REFERENCES

Medicine references are FDA/source catalog records used by pharmacies to quickly create medicine products.
They are not merchant inventory and do not include merchant pricing.

### Import Medicine References

Run after migrations when the CSV is available:

```bash
python manage.py import_medicine_references data/drug_products.csv
```

Default behavior:
- imports active/non-expired rows only
- skips expired rows
- skips rows without registration number or generic name
- cleans packaging line breaks
- detects `requires_prescription` from classification values like `Prescription Drug (RX)`
- upserts by `registration_number`

To import expired rows as inactive references:

```bash
python manage.py import_medicine_references data/drug_products.csv --include-expired
```

### Search Medicine References

`GET /medicine-references/?q=amoxicillin`

Optional filter:

`GET /medicine-references/?q=amoxicillin&requires_prescription=true`

Response:

```json
[
  {
    "id": "uuid",
    "registration_number": "DRP-7649",
    "product_information": "DRP-7649_PI_01.pdf",
    "generic_name": "Amoxicillin",
    "brand_name": "",
    "dosage_strength": "250mg",
    "dosage_form": "Capsule",
    "classification": "Prescription Drug (Rx)",
    "pharmacologic_category": "Antibacterial (Penicillin)",
    "packaging": "Blister Pack of 10's (Box of 100's)",
    "manufacturer": "DIAMOND LABORATORIES INC.",
    "country_of_origin": "Philippines",
    "trader": "",
    "importer": "",
    "distributor": "",
    "expiry_date": "2027-07-02",
    "requires_prescription": true,
    "is_active": true,
    "source": "FDA Philippines"
  }
]
```

Frontend medicine product creation should support two paths:

1. Select from medicine reference:

```json
{
  "category": "category_uuid",
  "product_type": "medicine",
  "medicine_reference": "reference_uuid",
  "name": "Amoxicillin 250mg",
  "price": "15.00",
  "is_available": true,
  "inventory_mode": "none"
}
```

The backend prefills these product fields from the selected reference when not explicitly supplied:
- `generic_name`
- `brand_name`
- `dosage`
- `medicine_form`
- `requires_prescription`

2. Create custom medicine manually:

```json
{
  "category": "category_uuid",
  "product_type": "medicine",
  "name": "Custom Medicine",
  "generic_name": "Generic Name",
  "brand_name": "Brand Name",
  "dosage": "500mg",
  "medicine_form": "Tablet",
  "requires_prescription": true,
  "price": "10.00",
  "is_available": true,
  "inventory_mode": "none"
}
```

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
- **Medicine References**: Medicine products may optionally link to `medicine_reference`; pharmacies can also create custom medicine products without a reference.
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
