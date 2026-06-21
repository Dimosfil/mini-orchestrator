# Dental CRM Release Checklist

- [ ] `JWT_SECRET` и `SEED_ADMIN_PASSWORD` заданы в `.env`.
- [ ] Запущены миграции: `npm run db:migrate`.
- [ ] Выполнен сид: `npm run db:seed`.
- [ ] `GET /api/health` возвращает блок миграций и pending jobs.
- [ ] Ключевые API валидация (patients, appointments, treatment-plans, invoices, users).
- [ ] Ролевой доступ ограничен по endpointам для ролей owner/admin/dentist/assistant/receptionist/billing/viewer.
- [ ] Публичная форма не возвращает `password_hash` и PII-детали в ошибках.
- [ ] Логи/аудит пишутся на `POST /api/*` с чувствательными изменениями.
- [ ] Очередь обработана хотя бы одним типом job (например, `invoice_overdue_reminder`).
- [ ] Фронтенд имеет loading/error/empty state на dashboard, patients, appointments, billing, tasks.
- [ ] Документация заполнена (README, RBAC, API, deploy, ограничение).
