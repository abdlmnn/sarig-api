# Users API (v1)

Base URL:
`http://localhost:8000/api/v1/users/`

---

## AUTHENTICATION

### Get JWT Token
`POST /auth/token/`
- **Body**: `username`, `password`

### Refresh Token
`POST /auth/token/refresh/`
- **Body**: `refresh`

### Register Account
`POST /register/`
- **Body**: `username`, `email`, `phone_number`, `password`, `first_name`, `last_name`
- **Default Role**: `Customer`

---

## MY ACCOUNT (ME)

### Get Current User
`GET /me/`
**Auth Required**
- Returns role properties: `is_customer`, `is_merchant`, `is_rider`.

### Profile Management
`GET /me/profile/`
`PATCH /me/profile/`

### Address Management
`GET /me/addresses/`
`POST /me/addresses/`

---

## NOTES
- **IDs**: All primary keys are now **UUIDv4**.
- **Roles**: Normalized to Title Case (`Customer`, `Merchant`, `Rider`).
- **Security**: Password hashing and JWT rotation are handled by `SimpleJWT`.
