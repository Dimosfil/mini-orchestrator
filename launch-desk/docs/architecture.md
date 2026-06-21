# Architecture notes (Dental CRM)

## Layers

1. API Layer (Express)
   - `auth` middleware parses bearer session token
   - `rbac` middleware enforces endpoint permissions by role
   - `zod` validates payloads
   - `global error` normalizes errors to consistent envelope

2. Data Layer (SQLite)
   - SQL migrations in `backend/migrations/*.sql`
   - `backend/scripts/migrate.ts` tracks applied migrations in `schema_migrations`
   - domain tables for clinic/patient/schedule/treatment/billing/tasks/audit

3. Queue Layer
   - table `background_jobs` stores due items
   - worker loop in `backend/src/services/queue.ts` + `backend/src/queue/worker.ts`
   - retry/backoff implemented via attempts + next_attempt_at

4. Presentation Layer
   - React shell in role-aware tabs
   - lightweight fetch wrappers in `frontend/src/api.ts`
   - dedicated screens for dashboard, patients, appointments, plans, billing, tasks, admin

## Security

- Password hashing: PBKDF2 + random salt (`hashPassword`).
- Session token: HMAC-sha256 signed payload with expiry.
- Rate-limiting: in-memory auth attempt throttling.
- Secrets read from env only; no secrets in repo.

## Observability

- request id middleware (`x-request-id`)
- audit log table for writes
- health endpoint and worker counters
