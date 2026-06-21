import type { Request, Response, NextFunction } from 'express';
import { randomUUID } from 'node:crypto';

export const requestId = (req: Request, res: Response, next: NextFunction) => {
  const requestId = (req.header('x-request-id')?.trim() || randomUUID());
  res.setHeader('x-request-id', requestId);
  (req as Request & { requestId: string }).requestId = requestId;
  next();
};
