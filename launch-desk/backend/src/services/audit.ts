import { runCommand } from '../db.js';

export const writeAuditLog = (
  actorUserId: number | null,
  clinicId: number,
  action: string,
  entityType: string,
  entityId: number | null,
  details: unknown,
) => {
  runCommand(
    `INSERT INTO audit_logs (
      actor_user_id, clinic_id, action, entity_type, entity_id, payload_json, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))`,
    [actorUserId, clinicId, action, entityType, entityId, JSON.stringify(details ?? {})],
  );
};
