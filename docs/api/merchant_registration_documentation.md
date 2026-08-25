# Merchant Registration Documentation

This file is a merchant-only frontend payload reference.
Use it when building the merchant sign-up forms.

Endpoint:
- `POST /api/v1/onboarding/merchant/apply/`

Request type:
- `multipart/form-data`

Auth:
- not required

Do not send:
- `application_id`
- `applicant`
- `status`
- `admin_remarks`
- `requested_fields`
- `created_at`
- `updated_at`

## Payload

### Business Info

- `business_name` required
- `owner_first_name` required
- `owner_last_name` required
- `company_email` required
- `contact_number` required
- `business_type` required
- `delivery_time` required
- `branch_name` required
- `terms_accepted` required

### Address

- `business_address` required
- `street` required
- `barangay` required
- `city` required
- `province` required
- `postal_code` required
- `location_source` required
- `pinned_address` optional
- `latitude` conditional
- `longitude` conditional

### Documents

- `dti_sec_certificate` required
- `mayors_permit` required
- `bir_cor` optional
- `owner_valid_id` required
- `storefront_photo` required

### Removed Field

- `halal_certification` is no longer accepted

## Response

```json
{
  "application_id": "MR-1028",
  "status": "PENDING",
  "message": "Merchant application submitted for review.",
  "confirmation_email_sent": false,
  "confirmation_email_queued": true
}
```
