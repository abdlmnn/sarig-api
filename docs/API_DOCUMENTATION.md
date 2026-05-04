# API Documentation (v1)

Base URL:
http://localhost:8000/api/v1/

--

AUTH

POST /auth/token/
POST /auth/token/refresh/

CREATE ACCOUNT USER

POST /users/register/

--

USER
Get Users

GET /users/
Auth required

--

ME (Current User)
Get current user

GET /users/me/

--

Get/Update Profile

GET /users/me/profile/

PATCH /users/me/profile/

--

Get/Create Addresses

GET /users/me/addresses/

POST /users/me/addresses/

--

PROFILES
List Profiles

GET /users/profiles/

Create Profile

POST /users/profiles/

--

ADDRESSES
List Addresses

GET /users/addresses/

Create Address

POST /users/addresses/

---

NOTES
/users/me/ is the recommended way to access user data
/users/{id}/ exists only for admin/debug
Roles are handled via User.roles


VERSIONING

Current API version:

v1

Future:

v2 (planned)
