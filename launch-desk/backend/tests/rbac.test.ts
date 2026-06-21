import { describe, expect, it } from 'vitest';
import { hasPermission } from '../../backend/src/middleware/rbac.js';

describe('RBAC policy', () => {
  it('grants dentist patients write and denies billing write', () => {
    expect(hasPermission('dentist', 'patients:write')).toBe(true);
    expect(hasPermission('dentist', 'billing:write')).toBe(false);
  });

  it('grants receptionist invoice write', () => {
    expect(hasPermission('receptionist', 'appointments:write')).toBe(true);
    expect(hasPermission('receptionist', 'billing:read')).toBe(true);
  });

  it('grants viewer dashboard read only and blocks writes', () => {
    expect(hasPermission('viewer', 'dashboard:read')).toBe(true);
    expect(hasPermission('viewer', 'patients:write')).toBe(false);
  });

  it('grants owner full access wildcard', () => {
    expect(hasPermission('owner', 'finance:admin')).toBe(true);
  });
});
