# Onboarding API v1 Frontend Contract

Base URL:
`/api/v1`

This document is the frontend-facing contract for merchant and rider onboarding.
The backend now treats merchant and rider sign-up as public application flows:

- submit application
- check application status using `application_id`
- react to `REQUEST_CHANGES` with a secure edit token
- complete account setup after approval with a secure setup token

Do not send `applicant`, `status`, `admin_remarks`, `requested_fields`, `created_at`, or `updated_at` from the frontend unless the endpoint explicitly says it accepts them.

## Merchant Signup

### Submit Merchant Application

`POST /api/v1/onboarding/merchant/apply/`

Request type:
`multipart/form-data`

Auth:
`not required`

Frontend payload keys:

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
bir_cor
owner_valid_id
storefront_photo
```

Important rules:
- `business_type` accepts `Shop` or `Restaurant`; backend stores `SHOP` or `RESTAURANT`
- `delivery_time` accepts `morning`, `afternoon`, `evening`, `allday`; backend stores `MORNING`, `AFTERNOON`, `EVENING`, `ALL_DAY`
- `terms_accepted` must be `true`
- if `location_source = pin`, send `pinned_address`, `latitude`, and `longitude`
- `halal_certification` is no longer part of the merchant payload

Success response:

```json
{
  "application_id": "MR-1028",
  "status": "PENDING",
  "message": "Merchant application submitted for review.",
  "confirmation_email_sent": true
}
```

### Check Merchant Status

`POST /api/v1/onboarding/merchant/status/check/`

Request type:
`application/json`

Request body:

```json
{
  "application_id": "MR-1028"
}
```

Response:

```json
{
  "application_id": "MR-1028",
  "type": "MERCHANT",
  "status": "PENDING",
  "submitted_at": "2026-06-23T10:30:00+08:00",
  "updated_at": "2026-06-23T10:30:00+08:00",
  "applicant_name": "Hassan Macarambon",
  "business_name": "Sultan Food House",
  "admin_remarks": "",
  "next_action": "Wait for admin review.",
  "can_edit": false,
  "edit_url": null
}
```

## Rider Signup

### Submit Rider Application

`POST /api/v1/onboarding/rider/apply/`

Request type:
`multipart/form-data`

Auth:
`not required`

Frontend payload keys:

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
lto_or_cr
nbi_clearance
barangay_clearance
```

Important rules:
- `vehicle_type` accepts `MOTORCYCLE`, `BICYCLE`, or `CAR`
- `plate_number` is required for `MOTORCYCLE` and `CAR`
- phone numbers are accepted as strings; do not strip punctuation on the frontend

Success response:

```json
{
  "application_id": "RD-2044",
  "status": "PENDING",
  "message": "Rider application submitted for review.",
  "confirmation_email_sent": true
}
```

### Check Rider Status

`POST /api/v1/onboarding/rider/status/check/`

Request type:
`application/json`

Request body:

```json
{
  "application_id": "RD-2044"
}
```

Response:

```json
{
  "application_id": "RD-2044",
  "type": "RIDER",
  "status": "REQUEST_CHANGES",
  "submitted_at": "2026-06-23T10:30:00+08:00",
  "updated_at": "2026-06-23T11:15:00+08:00",
  "applicant_name": "Ameer S.",
  "admin_remarks": "Please upload a clearer NBI clearance.",
  "next_action": "Update the requested fields using the secure edit link sent to your email.",
  "can_edit": true,
  "edit_url": "https://sarig.app/rider/application/edit/secure-token"
}
```

## Request Changes Flow

When admin requests changes, the frontend should:

1. Use the secure edit link from email or the `edit_url` returned by status check.
2. GET the edit endpoint to load requested fields and application data.
3. PATCH only the fields listed in `requested_fields`.
4. Upload changed documents/files again when required.

### Edit Application

`GET /api/v1/onboarding/applications/edit/{token}/`

`PATCH /api/v1/onboarding/applications/edit/{token}/`

Request type:
`multipart/form-data`

PATCH rule:
- only send fields listed in `requested_fields`
- token is single-use and becomes revoked after successful resubmission

## Account Setup Flow

After approval, the frontend receives an account setup link by email.

### Validate Account Setup Token

`GET /api/v1/accounts/setup/{token}/`

### Create Credentials

`POST /api/v1/accounts/setup/{token}/`

Request body:

```json
{
  "username": "sultanfood",
  "password": "secure-password"
}
```

Rules:
- token must already be approved
- username must be unique
- do not send email or phone number; those come from the application

## Admin Desk

These endpoints are for the admin onboarding desk only.

### List Applications

`GET /api/v1/admin/onboarding/applications/`

Query params:

```text
type=merchant|rider|all
status=pending|under_review|request_changes|approved|rejected|all
search=string
ordering=newest|oldest
page=1
page_size=20
```

### Application Detail

`GET /api/v1/admin/onboarding/applications/{application_id}/`

### View Document

`GET /api/v1/admin/onboarding/applications/{application_id}/documents/{document_key}/`

### Approve Application

`POST /api/v1/admin/onboarding/applications/{application_id}/approve/`

### Request Changes

`POST /api/v1/admin/onboarding/applications/{application_id}/request-changes/`

Request body:

```json
{
  "admin_remarks": "Please upload a clearer NBI clearance.",
  "requested_fields": ["nbi_clearance"]
}
```

### Reject Application

`POST /api/v1/admin/onboarding/applications/{application_id}/reject/`

Request body:

```json
{
  "admin_remarks": "Application rejected because required documents could not be verified."
}
```

## Frontend Mapping Summary

Merchant step 1:
- `storeName` -> `business_name`
- `ownerFirstName` -> `owner_first_name`
- `ownerLastName` -> `owner_last_name`
- `companyEmail` -> `company_email`
- `mobileNumber` -> `contact_number`
- `businessType` -> `business_type`
- `preferredDeliveryTime` -> `delivery_time`
- `branch` -> `branch_name`
- `acceptTerms` -> `terms_accepted`

Merchant step 2:
- `address` -> `business_address`
- `street` -> `street`
- `barangay` -> `barangay`
- `city` -> `city`
- `province` -> `province`
- `postalCode` -> `postal_code`
- `locationSource` -> `location_source`
- `pinnedAddress` -> `pinned_address`
- `latitude` -> `latitude`
- `longitude` -> `longitude`

Merchant step 3:
- `dti_sec_certificate` -> `dti_sec_certificate`
- `mayors_permit` -> `mayors_permit`
- `bir_cor` -> `bir_cor`
- `owner_valid_id` -> `owner_valid_id`
- `storefront_photo` -> `storefront_photo`

Rider step 1:
- `firstName` -> `first_name`
- `lastName` -> `last_name`
- `email` -> `email`
- `phoneNumber` -> `phone_number`
- `acceptTerms` -> `terms_accepted`

Rider step 2:
- `currentAddress` -> `current_address`
- `barangay` -> `barangay`
- `city` -> `city`
- `province` -> `province`
- `postalCode` -> `postal_code`
- `emergencyContactName` -> `emergency_contact_name`
- `emergencyContactNumber` -> `emergency_contact_number`
- `emergencyContactRelationship` -> `emergency_contact_relationship`

Rider step 3:
- `vehicleType` -> `vehicle_type`
- `vehicleBrand` -> `vehicle_brand`
- `plateNumber` -> `plate_number`
- `vehiclePhotoFront` -> `vehicle_photo_front`
- `vehiclePhotoBack` -> `vehicle_photo_back`

Rider step 4:
- `professionalDriversLicense` -> `professional_drivers_license`
- `ltoOrCr` -> `lto_or_cr`
- `nbiClearance` -> `nbi_clearance`
- `barangayClearance` -> `barangay_clearance`
