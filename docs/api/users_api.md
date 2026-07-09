# Users API (v1)

Base URL:
`http://localhost:8000/api/v1/users/`

---

## AUTHENTICATION

### Generic JWT Token
`POST /api/v1/auth/token/`
- **Body**: `username`, `password`
- **Use**: legacy/general login when the frontend does not need role-specific routing.

### Admin Login
`POST /api/v1/auth/login/`

Use this for the superadmin dashboard only.

Request body:

```json
{
  "identifier": "admin@sarig.local",
  "password": "admin12345"
}
```

`identifier` accepts either username or email.

Allowed account:
- `is_superuser = true`

Response:

```json
{
  "refresh": "jwt-refresh-token",
  "access": "jwt-access-token",
  "account_type": "ADMIN",
  "user": {
    "id": "uuid",
    "username": "admin",
    "email": "admin@sarig.local",
    "first_name": "",
    "last_name": "",
    "phone_number": null,
    "is_customer": false,
    "is_merchant": false,
    "is_rider": false
  }
}
```

### Merchant Login
`POST /api/v1/auth/login/`

Use this for approved merchant dashboard access.

Request body:

```json
{
  "identifier": "merchant1@sarig.local",
  "password": "merchant12345"
}
```

`identifier` accepts either username or email.

Allowed account:
- user has `Role(name="Merchant")`
- user is not a superadmin

Response:

```json
{
  "refresh": "jwt-refresh-token",
  "access": "jwt-access-token",
  "account_type": "MERCHANT",
  "user": {
    "id": "uuid",
    "username": "merchant1",
    "email": "merchant1@sarig.local",
    "first_name": "",
    "last_name": "",
    "phone_number": "+639171101003",
    "is_customer": false,
    "is_merchant": true,
    "is_rider": false
  }
}
```

### Refresh Token
`POST /api/v1/auth/token/refresh/`
- **Body**: `refresh`

### Register Account
`POST /register/`
- **Body**: `username`, `email`, `phone_number`, `password`, `first_name`, `last_name`
- **Default Role**: `Customer`
- **Registration Flow Doc**: `docs/api/user_merchant_rider_registration_flow.md`

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
