# Onboarding API (v1)

Base URL:
`http://localhost:8000/api/v1/onboarding/`

This app acts as the "Quarantine Zone" for new merchants and riders.
They submit their applications here. Only when an admin approves them do they get promoted to the official `vendors` or given the `Rider` role.

---

## MERCHANTS

### Apply as Merchant
`POST /merchant/apply/`
**Auth Required:** Yes (JWT)
**Description:** Submit a new restaurant or store application.
**Payload Requirements (multipart/form-data):**
- `business_name` (string)
- `business_address` (string)
- `contact_number` (string)
- `dti_sec_certificate` (file)
- `mayors_permit` (file)
- `bir_cor` (file, optional)
- `halal_certification` (file, optional)
- `owner_valid_id` (file)
- `storefront_photo` (image file)

### Check Merchant Application Status
`GET /merchant/status/{uuid}/`
**Auth Required:** Yes (JWT)
**Description:** Allows the applicant to check the status of their application. They can only see their own application.
**Returns:** Application details including `status` (e.g., DRAFT, PENDING, APPROVED, REJECTED, REQUEST_CHANGES) and `admin_remarks` (e.g., "Please upload a clearer ID").

---

## RIDERS

### Apply as Rider
`POST /rider/apply/`
**Auth Required:** Yes (JWT)
**Description:** Submit a new delivery rider application.
**Payload Requirements (multipart/form-data):**
- `vehicle_type` (string: "MOTORCYCLE" or "BICYCLE")
- `plate_number` (string, optional)
- `professional_drivers_license` (file)
- `lto_or_cr` (file, optional)
- `nbi_clearance` (file)
- `barangay_clearance` (file, optional)

### Check Rider Application Status
`GET /rider/status/{uuid}/`
**Auth Required:** Yes (JWT)
**Description:** Allows the applicant to check the status of their rider application. They can only see their own application.
**Returns:** Application details including `status` and `admin_remarks`.

---

## NOTES
- Files must be uploaded using `multipart/form-data`.
- Applicants cannot edit `status` or `admin_remarks`. These are read-only and controlled by the Sarig Admin.
- The user's ID (`applicant`) is automatically pulled from their JWT token. Do not send it in the payload.
