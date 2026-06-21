import { Router, type NextFunction, type Response } from 'express';
import type { SQLInputValue } from 'node:sqlite';
import { z } from 'zod';
import { getRow, runCommand, runQuery } from './db.js';
import { ApiError, badRequest, conflict, notFound } from './errors.js';
import { authenticate, createAuthPayload, type AuthenticatedRequest } from './middleware/auth.js';
import { authRateLimit } from './middleware/rateLimit.js';
import { requirePermission } from './middleware/rbac.js';
import { hashPassword, verifyPassword } from './services/security.js';
import { writeAuditLog } from './services/audit.js';
import { enqueueJob, listJobs, runWorkerOnce } from './services/queue.js';
const router = Router();

const toInt = (value: string | undefined, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

const parsePagination = (query: Record<string, string | undefined>) => {
  return {
    page: toInt(query.page, 1),
    pageSize: Math.min(100, toInt(query.pageSize, 25)),
    search: (query.q ?? '').trim(),
  };
};

const sanitizeUser = (user: { id: number; email: string; full_name: string; role: string; clinic_id: number; last_login_at?: string | null }) => ({
  id: user.id,
  email: user.email,
  fullName: user.full_name,
  role: user.role,
  clinicId: user.clinic_id,
  lastLoginAt: user.last_login_at ?? null,
});

const allowedRoles = ['owner', 'admin', 'dentist', 'assistant', 'receptionist', 'billing', 'viewer'];

router.post('/auth/login', authRateLimit, (req, res, next) => {
  const schema = z.object({ email: z.string().email(), password: z.string().min(8) });
  const parse = schema.safeParse(req.body);
  if (!parse.success) {
    next(badRequest('Invalid credentials payload', parse.error.flatten()));
    return;
  }

  const data = parse.data;
  const user = getRow<{ id: number; email: string; full_name: string; password_hash: string; role: string; clinic_id: number; is_active: number; deleted_at?: string | null }>(
    `SELECT id, email, full_name, password_hash, role, clinic_id, is_active, deleted_at
       FROM users
      WHERE email = ?`,
    [data.email.trim().toLowerCase()],
  );
  if (!user || user.deleted_at || !user.is_active) {
    next(badRequest('Invalid credentials'));
    return;
  }
  if (!verifyPassword(data.password, user.password_hash)) {
    next(badRequest('Invalid credentials'));
    return;
  }

  const tokenPayload = createAuthPayload({
    sub: user.id,
    email: user.email,
    fullName: user.full_name,
    role: user.role,
    clinicId: user.clinic_id,
  });
  runCommand(`UPDATE users SET last_login_at = datetime('now'), updated_at = datetime('now') WHERE id = ?`, [user.id]);
  writeAuditLog(user.id, user.clinic_id, 'auth.login', 'user', user.id, { ip: req.ip });
  res.json({
    token: tokenPayload.token,
    expiresAt: tokenPayload.expiresAt,
    user: sanitizeUser({
      id: user.id,
      email: user.email,
      full_name: user.full_name,
      role: user.role,
      clinic_id: user.clinic_id,
    }),
  });
});

router.get('/auth/me', authenticate, (req: AuthenticatedRequest, res) => {
  if (!req.user) {
    throw badRequest('Missing auth context');
  }
  res.json({ user: req.user });
});

router.get('/users', authenticate, requirePermission('users:read'), (_req, res) => {
  const req = _req as AuthenticatedRequest;
  const { page, pageSize, search } = parsePagination(req.query as Record<string, string | undefined>);
  const offset = (page - 1) * pageSize;
  const baseClause = `clinic_id = ?`;
  const params: (string | number)[] = [req.user?.clinicId ?? 0];
  if (search) {
    params.push(`%${search}%`);
  }
  const where = search
    ? `${baseClause} AND (email LIKE ? OR full_name LIKE ?)`
    : baseClause;
  const finalParams = search
    ? [params[0], params[1], params[1]]
    : params;
  const total = getRow<{ total: number }>(`SELECT COUNT(*) AS total FROM users WHERE ${where}`, finalParams);
  const rows = runQuery<{ id: number; email: string; full_name: string; role: string; clinic_id: number; is_active: number; last_login_at: string | null }>(
    `SELECT id, email, full_name, role, clinic_id, is_active, last_login_at
       FROM users
      WHERE ${where}
      ORDER BY id DESC
      LIMIT ? OFFSET ?`,
    [...finalParams, pageSize, offset],
  );
  res.json({ items: rows.map((user) => sanitizeUser(user as never)), total: total?.total ?? 0, page, pageSize });
});

router.post('/users', authenticate, requirePermission('users:write'), (req: AuthenticatedRequest, res, next) => {
  const schema = z.object({
    email: z.string().email(),
    fullName: z.string().min(2),
    password: z.string().min(8),
    role: z.string().refine((value) => allowedRoles.includes(value)),
    phone: z.string().optional(),
  });
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    next(badRequest('Invalid user payload', parsed.error.flatten()));
    return;
  }
  const existing = getRow<{ id: number }>('SELECT id FROM users WHERE email = ?', [parsed.data.email.toLowerCase()]);
  if (existing) {
    next(conflict('Email already used'));
    return;
  }
  const result = runCommand(
    `INSERT INTO users (clinic_id, email, full_name, password_hash, role, phone, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, datetime('now'))`,
    [req.user!.clinicId, parsed.data.email.toLowerCase(), parsed.data.fullName, hashPassword(parsed.data.password), parsed.data.role, parsed.data.phone ?? null],
  );
  const created = getRow<{ id: number; email: string; full_name: string; role: string; clinic_id: number; is_active: number; last_login_at: string | null }>(
    `SELECT id, email, full_name, role, clinic_id, is_active, last_login_at FROM users WHERE id = ?`,
    [Number(result.lastInsertRowid)],
  );
  if (!created) {
    next(badRequest('Unable to create user'));
    return;
  }
  writeAuditLog(req.user!.id, req.user!.clinicId, 'user.created', 'user', Number(result.lastInsertRowid), {
    createdUser: parsed.data.email,
  });
  res.status(201).json({ item: sanitizeUser(created as never) });
});

router.get('/users/:id', authenticate, requirePermission('users:read'), (req: AuthenticatedRequest, res, next) => {
  const parsed = z.coerce.number().int().safeParse(req.params.id);
  if (!parsed.success) {
    next(badRequest('Invalid user id'));
    return;
  }
  const user = getRow<{ id: number; email: string; full_name: string; role: string; clinic_id: number; is_active: number; last_login_at: string | null }>(
    `SELECT id, email, full_name, role, clinic_id, is_active, last_login_at
       FROM users
      WHERE id = ? AND clinic_id = ?`,
    [parsed.data, req.user!.clinicId],
  );
  if (!user) {
    next(notFound('User not found'));
    return;
  }
  res.json({ item: sanitizeUser(user as never) });
});

router.get('/patients', authenticate, requirePermission('patients:read'), (req: AuthenticatedRequest, res) => {
  const { page, pageSize, search } = parsePagination(req.query as Record<string, string | undefined>);
  const offset = (page - 1) * pageSize;
  const params = search
    ? [req.user!.clinicId, `%${search}%`, `%${search}%`, `%${search}%`, pageSize, offset]
    : [req.user!.clinicId, pageSize, offset];
  const total = getRow<{ total: number }>(
    `SELECT COUNT(*) AS total FROM patients p WHERE p.clinic_id = ? ${search ? 'AND (p.full_name LIKE ? OR p.phone LIKE ? OR p.email LIKE ?)' : ''}`,
    params.slice(0, search ? 4 : 1),
  );
  const items = runQuery<{ id: number; full_name: string; phone: string | null; email: string | null; deleted_at: string | null; date_of_birth: string | null }>(
    `SELECT id, full_name, phone, email, date_of_birth, deleted_at
       FROM patients p
      WHERE p.clinic_id = ? ${search ? 'AND (p.full_name LIKE ? OR p.phone LIKE ? OR p.email LIKE ?)' : ''}
      ORDER BY p.created_at DESC
      LIMIT ? OFFSET ?`,
    params,
  );
  res.json({ items, total: total?.total ?? 0, page, pageSize });
});

router.post('/patients', authenticate, requirePermission('patients:write'), (req: AuthenticatedRequest, res, next) => {
  const schema = z.object({
    fullName: z.string().min(2),
    dateOfBirth: z.string().optional(),
    phone: z.string().optional(),
    email: z.string().email().optional(),
    medicalCardNumber: z.string().optional(),
    gender: z.string().optional(),
    notes: z.string().optional(),
  });
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    next(badRequest('Invalid patient payload', parsed.error.flatten()));
    return;
  }
  const result = runCommand(
    `INSERT INTO patients (
      clinic_id, full_name, date_of_birth, phone, email, medical_card_number, gender, notes, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))`,
    [
      req.user!.clinicId,
      parsed.data.fullName,
      parsed.data.dateOfBirth ?? null,
      parsed.data.phone ?? null,
      parsed.data.email ?? null,
      parsed.data.medicalCardNumber ?? null,
      parsed.data.gender ?? null,
      parsed.data.notes ?? null,
    ],
  );
  writeAuditLog(req.user!.id, req.user!.clinicId, 'patient.created', 'patient', Number(result.lastInsertRowid), {
    fullName: parsed.data.fullName,
  });
  res.status(201).json({
    item: {
      id: Number(result.lastInsertRowid),
      ...parsed.data,
      clinicId: req.user!.clinicId,
    },
  });
});

router.patch('/patients/:id', authenticate, requirePermission('patients:write'), (req: AuthenticatedRequest, res, next) => {
  const parsedId = z.coerce.number().int().safeParse(req.params.id);
  if (!parsedId.success) {
    next(badRequest('Invalid patient id'));
    return;
  }
  const schema = z.object({
    fullName: z.string().min(2).optional(),
    dateOfBirth: z.string().optional(),
    phone: z.string().optional(),
    email: z.string().email().optional(),
    medicalCardNumber: z.string().optional(),
    gender: z.string().optional(),
    notes: z.string().optional(),
  });
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    next(badRequest('Invalid patient update', parsed.error.flatten()));
    return;
  }
  const current = getRow<{ id: number }>(`SELECT id FROM patients WHERE id = ? AND clinic_id = ?`, [parsedId.data, req.user!.clinicId]);
  if (!current) {
    next(notFound('Patient not found'));
    return;
  }
  const sets = Object.entries(parsed.data).filter(([, value]) => value !== undefined);
  if (!sets.length) {
    res.json({ item: current });
    return;
  }
  const setSql = sets.map(([key]) => `${key === 'fullName' ? 'full_name' : key === 'medicalCardNumber' ? 'medical_card_number' : key} = ?`).join(', ');
  const vals = sets.map(([, value]) => value ?? null);
  runCommand(
    `UPDATE patients
        SET ${setSql}, updated_at = datetime('now')
      WHERE id = ? AND clinic_id = ?`,
    [...vals, parsedId.data, req.user!.clinicId],
  );
  writeAuditLog(req.user!.id, req.user!.clinicId, 'patient.updated', 'patient', parsedId.data, { fields: sets.map(([key]) => key) });
  const updated = getRow<{ id: number; full_name: string; phone: string | null; email: string | null }>(
    `SELECT id, full_name, phone, email FROM patients WHERE id = ?`,
    [parsedId.data],
  );
  res.json({ item: updated });
});

router.delete('/patients/:id', authenticate, requirePermission('patients:write'), (req: AuthenticatedRequest, res, next) => {
  const parsedId = z.coerce.number().int().safeParse(req.params.id);
  if (!parsedId.success) {
    next(badRequest('Invalid patient id'));
    return;
  }
  const result = runCommand(
    `UPDATE patients
        SET deleted_at = datetime('now'), updated_at = datetime('now')
      WHERE id = ? AND clinic_id = ? AND deleted_at IS NULL`,
    [parsedId.data, req.user!.clinicId],
  );
  if (result.changes === 0) {
    next(notFound('Patient not found'));
    return;
  }
  writeAuditLog(req.user!.id, req.user!.clinicId, 'patient.deleted', 'patient', parsedId.data, {});
  res.status(204).send();
});

router.get('/appointments', authenticate, requirePermission('appointments:read'), (req: AuthenticatedRequest, res) => {
  const { page, pageSize } = parsePagination(req.query as Record<string, string | undefined>);
  const offset = (page - 1) * pageSize;
  const from = req.query.from as string | undefined;
  const to = req.query.to as string | undefined;
  const patientId = req.query.patientId as string | undefined;
  const whereParts = ['a.clinic_id = ?'];
  const params: SQLInputValue[] = [req.user!.clinicId];
  if (from) {
    whereParts.push('a.starts_at >= ?');
    params.push(from);
  }
  if (to) {
    whereParts.push('a.starts_at <= ?');
    params.push(to);
  }
  if (patientId) {
    const pId = z.coerce.number().int().safeParse(patientId);
    if (pId.success) {
      whereParts.push('a.patient_id = ?');
      params.push(pId.data);
    }
  }
  params.push(pageSize, offset);
  const where = whereParts.join(' AND ');
  const total = getRow<{ total: number }>(
    `SELECT COUNT(*) AS total
       FROM appointments a
      WHERE ${where}`,
    params.slice(0, -2),
  );
  const rows = runQuery<{
    id: number;
    patient_id: number;
    provider_id: number | null;
    starts_at: string;
    ends_at: string;
    status: string;
    reason: string | null;
  }>(
    `SELECT a.id, a.patient_id, a.provider_id, a.starts_at, a.ends_at, a.status, a.reason, p.full_name AS patientName
       FROM appointments a
       JOIN patients p ON p.id = a.patient_id
      WHERE ${where}
      ORDER BY a.starts_at DESC
      LIMIT ? OFFSET ?`,
    params,
  );
  res.json({ items: rows, total: total?.total ?? 0, page, pageSize });
});

router.post('/appointments', authenticate, requirePermission('appointments:write'), (req: AuthenticatedRequest, res, next) => {
  const schema = z.object({
    patientId: z.number().int(),
    providerId: z.number().int().optional(),
    serviceId: z.number().int().optional(),
    startsAt: z.string(),
    endsAt: z.string(),
    reason: z.string().optional(),
  });
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    next(badRequest('Invalid appointment payload', parsed.error.flatten()));
    return;
  }
  if (new Date(parsed.data.startsAt) >= new Date(parsed.data.endsAt)) {
    next(badRequest('startsAt must be before endsAt'));
    return;
  }
  const patient = getRow<{ id: number }>(
    `SELECT id FROM patients WHERE id = ? AND clinic_id = ? AND deleted_at IS NULL`,
    [parsed.data.patientId, req.user!.clinicId],
  );
  if (!patient) {
    next(notFound('Patient not found'));
    return;
  }
  if (parsed.data.providerId) {
    const busy = getRow<{ id: number }>(
      `SELECT id FROM appointments
         WHERE clinic_id = ? AND provider_id = ? AND deleted_at IS NULL AND status != 'cancelled'
           AND ((starts_at < ? AND ends_at > ?) OR (starts_at < ? AND ends_at > ?) OR (starts_at >= ? AND ends_at <= ?))
         LIMIT 1`,
      [
        req.user!.clinicId,
        parsed.data.providerId,
        parsed.data.endsAt,
        parsed.data.startsAt,
        parsed.data.endsAt,
        parsed.data.startsAt,
        parsed.data.endsAt,
        parsed.data.startsAt,
      ],
    );
    if (busy) {
      next(conflict('Provider has overlapping appointment'));
      return;
    }
  }
  const result = runCommand(
    `INSERT INTO appointments (
      clinic_id, patient_id, provider_id, service_id, starts_at, ends_at, reason, created_by_user_id, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))`,
    [
      req.user!.clinicId,
      parsed.data.patientId,
      parsed.data.providerId ?? null,
      parsed.data.serviceId ?? null,
      parsed.data.startsAt,
      parsed.data.endsAt,
      parsed.data.reason ?? null,
      req.user!.id,
    ],
  );
  const appointmentId = Number(result.lastInsertRowid);
  runCommand(
    `INSERT INTO appointment_status_history (
      appointment_id, status, changed_by_user_id, changed_at, note
    ) VALUES (?, 'scheduled', ?, datetime('now'), 'created')`,
    [appointmentId, req.user!.id],
  );
  const reminderAt = new Date(new Date(parsed.data.startsAt).getTime() - 24 * 60 * 60 * 1000).toISOString();
  const now = Date.now();
  const reminderPayload = {
    patientId: parsed.data.patientId,
    appointmentId,
    patientName: 'Patient',
  };
  enqueueJob(req.user!.clinicId, 'appointment_reminder', reminderPayload, { delayMs: Math.max(0, new Date(reminderAt).getTime() - now), maxAttempts: 3 });
  writeAuditLog(req.user!.id, req.user!.clinicId, 'appointment.created', 'appointment', appointmentId, {
    patientId: parsed.data.patientId,
  });
  res.status(201).json({ id: appointmentId });
});

router.patch('/appointments/:id', authenticate, requirePermission('appointments:write'), (req: AuthenticatedRequest, res, next) => {
  const id = z.coerce.number().int().safeParse(req.params.id);
  if (!id.success) {
    next(badRequest('Invalid appointment id'));
    return;
  }
  const schema = z.object({ status: z.enum(['scheduled', 'confirmed', 'completed', 'cancelled']).optional(), reason: z.string().optional() });
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    next(badRequest('Invalid appointment patch', parsed.error.flatten()));
    return;
  }
  const current = getRow<{ id: number; status: string }>(
    `SELECT id, status FROM appointments WHERE id = ? AND clinic_id = ? AND deleted_at IS NULL`,
    [id.data, req.user!.clinicId],
  );
  if (!current) {
    next(notFound('Appointment not found'));
    return;
  }
  const fields: string[] = [];
  const values: SQLInputValue[] = [];
  if (parsed.data.status) {
    fields.push('status = ?');
    values.push(parsed.data.status);
  }
  if (parsed.data.reason !== undefined) {
    fields.push('reason = ?');
    values.push(parsed.data.reason);
  }
  if (!fields.length) {
    res.json({ status: current.status, id: id.data });
    return;
  }
  runCommand(`UPDATE appointments SET ${fields.join(', ')}, updated_at = datetime('now') WHERE id = ? AND clinic_id = ?`, [...values, id.data, req.user!.clinicId]);
  if (parsed.data.status && parsed.data.status !== current.status) {
    runCommand(
      `INSERT INTO appointment_status_history (appointment_id, status, changed_by_user_id, changed_at, note)
       VALUES (?, ?, ?, datetime('now'), ?)`,
      [id.data, parsed.data.status, req.user!.id, parsed.data.reason ?? `status -> ${parsed.data.status}`],
    );
  }
  writeAuditLog(req.user!.id, req.user!.clinicId, 'appointment.updated', 'appointment', id.data, parsed.data);
  res.json({ id: id.data });
});

router.get('/treatment-plans', authenticate, requirePermission('treatment-plans:read'), (req: AuthenticatedRequest, res) => {
  const { page, pageSize, search } = parsePagination(req.query as Record<string, string | undefined>);
  const offset = (page - 1) * pageSize;
  const params = search
    ? [req.user!.clinicId, `%${search}%`, pageSize, offset]
    : [req.user!.clinicId, pageSize, offset];
  const total = getRow<{ total: number }>(
    `SELECT COUNT(*) AS total
       FROM treatment_plans t
      WHERE t.clinic_id = ? ${search ? 'AND t.title LIKE ?' : ''}`,
    params.slice(0, search ? 2 : 1),
  );
  const rows = runQuery<{ id: number; title: string; status: string; target_finish_at: string | null; total_cost: number }>(
    `SELECT t.id, t.title, t.status, t.target_finish_at, t.total_cost, p.full_name AS patientName
       FROM treatment_plans t
       JOIN patients p ON p.id = t.patient_id
      WHERE t.clinic_id = ? ${search ? 'AND t.title LIKE ?' : ''}
      ORDER BY t.created_at DESC
      LIMIT ? OFFSET ?`,
    params,
  );
  res.json({ items: rows, total: total?.total ?? 0, page, pageSize });
});

router.post('/treatment-plans', authenticate, requirePermission('treatment-plans:write'), (req: AuthenticatedRequest, res, next) => {
  const schema = z.object({
    patientId: z.number().int(),
    title: z.string().min(3),
    status: z.enum(['draft', 'active', 'completed']).default('draft'),
    targetFinishAt: z.string().optional(),
    notes: z.string().optional(),
  });
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    next(badRequest('Invalid treatment plan payload', parsed.error.flatten()));
    return;
  }
  const patient = getRow<{ id: number }>(
    `SELECT id FROM patients WHERE id = ? AND clinic_id = ? AND deleted_at IS NULL`,
    [parsed.data.patientId, req.user!.clinicId],
  );
  if (!patient) {
    next(notFound('Patient not found'));
    return;
  }
  const plan = runCommand(
    `INSERT INTO treatment_plans (
      clinic_id, patient_id, dentist_id, title, status, target_finish_at, notes, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))`,
    [
      req.user!.clinicId,
      parsed.data.patientId,
      req.user!.id,
      parsed.data.title,
      parsed.data.status,
      parsed.data.targetFinishAt ?? null,
      parsed.data.notes ?? null,
    ],
  );
  writeAuditLog(req.user!.id, req.user!.clinicId, 'treatment-plan.created', 'treatment_plan', Number(plan.lastInsertRowid), { status: parsed.data.status });
  res.status(201).json({ id: Number(plan.lastInsertRowid) });
});

router.post('/treatment-plans/:id/items', authenticate, requirePermission('treatment-plans:write'), (req: AuthenticatedRequest, res, next) => {
  const id = z.coerce.number().int().safeParse(req.params.id);
  if (!id.success) {
    next(badRequest('Invalid treatment plan id'));
    return;
  }
  const plan = getRow<{ id: number; clinic_id: number }>(`SELECT id, clinic_id FROM treatment_plans WHERE id = ?`, [id.data]);
  if (!plan || plan.clinic_id !== req.user!.clinicId) {
    next(notFound('Treatment plan not found'));
    return;
  }
  const schema = z.object({
    serviceId: z.number().int(),
    teeth: z.string().optional(),
    quantity: z.number().int().positive().default(1),
    discountPercent: z.number().min(0).max(100).default(0),
  });
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    next(badRequest('Invalid treatment item payload', parsed.error.flatten()));
    return;
  }
  const service = getRow<{ unit_price: number; id: number }>(
    `SELECT id, unit_price FROM services WHERE id = ? AND clinic_id = ? AND is_active = 1`,
    [parsed.data.serviceId, req.user!.clinicId],
  );
  if (!service) {
    next(notFound('Service not found'));
    return;
  }
  const unitPrice = service.unit_price;
  const total = parsed.data.quantity * unitPrice * (1 - parsed.data.discountPercent / 100);
  const inserted = runCommand(
    `INSERT INTO treatment_plan_items (
      treatment_plan_id, service_id, teeth, quantity, unit_price, discount_percent, total_price, status, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'planned', datetime('now'), datetime('now'))`,
    [id.data, parsed.data.serviceId, parsed.data.teeth ?? null, parsed.data.quantity, unitPrice, parsed.data.discountPercent, total],
  );
  runCommand(
    `UPDATE treatment_plans
        SET total_cost = COALESCE((SELECT SUM(total_price) FROM treatment_plan_items WHERE treatment_plan_id = ?), 0),
            updated_at = datetime('now')
      WHERE id = ?`,
    [id.data, id.data],
  );
  writeAuditLog(req.user!.id, req.user!.clinicId, 'treatment-plan-item.created', 'treatment_plan_item', Number(inserted.lastInsertRowid), {
    treatmentPlanId: id.data,
  });
  res.status(201).json({ id: Number(inserted.lastInsertRowid) });
});

router.get('/patients/:id/clinical-notes', authenticate, requirePermission('clinical-notes:read'), (req: AuthenticatedRequest, res) => {
  const patientId = z.coerce.number().int().safeParse(req.params.id);
  if (!patientId.success) {
    throw badRequest('Invalid patient id');
  }
  const rows = runQuery<{ id: number; title: string | null; note_type: string; note: string; created_at: string }>(
    `SELECT id, title, note_type, note, created_at
       FROM clinical_notes
      WHERE clinic_id = ? AND patient_id = ?
      ORDER BY id DESC`,
    [req.user!.clinicId, patientId.data],
  );
  res.json({ items: rows });
});

router.post('/patients/:id/clinical-notes', authenticate, requirePermission('clinical-notes:write'), (req: AuthenticatedRequest, res, next) => {
  const patientId = z.coerce.number().int().safeParse(req.params.id);
  if (!patientId.success) {
    next(badRequest('Invalid patient id'));
    return;
  }
  const patient = getRow<{ id: number }>(
    `SELECT id FROM patients WHERE id = ? AND clinic_id = ?`,
    [patientId.data, req.user!.clinicId],
  );
  if (!patient) {
    next(notFound('Patient not found'));
    return;
  }
  const schema = z.object({
    treatmentPlanId: z.number().int().optional(),
    noteType: z.enum(['progress', 'xray', 'prescription', 'billing']).default('progress'),
    title: z.string().max(160).optional(),
    note: z.string().min(3),
    isConfidential: z.boolean().default(true),
  });
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    next(badRequest('Invalid clinical note payload', parsed.error.flatten()));
    return;
  }
  const planId = parsed.data.treatmentPlanId;
  if (planId) {
    const plan = getRow<{ id: number }>(
      `SELECT id FROM treatment_plans WHERE id = ? AND patient_id = ?`,
      [planId, patientId.data],
    );
    if (!plan) {
      next(notFound('Treatment plan not found'));
      return;
    }
  }
  const inserted = runCommand(
    `INSERT INTO clinical_notes (
      clinic_id, patient_id, treatment_plan_id, author_user_id, note_type, title, note, is_confidential, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))`,
    [
      req.user!.clinicId,
      patientId.data,
      planId ?? null,
      req.user!.id,
      parsed.data.noteType,
      parsed.data.title ?? null,
      parsed.data.note,
      parsed.data.isConfidential ? 1 : 0,
    ],
  );
  writeAuditLog(req.user!.id, req.user!.clinicId, 'clinical-note.created', 'clinical_note', Number(inserted.lastInsertRowid), {
    patientId: patientId.data,
  });
  res.status(201).json({ id: Number(inserted.lastInsertRowid) });
});

router.get('/invoices', authenticate, requirePermission('invoices:read'), (req: AuthenticatedRequest, res) => {
  const { page, pageSize, search } = parsePagination(req.query as Record<string, string | undefined>);
  const offset = (page - 1) * pageSize;
  const where = search
    ? `WHERE i.clinic_id = ? AND (p.full_name LIKE ? OR i.status LIKE ?)`
    : `WHERE i.clinic_id = ?`;
  const params = search ? [req.user!.clinicId, `%${search}%`, `%${search}%`, pageSize, offset] : [req.user!.clinicId, pageSize, offset];
  const total = getRow<{ total: number }>(
    `SELECT COUNT(*) AS total
       FROM invoices i
       JOIN patients p ON p.id = i.patient_id
      ${where}`,
    params.slice(0, search ? 3 : 1),
  );
  const rows = runQuery<{ id: number; status: string; total: number; currency: string; due_date: string; patientName: string }>(
    `SELECT i.id, i.status, i.total, i.currency, i.due_date, p.full_name AS patientName
       FROM invoices i
       JOIN patients p ON p.id = i.patient_id
      ${where}
      ORDER BY i.created_at DESC
      LIMIT ? OFFSET ?`,
    params,
  );
  res.json({ items: rows, total: total?.total ?? 0, page, pageSize });
});

router.post('/invoices', authenticate, requirePermission('invoices:write'), (req: AuthenticatedRequest, res, next) => {
  const schema = z.object({
    patientId: z.number().int(),
    dueDate: z.string(),
    currency: z.string().default('RUB'),
    items: z
      .array(
        z.object({
          serviceId: z.number().int(),
          description: z.string().min(2),
          quantity: z.number().int().positive().default(1),
          unitPrice: z.number().positive().default(0),
        }),
      )
      .min(1),
  });
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    next(badRequest('Invalid invoice payload', parsed.error.flatten()));
    return;
  }
  const patient = getRow<{ id: number }>(`SELECT id FROM patients WHERE id = ? AND clinic_id = ?`, [parsed.data.patientId, req.user!.clinicId]);
  if (!patient) {
    next(notFound('Patient not found'));
    return;
  }
  const lineTotals = parsed.data.items.map((item) => item.quantity * item.unitPrice);
  const subtotal = lineTotals.reduce((acc, total) => acc + total, 0);
  const total = subtotal;
  const insert = runCommand(
    `INSERT INTO invoices (
      clinic_id, patient_id, created_by_user_id, status, currency, subtotal, total, due_date, issued_at, created_at, updated_at
    ) VALUES (?, ?, ?, 'open', ?, ?, ?, ?, datetime('now'), datetime('now'), datetime('now'))`,
    [
      req.user!.clinicId,
      parsed.data.patientId,
      req.user!.id,
      parsed.data.currency,
      subtotal,
      total,
      parsed.data.dueDate,
    ],
  );
  const invoiceId = Number(insert.lastInsertRowid);
  for (const item of parsed.data.items) {
    const lineTotal = item.quantity * item.unitPrice;
    runCommand(
      `INSERT INTO invoice_items (
        invoice_id, service_id, description, quantity, unit_price, line_total, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))`,
      [invoiceId, item.serviceId, item.description, item.quantity, item.unitPrice, lineTotal],
    );
  }
  enqueueJob(req.user!.clinicId, 'invoice_overdue_reminder', { invoiceId, patientId: parsed.data.patientId }, { delayMs: 0, maxAttempts: 5 });
  writeAuditLog(req.user!.id, req.user!.clinicId, 'invoice.created', 'invoice', invoiceId, { patientId: parsed.data.patientId, total });
  res.status(201).json({ id: invoiceId });
});

router.post('/invoices/:id/payments', authenticate, requirePermission('invoices:write'), (req: AuthenticatedRequest, res, next) => {
  const id = z.coerce.number().int().safeParse(req.params.id);
  if (!id.success) {
    next(badRequest('Invalid invoice id'));
    return;
  }
  const invoice = getRow<{ id: number; total: number; paid_at: string | null }>(
    `SELECT id, total, paid_at FROM invoices WHERE id = ? AND clinic_id = ?`,
    [id.data, req.user!.clinicId],
  );
  if (!invoice) {
    next(notFound('Invoice not found'));
    return;
  }
  const schema = z.object({
    amount: z.number().positive(),
    method: z.string().min(2),
    referenceNo: z.string().optional(),
  });
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    next(badRequest('Invalid payment payload', parsed.error.flatten()));
    return;
  }
  const paidNow = runQuery<{ paid: number }>(
    `SELECT COALESCE(SUM(amount), 0) AS paid
       FROM payments
      WHERE invoice_id = ?`,
    [id.data],
  )[0]?.paid ?? 0;
  if (paidNow + parsed.data.amount > invoice.total) {
    next(conflict('Payment exceeds invoice total'));
    return;
  }
  runCommand(
    `INSERT INTO payments (invoice_id, received_by_user_id, amount, method, reference_no, paid_at, created_at)
     VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))`,
    [id.data, req.user!.id, parsed.data.amount, parsed.data.method, parsed.data.referenceNo ?? null],
  );
  const paidAfter = paidNow + parsed.data.amount;
  if (paidAfter >= invoice.total) {
    runCommand(`UPDATE invoices SET status = 'paid', paid_at = datetime('now'), updated_at = datetime('now') WHERE id = ?`, [id.data]);
  }
  writeAuditLog(req.user!.id, req.user!.clinicId, 'invoice.payment_created', 'invoice', id.data, {
    amount: parsed.data.amount,
    method: parsed.data.method,
  });
  res.status(201).json({ invoiceId: id.data, paidAfter, total: invoice.total });
});

router.get('/tasks', authenticate, requirePermission('tasks:read'), (req: AuthenticatedRequest, res) => {
  const { page, pageSize, search } = parsePagination(req.query as Record<string, string | undefined>);
  const offset = (page - 1) * pageSize;
  const where = search
    ? `WHERE t.clinic_id = ? AND t.status = 'open' AND (t.title LIKE ? OR t.description LIKE ?)`
    : `WHERE t.clinic_id = ? AND t.status = 'open'`;
  const params = search ? [req.user!.clinicId, `%${search}%`, `%${search}%`, pageSize, offset] : [req.user!.clinicId, pageSize, offset];
  const total = getRow<{ total: number }>(
    `SELECT COUNT(*) AS total FROM tasks t ${where}`,
    params.slice(0, search ? 3 : 1),
  );
  const rows = runQuery<{ id: number; title: string; description: string | null; due_at: string | null; status: string; priority: string }>(
    `SELECT id, title, description, due_at, status, priority
       FROM tasks t
      ${where}
      ORDER BY t.due_at IS NULL, t.due_at ASC, t.id DESC
      LIMIT ? OFFSET ?`,
    params,
  );
  res.json({ items: rows, total: total?.total ?? 0, page, pageSize });
});

router.post('/tasks', authenticate, requirePermission('tasks:write'), (req: AuthenticatedRequest, res, next) => {
  const schema = z.object({
    patientId: z.number().int().optional(),
    assignedToUserId: z.number().int().optional(),
    title: z.string().min(3),
    description: z.string().optional(),
    dueAt: z.string().optional(),
    priority: z.enum(['low', 'medium', 'high']).default('medium'),
  });
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    next(badRequest('Invalid task payload', parsed.error.flatten()));
    return;
  }
  const run = runCommand(
    `INSERT INTO tasks (
      clinic_id, patient_id, assigned_to_user_id, title, description, due_at, status, priority, created_by_user_id, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, datetime('now'))`,
    [
      req.user!.clinicId,
      parsed.data.patientId ?? null,
      parsed.data.assignedToUserId ?? null,
      parsed.data.title,
      parsed.data.description ?? null,
      parsed.data.dueAt ?? null,
      parsed.data.priority,
      req.user!.id,
    ],
  );
  writeAuditLog(req.user!.id, req.user!.clinicId, 'task.created', 'task', Number(run.lastInsertRowid), { title: parsed.data.title });
  res.status(201).json({ id: Number(run.lastInsertRowid) });
});

router.patch('/tasks/:id/complete', authenticate, requirePermission('tasks:write'), (req: AuthenticatedRequest, res, next) => {
  const id = z.coerce.number().int().safeParse(req.params.id);
  if (!id.success) {
    next(badRequest('Invalid task id'));
    return;
  }
  const result = runCommand(
    `UPDATE tasks
        SET status = 'done', completed_at = datetime('now')
      WHERE id = ? AND clinic_id = ?`,
    [id.data, req.user!.clinicId],
  );
  if (result.changes === 0) {
    next(notFound('Task not found'));
    return;
  }
  writeAuditLog(req.user!.id, req.user!.clinicId, 'task.completed', 'task', id.data, {});
  res.status(204).send();
});

router.get('/dashboard', authenticate, requirePermission('dashboard:read'), (req: AuthenticatedRequest, res) => {
  const today = new Date().toISOString().slice(0, 10);
  const todayAppointments = getRow<{ count: number }>(
    `SELECT COUNT(*) AS count FROM appointments WHERE clinic_id = ? AND starts_at LIKE ?`,
    [req.user!.clinicId, `${today}%`],
  );
  const pendingTasks = getRow<{ count: number }>(
    `SELECT COUNT(*) AS count FROM tasks WHERE clinic_id = ? AND status = 'open'`,
    [req.user!.clinicId],
  );
  const openInvoices = getRow<{ count: number }>(
    `SELECT COUNT(*) AS count FROM invoices WHERE clinic_id = ? AND status IN ('open', 'partial', 'overdue')`,
    [req.user!.clinicId],
  );
  const lastEvents = runQuery<{ id: number; action: string; created_at: string }>(
    `SELECT id, action, created_at
       FROM audit_logs
      WHERE clinic_id = ?
      ORDER BY id DESC
      LIMIT 12`,
    [req.user!.clinicId],
  );
  res.json({
    summary: {
      todayAppointments: todayAppointments?.count ?? 0,
      pendingTasks: pendingTasks?.count ?? 0,
      openInvoices: openInvoices?.count ?? 0,
    },
    recentAudit: lastEvents,
  });
});

router.get('/jobs', authenticate, requirePermission('billing:write'), (req: AuthenticatedRequest, res) => {
  const { page, pageSize } = parsePagination(req.query as Record<string, string | undefined>);
  const jobs = listJobs(req.user!.clinicId).slice((page - 1) * pageSize, page * pageSize);
  const total = getRow<{ count: number }>(`SELECT COUNT(*) AS count FROM background_jobs WHERE clinic_id = ?`, [req.user!.clinicId]);
  res.json({ items: jobs, page, pageSize, total: total?.count ?? 0 });
});

router.post('/jobs/run', authenticate, requirePermission('billing:write'), (_req, res) => {
  const done = runWorkerOnce();
  res.json({ processed: done });
});

const notFoundErr = (_req: AuthenticatedRequest, _res: Response, next: NextFunction) => {
  next(notFound('Route not found'));
};
router.use(notFoundErr);

export default router;
