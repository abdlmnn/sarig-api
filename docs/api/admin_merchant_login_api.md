# Admin and Merchant Login API

This document is the frontend contract for admin and merchant sign-in.

Base URL:
`/api/v1`

Both login endpoints accept either username or email through the same field:
`identifier`.

## Admin Login

Use this endpoint for the superadmin dashboard sign-in page.

Endpoint:
`POST /api/v1/auth/admin/login/`

Auth:
not required

Request type:
`application/json`

Request body:

```json
{
  "identifier": "admin",
  "password": "admin12345"
}
```

Email also works:

```json
{
  "identifier": "admin@sarig.local",
  "password": "admin12345"
}
```

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
    "first_name": "Sarig",
    "last_name": "Admin",
    "phone_number": null,
    "is_customer": false,
    "is_merchant": false,
    "is_rider": false
  }
}
```

Frontend routing after success:
- send user to `/admin/dashboard`
- store `access` for authenticated admin API calls
- store `refresh` for token refresh/logout

## Merchant Login

Use this endpoint for the approved merchant sign-in page.

Endpoint:
`POST /api/v1/auth/merchant/login/`

Auth:
not required

Request type:
`application/json`

Request body:

```json
{
  "identifier": "merchant3",
  "password": "merchant12345"
}
```

Email also works:

```json
{
  "identifier": "merchant3@sarig.local",
  "password": "merchant12345"
}
```

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
    "username": "merchant3",
    "email": "merchant3@sarig.local",
    "first_name": "",
    "last_name": "",
    "phone_number": "+639171101003",
    "is_customer": false,
    "is_merchant": true,
    "is_rider": false
  }
}
```

Frontend routing after success:
- send user to `/merchant/dashboard`
- store `access` for authenticated merchant API calls
- store `refresh` for token refresh/logout

## Refresh Token

Endpoint:
`POST /api/v1/auth/token/refresh/`

Request body:

```json
{
  "refresh": "jwt-refresh-token"
}
```

Response:

```json
{
  "access": "new-jwt-access-token",
  "refresh": "rotated-refresh-token"
}
```

The project uses rotating refresh tokens, so the frontend should replace the old refresh token when the response includes a new one.

## Logout

Endpoint:
`POST /api/v1/auth/logout/`

Auth:
Bearer access token required

Request body:

```json
{
  "refresh": "jwt-refresh-token"
}
```

Response:

```json
{
  "detail": "Logged out successfully."
}
```

## Error Responses

Wrong password or unknown username/email returns `400`.

Example:

```json
{
  "code": "invalid_credentials",
  "message": "Invalid username/email or password."
}
```

The backend intentionally returns the same error for an unknown account and a wrong password. The frontend should display `message` directly.

Wrong role examples:
- merchant account using `/api/v1/auth/admin/login/`
- superadmin account using `/api/v1/auth/merchant/login/`

Response:

```json
{
  "code": "forbidden",
  "message": "This account is not allowed to use this login."
}
```

Inactive account response:

```json
{
  "code": "inactive",
  "message": "This account is inactive."
}
```

## Seeded Test Accounts

Run this backend command first if the database has no mock data:

```bash
python manage.py seed_onboarding_mock_data --reset
```

Admin:

```text
username: admin
email: admin@sarig.local
password: admin12345
```

Approved merchant examples:

```text
username: merchant3
email: merchant3@sarig.local
password: merchant12345
```

```text
username: merchant8
email: merchant8@sarig.local
password: merchant12345
```

## Frontend Notes

- The request field is `identifier`, not `username`.
- The value can be either username or email.
- Use the admin login endpoint only for the admin sign-in screen.
- Use the merchant login endpoint only for the merchant sign-in screen.
- The generic endpoint `/api/v1/auth/token/` still exists, but frontend admin and merchant screens should use the role-specific endpoints above.
