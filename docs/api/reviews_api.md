# Reviews API

The Reviews API manages unified 5-star feedback for Stores and Riders.

## Endpoints

### 1. Submit Review
`POST /api/v1/reviews/submit/`
- Payload requires `order` ID, `store_rating`, `store_comment` (optional), `rider_rating` (optional), and `rider_comment` (optional).
- **Security Check 1**: User must be the owner of the order.
- **Security Check 2**: Order must be in `DELIVERED` status.
- **Security Check 3**: Prevents duplicate reviews (one review per order).
- Stores the data across `OrderReview` model, linking to `Customer`, `Store`, and `RiderProfile`.
