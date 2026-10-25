# TrustVault — Threat Model and Security Mitigations

## Overview

TrustVault is a document-sharing application with authentication, role-based permissions, encrypted file storage, and audit logging.

This document describes the security controls implemented in the source code reviewed in the public TrustVault repository.

Repository: https://github.com/MOHAMMADSAIF161/Trustvault

The controls described below are based on source-code inspection. This document does not claim that every possible attack is prevented or that the complete application has passed a security audit.

---

## 1. Unauthorized Access to Another User's Documents

**Threat:** A user attempts to access another user's private document by changing a document ID or requesting an operation they are not permitted to perform.

**What the code does:**

- `backend/app/permissions.py` defines document actions, including viewing, downloading, editing, deleting, and sharing.
- The `can_access()` function checks whether the user owns the document or has an explicit permission grant for the requested action.
- `backend/app/documents.py` uses document permission checks when handling document operations.
- Unauthorized document requests generally receive a `404 Document not found` response rather than being given the document's contents.
- `backend/tests/test_cross_owner_isolation.py` contains tests for cross-owner metadata access, downloading, granting permissions, and revoking permissions.

These controls provide application-level checks for document access. The tests include mocked permission checks, so they do not independently prove that every authorization path is correct.

## 2. Invalid, Expired, or Revoked Sessions

**Threat:** A user attempts to access protected endpoints using an invalid token or a session that has expired or been revoked.

**What the code does:**

- `backend/app/security.py` creates JWT access tokens containing the user ID, session ID, issue time, and expiration time.
- Tokens are signed using the configured JWT secret and the HS256 algorithm.
- `backend/app/dependencies.py` validates the token and checks that its session exists in Redis.
- The Redis session's user ID must match the user ID contained in the token.
- Protected requests also check that the account exists and is active.
- `backend/app/auth.py` creates a Redis session during login and deletes the session during logout.
- Redis connection errors cause authentication to return a service-unavailable response rather than accepting the request as authenticated.

Relevant files:

- `backend/app/auth.py`
- `backend/app/security.py`
- `backend/app/dependencies.py`
- `backend/app/redis_client.py`

## 3. Insecure Password Storage

**Threat:** Stored passwords could be exposed if passwords were saved directly in the database.

**What the code does:**

- `backend/app/security.py` uses Argon2 through `argon2-cffi` to hash passwords and verify password attempts.
- `backend/app/auth.py` requires registration passwords to have a length between 12 and 128 characters.
- Login returns a common `Invalid email or password` message when the email is not found or the password is incorrect.

The reviewed login route does not visibly implement a dedicated login rate limit. Such protection should not be claimed based on this code alone.

## 4. Disabled Accounts Using Existing Sessions

**Threat:** A disabled user attempts to keep using a previously issued access token.

**What the code does:**

- `backend/app/dependencies.py` checks the account's active status on protected requests.
- `backend/app/admin.py` provides an administrator operation to disable a user.
- The disable operation sets `is_active` to `False` and records a `user.disable` audit event.
- The login endpoint also rejects disabled accounts.
- `backend/tests/test_disabled_session.py` and `backend/tests/test_admin.py` contain tests related to disabled-account behavior.

## 5. Viewers Performing Unauthorized Operations

**Threat:** A user with a viewer role tries to edit, delete, or share a document.

**What the code does:**

- `backend/app/permissions.py` prevents users with the `viewer` role from performing `edit`, `delete`, and `share` actions.
- The permission checker evaluates the requested action instead of relying only on whether the user is signed in.
- Permission decisions are sent to the audit logging function.
- `backend/tests/test_view_only_download.py` checks that an encrypted file is not read when a download permission check denies access.

## 6. Continued Access After Permission Revocation

**Threat:** A recipient tries to access a shared document after the owner has revoked the recipient's permission.

**What the code does:**

- `backend/app/permissions.py` retrieves the current `DocumentGrant` and evaluates its permissions when checking access.
- The document routes provide operations to grant and revoke permissions.
- `backend/tests/test_permission_revocation.py` tests removal of a grant and checks that subsequent permission checks and document requests are denied.

**Limitation:** Revoking access cannot retrieve a copy that a recipient has already downloaded. It also cannot recall data already delivered to the recipient.

## 7. Unauthorized Administrative Access

**Threat:** An ordinary user attempts to call endpoints intended for administrators.

**What the code does:**

- `backend/app/admin.py` defines a `require_admin()` dependency.
- This dependency checks that the authenticated user's role is `ADMIN`.
- Administrative routes use this dependency to protect operations involving user management, document metadata, audit logs, and the dashboard assistant.
- `backend/tests/test_admin.py` includes tests that non-admin users cannot perform selected administrative operations or verify audit logs.

The administrator's ability to view document metadata is separate from permission to read private document contents. The deployment should define its intended administrator metadata-access policy clearly.

## 8. Path Traversal and Unsafe Storage Keys

**Threat:** An attacker supplies a filename or storage key intended to make the application access files outside its storage directory.

**What the code does:**

- `backend/app/documents.py` reduces the uploaded filename to its basename.
- The application generates a UUID-based encrypted storage filename rather than using the uploaded filename as the disk path.
- `backend/app/storage.py` validates storage keys against a UUID-style filename pattern.
- The storage functions resolve paths and check that the resulting file remains directly inside the configured storage root.
- `backend/tests/test_storage.py` tests rejection of traversal keys such as `../secret.enc` when saving, reading, or deleting files.

The storage root configured in the code is `C:\TrustVaultPrivateStorage`. The host must ensure that this directory is not publicly exposed and that its filesystem permissions are appropriate.

## 9. Direct Access to Stored Files

**Threat:** Someone attempts to retrieve a stored file without going through an authenticated application endpoint.

**What the code does:**

- `backend/app/storage.py` saves encrypted files in a server-side directory rather than the frontend's public directory.
- The storage module does not define a public static-file endpoint for that directory.
- Document routes read stored content through backend storage functions.

The source code alone does not establish the actual operating-system permissions, reverse-proxy configuration, backup access, or whether a separate deployment component exposes the storage directory.

## 10. Exposure or Tampering of Stored Document Contents

**Threat:** An attacker obtains encrypted file data or modifies ciphertext so that the application attempts to use altered content.

**What the code does:**

- `backend/app/encryption.py` uses AES-256-GCM to encrypt document contents.
- Each file receives a separately generated encryption key.
- The per-file key is wrapped using a master encryption key.
- Decryption verifies the authenticated-encryption tag and raises an `EncryptionError` if the ciphertext or wrapped key is invalid.
- `backend/tests/test_encryption.py` contains tests for encrypting and decrypting content, detecting modified ciphertext, and rejecting an incorrect wrapped key.

The master encryption key must be kept secret. The reviewed files do not establish a complete production key-rotation or key-recovery procedure.

## 11. Misleading File Extensions and Oversized Uploads

**Threat:** A user uploads a file whose contents do not match its extension or uploads an excessively large file.

**What the code does:**

- `backend/app/documents.py` defines an allowlist of supported file extensions.
- The upload validation function checks detected MIME types and file signatures for supported formats.
- DOCX and XLSX files are checked as ZIP archives for expected internal members.
- Uploads are read in chunks and rejected when their size exceeds 10 MiB.
- Invalid and oversized uploads generate denied audit events.

These checks validate certain file properties. They are not equivalent to antivirus scanning and do not prove that accepted files are harmless.

## 12. Modification of Audit Events

**Threat:** Someone modifies an audit event or changes its connection to earlier events to hide evidence of an action.

**What the code does:**

- `backend/app/audit.py` calculates SHA-256 hashes for audit events.
- Each event includes a reference to the previous event's hash.
- The verification functions recalculate the hashes and check the links between events.
- `backend/tests/test_audit_chain.py` tests detection of an incorrect event hash and a broken previous-hash link.
- The `/admin/audit/verify` endpoint exposes audit-chain verification through the administrator-protected router.

**Limitation:** The hash chain is stored in the same database as the audit events. An attacker with sufficient database privileges could potentially rewrite the entire chain and recalculate the hashes. The reviewed code does not establish an external immutable audit archive.

## 13. Unauthorized Document Actions Missing from the Audit Log

**Threat:** Access-control decisions are made without recording whether the action was allowed or denied.

**What the code does:**

- `backend/app/permissions.py` sends permission decisions to `log_audit_event()`.
- These events include the action, result, reason, actor, document, and request IP address when supplied.
- Document routes also log selected denied operations, including unauthorized permission-management attempts and invalid or oversized uploads.
- `backend/app/audit.py` persists audit events in the database.

Audit logging depends on successful database operations. The reviewed files do not establish external alerting or log forwarding.

## 14. Unauthorized Reading of Audit Logs

**Threat:** An ordinary user attempts to read administrative audit information.

**What the code does:**

- Administrative audit routes in `backend/app/admin.py` use the `require_admin` dependency.
- The audit endpoints can return event details such as actor IDs, document IDs, IP addresses, reasons, and event data.
- `backend/tests/test_admin.py` contains a test that a viewer cannot verify the audit chain.

## 15. Accidental Inclusion of Sensitive Files in Git

**Threat:** Local credentials, database files, virtual environments, or generated files are accidentally included in the public repository.

**What the code does:**

The root `.gitignore` excludes several categories of files, including:

- `.env` and `.env.*`, while allowing `.env.example`
- Python virtual environments and bytecode
- Frontend `node_modules` and build output
- Storage directories
- Database dumps and local database files
- IDE and operating-system metadata

A `.gitignore` file does not remove files that have already been committed. It also does not remove credentials from Git history. The full Git history was not audited as part of this review.

## 16. Browser Origins and Document Preview

**Threat:** A website from an unapproved browser origin attempts to interact with the API, or the application previews an unsupported file format.

**What the code does:**

- `backend/app/main.py` configures CORS for the local frontend origins `http://localhost:5173` and `http://127.0.0.1:5173`.
- `backend/app/documents.py` restricts in-app preview to PDF, PNG, JPEG, and TXT content types.
- Other accepted upload types are not included in the preview allowlist.

CORS is not a replacement for authentication, authorization, or CSRF defenses. The reviewed files do not establish a complete CSRF strategy or production browser security-header configuration.

## 17. Unsafe Use of the Administrative AI Assistant

**Threat:** A user attempts to access the administrative assistant without the required role or tries to use it to perform unauthorized administrative changes.

**What the code does:**

- The `/admin/assistant` route in `backend/app/admin.py` is protected by `require_admin`.
- The handler calculates dashboard counts using database queries and includes a limited set of recent audit events in the data sent to the configured Ollama endpoint.
- The question is validated as a string with a configured length range.
- The handler returns a text answer and does not expose a tool-call interface for database mutations.

The prompt's instructions to avoid invented claims are not a security boundary. The endpoint uses `OLLAMA_URL` when configured and otherwise defaults to `http://127.0.0.1:11434/api/generate`; the source therefore does not guarantee that every deployment sends prompts only to a local service.

---

## Limitations and Accepted Risks

1. **Previously downloaded files:** A recipient may retain a downloaded copy after access is revoked.
2. **Data already delivered:** Revocation cannot recall content that has already been transmitted.
3. **Master encryption key:** Losing the key can make encrypted documents unrecoverable; exposing it may compromise confidentiality.
4. **Audit-chain storage:** The hash chain detects many event changes but does not prevent a privileged attacker from rewriting the entire database-resident chain.
5. **Storage deployment:** Filesystem permissions and web-server exposure must be configured and checked on the actual host.
6. **Upload scanning:** File validation does not provide malware scanning.
7. **Login rate limiting:** A dedicated login rate-limit implementation was not visible in the reviewed authentication source.
8. **Deployment security:** The source review does not prove that production TLS, proxy rules, database access, Redis access, backups, and host permissions are secure.
9. **Testing scope:** Some tests use mock objects or mocked permission checks. This document does not claim that the complete test suite was run or that production behavior has been verified.

## Source Files Reviewed

- `backend/app/auth.py`
- `backend/app/security.py`
- `backend/app/dependencies.py`
- `backend/app/redis_client.py`
- `backend/app/permissions.py`
- `backend/app/documents.py`
- `backend/app/storage.py`
- `backend/app/encryption.py`
- `backend/app/audit.py`
- `backend/app/admin.py`
- `backend/app/main.py`
- Root `.gitignore`

Relevant tests include:

- `backend/tests/test_cross_owner_isolation.py`
- `backend/tests/test_permission_revocation.py`
- `backend/tests/test_disabled_session.py`
- `backend/tests/test_storage.py`
- `backend/tests/test_encryption.py`
- `backend/tests/test_audit_chain.py`
- `backend/tests/test_view_only_download.py`
- `backend/tests/test_admin.py`

