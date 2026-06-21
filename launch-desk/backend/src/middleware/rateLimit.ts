import type { Request, Response, NextFunction } from 'express';
import { env } from '../config/env.js';
import { unauthorized } from '../errors.js';

type Bucket = { count: number; windowEndsAt: number };
const buckets = new Map<string, Bucket>();

export const authRateLimit = (req: Request, res: Response, next: NextFunction) => {
  const key = req.ip || req.socket.remoteAddress || 'global';
  const now = Date.now();
  const existing = buckets.get(key);
  const windowEndsAt = Math.floor(now / env.authRateLimitWindowMs) * env.authRateLimitWindowMs + env.authRateLimitWindowMs;

  if (!existing || existing.windowEndsAt < now) {
    buckets.set(key, { count: 1, windowEndsAt });
    next();
    return;
  }

  if (existing.count >= env.authRateLimitMaxAttempts) {
    next(unauthorized('Rate limit exceeded. Slow down login attempts.'));
    return;
  }

  existing.count += 1;
  next();
};
