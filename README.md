# TrustVault — Secure Document Sharing and Access Management

TrustVault is a secure document management and sharing application built with React, FastAPI, PostgreSQL, Redis, and authenticated file encryption. It provides user authentication, document-level permissions, protected document storage, administrative monitoring, and an audit trail.

**Repository:** https://github.com/MOHAMMADSAIF161/Trustvault

## Table of Contents

1. Project Overview
2. Features
3. Technology Stack
4. Project Structure
5. System Requirements
6. Environment Configuration
7. Database and Redis Setup
8. Backend Installation and Startup
9. Frontend Installation and Startup
10. Creating an Admin User
11. Creating Owner and Viewer Accounts
12. Running the Application
13. API Documentation
14. Security Design
15. Running Tests
16. Troubleshooting
17. Known Limitations
18. Security Documentation
19. Deployment Notes

---

## 1. Project Overview

TrustVault helps users manage and share documents while enforcing access permissions on the server.

The application includes three roles:

| Role | Main responsibility |
|---|---|
| Admin | Manage accounts, view administrative document metadata, inspect audit events, and access the admin dashboard. |
| Owner | Upload and manage owned documents, and share documents with other registered users. |
| Viewer | Access documents shared with them according to their granted permissions. |

Document access is checked on the backend. Hiding an action in the frontend is not treated as a substitute for server-side authorization.

## 2. Features

### Authentication and sessions

- User registration through the backend API.
- Password hashing using Argon2.
- JWT-based access tokens.
- Redis-backed session validation.
- Session invalidation on logout.
- Checks for disabled accounts.

### Document management

- Upload supported document formats.
- List accessible documents.
- View document metadata.
- Preview supported file types.
- Download documents when permitted.
- Edit or delete documents according to permissions.
- Grant and revoke document access.

### File protection

- AES-256-GCM authenticated encryption.
- A separate generated encryption key for each file.
- Wrapped per-file encryption keys.
- Server-generated storage keys.
- Storage-key validation to reduce path traversal risks.
- File extension, content-type, and content validation.
- A maximum upload size of 10 MiB.

### Administration

- List and search users.
- Enable or disable accounts.
- View document metadata.
- Soft-delete documents through an administrative endpoint.
- View audit events.
- Verify the audit hash chain.
- Ask the dashboard assistant for information about the supplied dashboard data.

### Audit trail

- Records selected document permission decisions and other security-sensitive events.
- Stores event details, timestamps, results, and hash-chain information.
- Provides audit-chain verification functionality.

These features describe functionality visible in the source code; they are not a claim that every security risk has been eliminated.

## 3. Technology Stack

| Component | Technology |
|---|---|
| Frontend | React |
| Frontend development server | Vite |
| Backend API | FastAPI |
| Backend language | Python |
| Database | PostgreSQL |
| Session storage | Redis |
| ORM | SQLAlchemy |
| Authentication | JWT and Redis sessions |
| Password hashing | Argon2 |
| File encryption | AES-256-GCM |
| Audit integrity | SHA-256 hash chain |
| Local AI assistant | Ollama endpoint configured in the backend |
| Database containers | Docker Compose |

## 4. Project Structure

The main project files include:

```text
Trustvault/
├── .gitignore
├── README.md
├── THREATS.md
├── PROMPTS.md
├── docker-compose.yml
│
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── auth.py
│   │   ├── security.py
│   │   ├── dependencies.py
│   │   ├── redis_client.py
│   │   ├── permissions.py
│   │   ├── documents.py
│   │   ├── encryption.py
│   │   ├── storage.py
│   │   ├── audit.py
│   │   └── admin.py
│   └── tests/
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx
        ├── App.css
        ├── main.jsx
        └── index.css
```

The tree above highlights the main files. Consult the repository for the complete current file list.

## 5. System Requirements

For local development on Windows, install:

- Python 3.11 or a compatible Python version.
- Node.js compatible with the installed Vite version.
- npm.
- Docker Desktop with Docker Compose.
- Git.
- VS Code or another editor.

Check the installed tools:

```powershell
python --version
node --version
npm --version
git --version
docker --version
docker compose version
```

## 6. Environment Configuration

### Step 1: Create the root `.env` file

The backend configuration expects the environment file at `../.env` when backend commands are run from the `backend` directory.

Create a file named `.env` in the repository root, beside `docker-compose.yml`.

Add the following variables:

```dotenv
POSTGRES_PASSWORD=replace_with_a_long_random_password
POSTGRES_RUNTIME_PASSWORD=replace_with_another_long_random_password

MASTER_ENCRYPTION_KEY=replace_with_a_generated_base64_key
JWT_SECRET=replace_with_a_generated_secret

DATABASE_NAME=trustvault_test
REDIS_URL=redis://127.0.0.1:6379/0

OLLAMA_URL=http://127.0.0.1:11434/api/generate
OLLAMA_MODEL=llama3.2:latest
```

Replace every placeholder with your own values.

- `POSTGRES_PASSWORD` is used by Docker Compose for its initial PostgreSQL user.
- `POSTGRES_RUNTIME_PASSWORD` is the password for the database role used by the application.
- `MASTER_ENCRYPTION_KEY` must be Base64 encoding of exactly 32 random bytes.
- `JWT_SECRET` is the secret used to sign JWT tokens.
- `DATABASE_NAME` selects the application database.
- `REDIS_URL` identifies the Redis instance.

### Step 2: Generate the encryption key

Run:

```powershell
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Copy the output into `MASTER_ENCRYPTION_KEY`.

### Step 3: Generate a JWT secret

Run:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the output into `JWT_SECRET`.

Generate strong, separate passwords for both PostgreSQL variables. Keep all these values private.

**Important:** Never commit your real `.env` file to GitHub. The root `.gitignore` excludes it.

## 7. Database and Redis Setup

The existing `docker-compose.yml` launches PostgreSQL and Redis. The backend configuration uses the database name `trustvault_test` and the PostgreSQL role `trustvault_runtime`, so create that runtime role and database for a fresh local setup.

### Step 1: Start PostgreSQL and Redis

Open PowerShell in the project root:

```powershell
cd C:\Projects\TrustVault
docker compose up -d db redis
docker compose ps
```

Wait until both services are healthy.

### Step 2: Create the runtime database role and database

Open a PostgreSQL shell in the container:

```powershell
docker compose exec db psql -U trustvault_app -d postgres
```

For a fresh database, execute the following SQL. Replace the password placeholder with the exact value of `POSTGRES_RUNTIME_PASSWORD` in your `.env` file.

```sql
CREATE ROLE trustvault_runtime
WITH LOGIN PASSWORD 'YOUR_POSTGRES_RUNTIME_PASSWORD';

CREATE DATABASE trustvault_test
OWNER trustvault_runtime;
```

Then exit PostgreSQL:

```sql
\q
```

Run the creation statements only once. If the role or database already exists, inspect the existing configuration instead of creating duplicates.

The application connects to PostgreSQL at `127.0.0.1:5433`, as configured in `backend/app/config.py`.

### Step 3: Verify Redis

Run:

```powershell
docker compose exec redis redis-cli ping
```

Expected response:

```text
PONG
```

## 8. Backend Installation and Startup

### Step 1: Open the backend directory

```powershell
cd C:\Projects\TrustVault\backend
```

### Step 2: Create a Python virtual environment

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script activation, use a permitted terminal or follow your organization's PowerShell execution policy. Do not weaken the policy globally just to activate a virtual environment.

### Step 3: Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**Dependency note:** The reviewed source imports `EmailStr` and `magic`, but the current `backend/requirements.txt` does not list `email-validator` or a package providing `magic`. If imports fail, install the missing packages for your platform. On Windows, a commonly used option for the latter is:

```powershell
python -m pip install email-validator python-magic-bin
```

For reproducible clean-clone installation, add the appropriate dependencies to `backend/requirements.txt` and commit that change.

### Step 4: Start the API

Make sure the terminal's current directory is `backend`:

```powershell
python -m uvicorn app.main:app --reload
```

The API should be available at:

- API root: http://127.0.0.1:8000/
- Health check: http://127.0.0.1:8000/health
- Interactive API documentation: http://127.0.0.1:8000/docs

The application creates its SQLAlchemy tables through `Base.metadata.create_all()` when the FastAPI application starts.

Keep this terminal running.

## 9. Frontend Installation and Startup

Open a second terminal.

```powershell
cd C:\Projects\TrustVault\frontend
npm install
npm run dev
```

Open the Vite URL displayed in the terminal, normally:

http://localhost:5173/

The current frontend uses the API URL:

```javascript
const API_URL = "http://127.0.0.1:8000";
```

The backend's CORS configuration permits the local frontend origins `http://localhost:5173` and `http://127.0.0.1:5173`.

The current frontend provides a login interface. Create user accounts through the registration API or the documented local bootstrap procedure below.

## 10. Creating the First Admin User

**This is the recommended local bootstrap procedure for the current code.**

The registration endpoint accepts only `owner` and `viewer` roles. It does not allow public registration as `admin`.

To create the initial admin, use a local Python command that stores the password as an Argon2 hash and assigns the `ADMIN` enum role. Do not expose a public API endpoint that allows anyone to register as an administrator.

### Step 1: Make sure the database is ready

Ensure that:

- PostgreSQL is running.
- The `.env` file contains the correct database settings.
- The `trustvault_runtime` role and `trustvault_test` database exist.

### Step 2: Open a backend terminal

```powershell
cd C:\Projects\TrustVault\backend
.\.venv\Scripts\Activate.ps1
```

### Step 3: Run the admin bootstrap script

Copy and paste the complete block below into PowerShell while the current directory is `backend`.

The script creates a new admin account when the email does not exist. If the email already belongs to an account, it asks for explicit confirmation before promoting that account.

```powershell
@'
from getpass import getpass

from app import models
from app.database import Base, engine, SessionLocal
from app.models import User, UserRole
from app.security import hash_password

Base.metadata.create_all(bind=engine)

email = input("Admin email address: ").strip().lower()

if not email or "@" not in email:
    raise SystemExit("Enter a valid email address.")

with SessionLocal() as db:
    user = db.query(User).filter(User.email == email).first()

    if user is not None:
        confirmation = input(
            "This account exists. Type PROMOTE to make it an admin: "
        ).strip()

        if confirmation != "PROMOTE":
            raise SystemExit("No changes made.")

        user.role = UserRole.ADMIN
        db.commit()
        db.refresh(user)

        print(f"Account {user.email} now has role: {user.role.value}")

    else:
        password = getpass("Create admin password (12-128 characters): ")

        if not 12 <= len(password) <= 128:
            raise SystemExit(
                "Password must be between 12 and 128 characters."
            )

        confirm_password = getpass("Confirm admin password: ")

        if password != confirm_password:
            raise SystemExit("Passwords do not match.")

        user = User(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"Admin created: {user.email}")
        print(f"Role: {user.role.value}")
        print("Keep the password secure.")
'@ | python -
```

### Step 4: Log in as Admin

Open the TrustVault frontend at http://localhost:5173/.

Select the **Administrator** role on the login screen and use the admin email and password created in the previous step.

The frontend checks that the selected role matches the role returned by the backend.

If authentication is successful, the application should open the Admin Dashboard.

### Admin creation security notes

- Run the bootstrap command locally in a trusted environment.
- Do not put administrator passwords in source code or commit them to GitHub.
- Do not expose this bootstrap code as an unauthenticated production API.
- Keep administrator access limited to the people who require it.
- The current model does not add a dedicated audit event for this one-time CLI bootstrap operation.

## 11. Creating Owner and Viewer Accounts

The backend registration endpoint is:

`POST /auth/register`

It accepts `owner` or `viewer`, but not `admin`.

You can create accounts using the Swagger interface at http://127.0.0.1:8000/docs.

Alternatively, from PowerShell, create an owner:

```powershell
$body = @{
    email = "owner@example.com"
    password = "ChangeThisToAStrongPassword123!"
    role = "owner"
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/auth/register" `
    -ContentType "application/json" `
    -Body $body
```

Create a viewer by using a different email and setting:

```json
{
  "email": "viewer@example.com",
  "password": "ChangeThisToAnotherStrongPassword123!",
  "role": "viewer"
}
```

These are examples only. Use your own unique passwords.

The registration endpoint enforces password length between 12 and 128 characters. It also rejects duplicate email addresses.

## 12. Running the Application

Start the services in this order:

1. Create the root `.env` file.
2. Start PostgreSQL and Redis with Docker Compose.
3. Create the `trustvault_runtime` database role and `trustvault_test` database.
4. Install backend dependencies and start FastAPI.
5. Create the first admin account through the local bootstrap script.
6. Start the React/Vite frontend.
7. Create owner and viewer accounts through the registration endpoint.
8. Log in and test document upload, sharing, preview, download, and revocation.
9. Use the admin account to inspect administrative data and audit events.

## 13. API Documentation

FastAPI's interactive documentation is available at:

http://127.0.0.1:8000/docs

### Health and authentication

| Method | Endpoint | Access |
|---|---|---|
| GET | `/` | Public |
| GET | `/health` | Public |
| POST | `/auth/register` | Public; owner or viewer role only |
| POST | `/auth/login` | Public |
| POST | `/auth/logout` | Authenticated user |
| GET | `/me` | Authenticated user |

### Document endpoints

| Method | Endpoint | Access rule |
|---|---|---|
| GET | `/documents` | Authenticated user; returns documents visible to that user |
| POST | `/documents/upload` | Active owner |
| GET | `/documents/{document_id}` | Authenticated user with view permission |
| GET | `/documents/{document_id}/view` | Authenticated user with view permission and a supported preview type |
| GET | `/documents/{document_id}/download` | Authenticated user with download permission |
| POST | `/documents/{document_id}/grants` | Document owner |
| DELETE | `/documents/{document_id}/grants/{user_id}` | Document owner |
| DELETE | `/documents/{document_id}` | Requires the applicable document delete permission |
| PUT | `/documents/{document_id}/edit` | Requires the applicable document edit permission |

### Administrative endpoints

| Method | Endpoint | Access |
|---|---|---|
| GET | `/admin/users` | Admin |
| PATCH | `/admin/users/{user_id}/disable` | Admin |
| PATCH | `/admin/users/{user_id}/enable` | Admin |
| GET | `/admin/documents` | Admin |
| DELETE | `/admin/documents/{document_id}` | Admin |
| GET | `/admin/dashboard` | Admin |
| GET | `/admin/audit` | Admin |
| GET | `/admin/audit/verify` | Admin |
| POST | `/admin/assistant` | Admin |

All protected API calls require a valid bearer token. Use the live Swagger schema to inspect request bodies, query parameters, response models, and current endpoint details.

The admin endpoints manage accounts and administrative metadata. An admin role does not automatically grant access to private document contents through the normal document permission checker.

## 14. Security Design

### Authentication

Passwords are hashed with Argon2. JWT tokens are checked against Redis-backed sessions. Logout removes the session, and protected requests verify that the user still exists and is active.

### Authorization

Document access checks are performed on the backend using ownership and explicit grants. Viewer restrictions are applied to edit, delete, and share actions.

### Encryption

The code uses AES-256-GCM with a generated per-file key. The per-file key is wrapped using a master encryption key.

### Storage

Storage keys are generated by the server and validated before file operations. Upload validation checks permitted file extensions and file content.

### Audit trail

Audit events use SHA-256 hash chaining. Verification can detect event hashes or previous-hash links that do not match.

### Security documentation

- `THREATS.md` describes source-backed threats, controls, and limitations.
- `PROMPTS.md` records AI-assisted development, mistakes identified, corrections, and commit links.

These mechanisms provide specific protections, but no single control eliminates all security risks.

## 15. Running Tests

Ensure that the backend dependencies are installed and the expected database environment is configured.

From PowerShell:

```powershell
cd C:\Projects\TrustVault\backend
.\.venv\Scripts\Activate.ps1
python -m pytest
```

Run targeted security tests when investigating a particular area:

```powershell
python -m pytest tests/test_cross_owner_isolation.py
python -m pytest tests/test_permission_revocation.py
python -m pytest tests/test_disabled_session.py
python -m pytest tests/test_encryption.py
python -m pytest tests/test_storage.py
python -m pytest tests/test_audit_chain.py
python -m pytest tests/test_view_only_download.py
python -m pytest tests/test_admin.py
```

Some tests use mocked data, while others interact with configured services. A test result should be reported as successful only after the test has actually been executed.

### Frontend validation

From the frontend directory:

```powershell
cd C:\Projects\TrustVault\frontend
npm run lint
npm run build
```

## 16. Troubleshooting

### PostgreSQL connection failure

Check that the database container is running:

```powershell
docker compose ps
```

Confirm that:

- The root `.env` file contains both PostgreSQL passwords.
- The runtime role is named `trustvault_runtime`.
- The database is named `trustvault_test`.
- PostgreSQL is reachable through `127.0.0.1:5433`.

### Redis connection failure

Run:

```powershell
docker compose exec redis redis-cli ping
```

Check that `REDIS_URL` points to the correct running Redis instance.

### Invalid or expired session

Log out and log in again. The application validates sessions through Redis, so a missing session cannot be fixed merely by retaining the old JWT.

### Admin login fails

Confirm that the account's database role is `admin` and that the login screen's selected role is **Administrator**.

If necessary, rerun the local bootstrap command and explicitly confirm promotion of the existing account.

### Missing Python module

Check that the correct virtual environment is active:

```powershell
python -c "import sys; print(sys.executable)"
```

Install the project's requirements and any missing dependencies identified in Section 8.

### File encryption error

Verify that `MASTER_ENCRYPTION_KEY` contains valid Base64 representing exactly 32 bytes. The same master key must remain available to decrypt existing stored documents.

Do not replace the master key in a database containing existing encrypted files unless you have a proper key migration or recovery plan.

### Frontend cannot reach the backend

Check that FastAPI is running on port 8000 and that the frontend API URL and CORS origins match the local setup.

## 17. Known Limitations

The following points require attention or independent verification:

- The public registration API accepts only owner and viewer roles. Admin creation uses a local bootstrap procedure.
- The current frontend uses a hard-coded local API URL.
- The storage root is hard-coded to `C:\TrustVaultPrivateStorage`; non-Windows deployment requires a suitable configuration change.
- The reviewed backend requirements omit dependencies for the `EmailStr` and `magic` imports.
- Production key management, external immutable audit storage, malware scanning, and a complete deployment security configuration are not established by the reviewed source.
- Test results must be generated from an actual test run; this README does not claim that the full suite has passed.
- The current repository inspection did not establish a publicly deployed demo URL. Add a live URL after a deployment is available.

## 18. Security Documentation

### THREATS.md

This file explains the threats considered, what relevant source code does, and the limitations or accepted risks of those controls.

### PROMPTS.md

This file records the use of AI during development, including prompts or fair summaries, AI output, specific mistakes identified, the corrections made, and links to the relevant commits.

The AI log must reflect genuine development work and actual commit history.

## 19. Deployment Notes

The current Docker Compose configuration starts PostgreSQL and Redis; it does not build and launch the FastAPI backend or React frontend as containers.

For deployment:

- Configure environment variables through the deployment platform's secret-management facility.
- Use HTTPS for public traffic.
- Restrict database, Redis, and filesystem access.
- Configure the production frontend API URL and allowed CORS origins.
- Configure private document storage and secure encryption-key management.
- Verify protected endpoints, role permissions, permission revocation, and audit behavior in the deployed environment.
- Do not publish real passwords or sensitive seed data in the repository.
- Add the deployed application URL and safe evaluator accounts to this README only after those resources exist and have been verified.

