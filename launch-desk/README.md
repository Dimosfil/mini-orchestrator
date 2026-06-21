# Dental CRM (production-ready MVP)

`launch-desk` now hosts a dedicated V1 dental clinic CRM with:
- role-based web auth;
- patient and appointment domain;
- treatment plans and clinical notes;
- invoices and payments;
- tasks/reminders;
- queue/worker with retry and failed-job history;
- SQLite persistence, migrations, observability, and deployment docs.

The project remains a TypeScript monorepo style workspace:
- `backend/` Express API and DB schema/migrations;
- `frontend/` React app with role-aware shell;
- root scripts for local orchestration.

## Stack

- Backend: Node.js + Express + Zod
- DB: SQLite (file database at `data/dental-crm.sqlite`)
- Frontend: React + Vite
- Worker: internal background scheduler (`runWorkerOnce`)
- Auth: custom signed token + PBKDF2 password hashing
- UI states: loading/error/empty handled in core screens

## Quick start

```bash
cd launch-desk
copy .env.example .env
# set required values:
# JWT_SECRET, SEED_ADMIN_PASSWORD
npm run install:all
npm run db:migrate
npm run db:seed
npm run dev
```

Services:
- backend: `http://localhost:4000`
- frontend: `http://localhost:5173`

## Environment

| variable | meaning |
| --- | --- |
| `JWT_SECRET` | signing key for session tokens |
| `SEED_ADMIN_PASSWORD` | password for bootstrap admin |
| `DATABASE_PATH` | DB file path |
| `PORT` | backend listen port |
| `CORS_ORIGIN` | allowed browser origin |
| `AUTH_RATE_LIMIT_MAX_ATTEMPTS` | login throttling limit |
| `WORKER_ENABLED` | true/false for background loop in backend |
| `WORKER_POLL_INTERVAL_MS` | queue polling interval |

## Development scripts

- `npm run dev` — starts backend and frontend together
- `npm run dev:backend` — backend only
- `npm run dev:frontend` — frontend only
- `npm run db:migrate` — run SQL migrations
- `npm run db:seed` — seed default clinic/admin/demo fixtures
- `npm run build:backend` — TypeScript build check
- `npm run build:frontend` — Vite build check
- `npm run worker` — start queue worker process

## API overview

Base path: `/api`

- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/dashboard`
- `GET /api/patients`
- `POST /api/patients`
- `PATCH /api/patients/:id`
- `DELETE /api/patients/:id`
- `GET /api/appointments`
- `POST /api/appointments`
- `PATCH /api/appointments/:id`
- `GET /api/treatment-plans`
- `POST /api/treatment-plans`
- `POST /api/treatment-plans/:id/items`
- `GET /api/patients/:id/clinical-notes`
- `POST /api/patients/:id/clinical-notes`
- `GET /api/invoices`
- `POST /api/invoices`
- `POST /api/invoices/:id/payments`
- `GET /api/tasks`
- `POST /api/tasks`
- `PATCH /api/tasks/:id/complete`
- `GET /api/users`
- `POST /api/users`
- `GET /api/jobs`
- `POST /api/jobs/run`
- `GET /api/health`

Error envelope:

```json
{ "error": { "code": "BAD_REQUEST", "message": "Validation failed", "details": {} } }
```

## RBAC roles

- `owner`, `admin`: full access
- `dentist`: patients, appointments, treatment plans, notes
- `assistant`: appointments + limited patient/tasks views
- `receptionist`: scheduling and patient registry, invoices read/write
- `billing`: invoices and payments
- `viewer`: read-only operational visibility

## Data model

Main entities:
- clinics
- users (role-based)
- patients + patient_contacts
- appointments + appointment_status_history
- providers, services
- treatment_plans + treatment_plan_items
- clinical_notes
- invoices + invoice_items + payments
- tasks
- reminders
- files, audit_logs
- background_jobs + schema_migrations

## Queue + worker

Supported job types:
- `appointment_reminder`
- `invoice_overdue_reminder`
- `daily_appointment_digest`
- `audit_retention_cleanup`

Each job includes:
- retry attempts
- max attempts
- next attempt schedule
- last error

## Observability

- request IDs via `x-request-id` middleware
- audit trail for sensitive writes
- `/api/health` returns:
  - migration count
  - pending job count
  - DB path

## Release checklist

- [ ] Env variables configured (`JWT_SECRET`, `SEED_ADMIN_PASSWORD`)
- [ ] `npm run db:migrate` completed
- [ ] `npm run db:seed` completed
- [ ] Manual smoke:
  - login as `SEED_ADMIN_EMAIL`
  - create patient
  - create appointment
  - create treatment plan
  - create invoice/payment
- [ ] Worker started and processes at least one queue row
- [ ] Health endpoint returns pending queue count

## Known limitations

- SMS/email provider is queued as adapter-ready stubs and logs output now
- No external FHIR/insurance integration
- No HIPAA/GDPR legal controls built-in; treat as production scaffold needing compliance hardening for jurisdiction
