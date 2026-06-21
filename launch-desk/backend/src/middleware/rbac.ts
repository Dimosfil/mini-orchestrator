import type { NextFunction, Response } from 'express';
import { forbidden } from '../errors.js';
import type { AuthenticatedRequest } from './auth.js';

const rolePermissions: Record<string, string[]> = {
  'owner': ['*'],
  'admin': ['*'],
  'dentist': [
    'patients:read',
    'patients:write',
    'appointments:read',
    'appointments:write',
    'treatment-plans:read',
    'treatment-plans:write',
    'clinical-notes:read',
    'clinical-notes:write',
    'tasks:read',
    'tasks:write',
    'dashboard:read',
  ],
  'assistant': [
    'patients:read',
    'appointments:read',
    'appointments:write',
    'clinical-notes:read',
    'tasks:read',
    'dashboard:read',
  ],
  'receptionist': [
    'patients:read',
    'patients:write',
    'appointments:read',
    'appointments:write',
    'invoices:read',
    'invoices:write',
    'billing:read',
    'tasks:read',
    'tasks:write',
    'dashboard:read',
  ],
  'billing': [
    'invoices:read',
    'invoices:write',
    'billing:read',
    'billing:write',
    'patients:read',
    'tasks:read',
    'dashboard:read',
  ],
  'viewer': [
    'patients:read',
    'appointments:read',
    'treatment-plans:read',
    'clinical-notes:read',
    'invoices:read',
    'tasks:read',
    'dashboard:read',
  ],
};

export const hasPermission = (role: string, permission: string) => {
  const grants = rolePermissions[role] ?? [];
  return grants.includes('*') || grants.includes(permission);
};

export const requirePermission = (permission: string) => {
  return (req: AuthenticatedRequest, _res: Response, next: NextFunction) => {
    const role = req.user?.role ?? '';
    if (!hasPermission(role, permission)) {
      next(forbidden(`Permission denied: ${permission}`));
      return;
    }
    next();
  };
};
