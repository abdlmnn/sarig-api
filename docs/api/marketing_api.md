# Marketing API

The Marketing API handles promotional campaigns, discount codes, and usage limits.

## Models
* **PromoCode**: Supports fixed amount and percentage-based discounts. Validations include `minimum_spend`, `max_discount_amount`, expiration dates, and `usage_limit`.

## Application Logic
* **Validation**: Integrated directly into `CheckoutView`. The `is_valid` method checks dates, minimum spend, and available usage slots.
* **Calculation**: The `calculate_discount` method dynamically computes the deduction, ensuring it never exceeds the `max_discount_amount` or the total order value.
* **Concurrency**: Usage counters are incremented using database `F()` expressions inside a `transaction.atomic()` block during checkout. This guarantees no "over-usage" if multiple users apply the code at the exact same millisecond.
