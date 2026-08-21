# User + Merchant + Rider Registration Flow

This is the frontend contract for onboarding.
The current backend flow is:

1. User creates a login account only for customer access.
2. Merchant or rider submits a public onboarding application.
3. Admin reviews the application.
4. If approved, backend sends account setup link.
5. Applicant sets a password through the setup token and then logs in with email.

Do not create merchant or rider login credentials during application submission.

## Shared Rules

- Merchant and rider applications are public.
- Use `multipart/form-data` for file uploads.
- `application_id` is the public lookup key, not the database UUID.
- Status checks use `application_id`.
- `halal_certification` is not part of merchant onboarding anymore.

## Merchant Fields

Endpoint:
- `POST /api/v1/onboarding/merchant/apply/`

Required payload keys:

```text
business_name
owner_first_name
owner_last_name
company_email
contact_number
business_type
delivery_time
branch_name
terms_accepted
business_address
street
barangay
city
province
postal_code
location_source
pinned_address
latitude
longitude
dti_sec_certificate
mayors_permit
owner_valid_id
storefront_photo
bir_cor
```

Optional:
- `bir_cor`
- `pinned_address`
- `latitude`
- `longitude` only when `location_source = pin`

Accepted values:
- `business_type`: `Shop` or `Restaurant`
- `delivery_time`: `morning`, `afternoon`, `evening`, `allday`

Success response:

```json
{
  "application_id": "MR-1028",
  "status": "PENDING",
  "message": "Merchant application submitted for review.",
  "confirmation_email_sent": false,
  "confirmation_email_queued": true
}
```

## Rider Fields

Endpoint:
- `POST /api/v1/onboarding/rider/apply/`

Required payload keys:

```text
first_name
last_name
email
phone_number
terms_accepted
current_address
barangay
city
province
postal_code
emergency_contact_name
emergency_contact_number
emergency_contact_relationship
vehicle_type
vehicle_brand
plate_number
vehicle_photo_front
vehicle_photo_back
professional_drivers_license
nbi_clearance
lto_or_cr
barangay_clearance
```

Conditional:
- `plate_number` is required for `MOTORCYCLE` and `CAR`

Accepted vehicle values:
- `MOTORCYCLE`
- `BICYCLE`
- `CAR`

Success response:

```json
{
  "application_id": "RD-2044",
  "status": "PENDING",
  "message": "Rider application submitted for review.",
  "confirmation_email_sent": false,
  "confirmation_email_queued": true
}
```

## Status Lookup

Merchant:
- `POST /api/v1/onboarding/merchant/status/check/`

Rider:
- `POST /api/v1/onboarding/rider/status/check/`

Request body:

```json
{
  "application_id": "MR-1028"
}
```

## Request Changes

If status becomes `REQUEST_CHANGES`, the backend sends an edit token.

Frontend should:
- open `GET /api/v1/onboarding/applications/edit/{token}/`
- display requested fields
- send `PATCH /api/v1/onboarding/applications/edit/{token}/`
- only include fields that were requested

## Account Setup

If status becomes `APPROVED`, the backend sends a setup token.

Frontend should:
- open `GET /api/v1/onboarding/accounts/setup/{token}/`
- submit credentials with `POST /api/v1/onboarding/accounts/setup/{token}/`

Body:

```json
{
  "password": "secure-password",
  "password_confirm": "secure-password"
}
```

The backend generates an internal username. Merchant and rider login should use the application email and selected password. Successful setup consumes the token and changes the application status from `APPROVED` to `ACTIVE`.
