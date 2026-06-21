import { getRow, runCommand, runQuery } from '../db.js';
import { writeAuditLog } from './audit.js';
import { nowIso } from '../db.js';

const MS = {
  MINUTE: 60_000,
};

type QueuePayload = Record<string, unknown>;

const backoffForAttempt = (attempt: number) => Math.min(5 * 60, Math.pow(2, attempt)) * MS.MINUTE;

export type BackgroundJob = {
  id: number;
  clinic_id: number;
  type: string;
  payload_json: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  attempts: number;
  max_attempts: number;
  next_attempt_at: string;
  last_error: string | null;
};

export const enqueueJob = (clinicId: number, type: string, payload: QueuePayload, options?: { delayMs?: number; maxAttempts?: number }) => {
  const runAt = new Date(Date.now() + (options?.delayMs ?? 0)).toISOString();
  runCommand(
    `INSERT INTO background_jobs (
      clinic_id, type, payload_json, status, attempts, max_attempts, next_attempt_at, created_at, updated_at
    ) VALUES (?, ?, ?, 'pending', 0, ?, ?, datetime('now'), datetime('now'))`,
    [clinicId, type, JSON.stringify(payload), options?.maxAttempts ?? 3, runAt],
  );
};

export const listJobs = (clinicId: number) => {
  return runQuery<BackgroundJob>(
    `SELECT id, clinic_id, type, payload_json, status, attempts, max_attempts, next_attempt_at, last_error
       FROM background_jobs
      WHERE clinic_id = ?
      ORDER BY id DESC
      LIMIT 100`,
    [clinicId],
  );
};

const setJobFailed = (id: number, err: unknown) => {
  const next = nowIso();
  runCommand(
    `UPDATE background_jobs
        SET status='failed', last_error=?, updated_at=?
      WHERE id=?`,
    [String(err instanceof Error ? err.message : String(err)), next, id],
  );
};

const setJobDone = (id: number) => {
  runCommand(
    `UPDATE background_jobs
        SET status='done', last_error=NULL, updated_at=?
      WHERE id=?`,
    [nowIso(), id],
  );
};

const reschedule = (id: number, attempts: number, maxAttempts: number) => {
  const nextAttempt = new Date(Date.now() + backoffForAttempt(attempts)).toISOString();
  runCommand(
    `UPDATE background_jobs
        SET status='pending', attempts=?, next_attempt_at=?, updated_at=?
      WHERE id=?`,
    [attempts, nextAttempt, nowIso(), id],
  );
  if (attempts >= maxAttempts) {
    runCommand(
      `UPDATE background_jobs
          SET status='failed', updated_at=?
        WHERE id=?`,
      [nowIso(), id],
    );
  }
};

const markRunning = (id: number, attempts: number) => {
  runCommand(
    `UPDATE background_jobs
        SET status='running', attempts=?, updated_at=?
      WHERE id=?`,
    [attempts, nowIso(), id],
  );
};

const handleJob = async (job: BackgroundJob) => {
  const payload = JSON.parse(job.payload_json) as {
    patientId?: number;
    appointmentId?: number;
    invoiceId?: number;
  };
  switch (job.type) {
    case 'appointment_reminder': {
      if (!payload.patientId || !payload.appointmentId) {
        throw new Error('Missing appointment reminder payload');
      }
      break;
    }
    case 'invoice_overdue_reminder': {
      if (!payload.patientId || !payload.invoiceId) {
        throw new Error('Missing invoice reminder payload');
      }
      break;
    }
    case 'daily_appointment_digest': {
      break;
    }
    case 'audit_retention_cleanup': {
      runCommand(`DELETE FROM audit_logs WHERE created_at < datetime('now', '-365 days')`);
      break;
    }
    default:
      throw new Error(`Unknown job type: ${job.type}`);
  }
};

export const runWorkerOnce = () => {
  const now = nowIso();
  const dueJobs = runQuery<BackgroundJob>(
    `SELECT id, clinic_id, type, payload_json, status, attempts, max_attempts, next_attempt_at, last_error
       FROM background_jobs
      WHERE status IN ('pending','failed')
        AND next_attempt_at <= ?
      ORDER BY id ASC
      LIMIT 20`,
    [now],
  );

  for (const job of dueJobs) {
    const nextAttempt = job.attempts + 1;
    markRunning(job.id, nextAttempt);
    try {
      handleJob(job);
      setJobDone(job.id);
      writeAuditLog(null, job.clinic_id, 'queue.job_done', 'background_job', job.id, {
        type: job.type,
        attempts: job.attempts + 1,
      });
    } catch (error) {
      if (nextAttempt >= job.max_attempts) {
        reschedule(job.id, nextAttempt, job.max_attempts);
      } else {
        runCommand(
          `UPDATE background_jobs
              SET status='failed', attempts=?, last_error=?, updated_at=?
            WHERE id=?`,
          [nextAttempt, String(error instanceof Error ? error.message : String(error)), nowIso(), job.id],
        );
      }
      writeAuditLog(null, job.clinic_id, 'queue.job_failed', 'background_job', job.id, {
        type: job.type,
        error: error instanceof Error ? error.message : 'unknown',
      });
    }
  }
  return dueJobs.length;
};
