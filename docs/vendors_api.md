# Vendors API (v1)

Base URL:
http://localhost:8000/api/v1/

--

Business Vertical

List Business Verticals
GET /api/verticals/

Create Vertical (Merchant only)
POST /api/verticals/

Retrieve Vertical Detail
GET /api/verticals/{id}/

Update Vertical (Full update)
PUT /api/verticals/{id}/

Partial Update Vertical
PATCH /api/verticals/{id}/

Delete Vertical
DELETE /api/verticals/{id}/

--

Store


List Stores
GET /api/stores/

Create Vertical (if allowed by permissions)
POST /api/verticals/

Retrieve Vertical Detail
GET /api/verticals/{id}/

Update Vertical
PUT /api/verticals/{id}/

Partial Update Vertical
PATCH /api/verticals/{id}/

Delete Vertical
DELETE /api/verticals/{id}/

--

Geo Filtering (IMPORTANT for future use)

Nearby Stores (radius search – currently commented but ready)
GET /api/stores/?lat={lat}&lng={lng}&radius={km}

--

Auth Behavior Summary
stores/ → requires authenticated user
Merchant role → can create stores
Admin (is_staff) → can access all stores
Normal merchant → only sees own stores
