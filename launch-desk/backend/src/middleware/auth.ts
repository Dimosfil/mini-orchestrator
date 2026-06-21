import type { NextFunction, Request, Response } from 'express';
import { unauthorized, ApiError } from '../errors.js';
import { issueSessionToken, verifySessionToken } from '../services/security.js';
import { nowIso } from '../db.js';

export type AppUser = {
  id: number;
  email: string;
  fullName: string;
  role: string;
  clinicId: number;
  lastLoginAt?: string | null;
};

export interface AuthenticatedRequest extends Request {
  user?: AppUser;
}

export const authenticate = (req: AuthenticatedRequest, _res: Response, next: NextFunction) => {
  try {
    const header = req.headers.authorization || '';
    if (!header.startsWith('Bearer ')) {
      throw unauthorized('Missing Authorization: Bearer token');
    }

    const token = header.substring(7).trim();
    const parsed = verifySessionToken(token);
    if (!parsed) {
      throw unauthorized('Invalid or expired session token');
    }

    req.user = {
      id: parsed.sub,
      email: parsed.email,
      fullName: parsed.fullName,
      role: parsed.role,
      clinicId: parsed.clinicId,
      lastLoginAt: parsed.iat ? new Date(parsed.iat * 1000).toISOString() : nowIso(),
    };
    next();
  } catch (error) {
    if (error instanceof ApiError) {
      next(error);
      return;
    }
    next(unauthorized('Authentication failed'));
  }
};

export const createAuthPayload = issueSessionToken;
