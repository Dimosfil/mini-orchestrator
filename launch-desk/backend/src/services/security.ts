import { createHmac, createHash, randomBytes, pbkdf2Sync, timingSafeEqual } from 'node:crypto';
import { env } from '../config/env.js';

const PBKDF2_ITERS = 120000;
const PBKDF2_KEYLEN = 64;
const PBKDF2_DIGEST = 'sha512';

const toTokenParts = (payload: string, signature: string) => `${Buffer.from(payload, 'utf8').toString('base64url')}.${signature}`;
const fromTokenParts = (token: string) => {
  const separatorIndex = token.indexOf('.');
  if (separatorIndex < 1) {
    return null;
  }
  const encodedPayload = token.slice(0, separatorIndex);
  const signature = token.slice(separatorIndex + 1);
  const payload = Buffer.from(encodedPayload, 'base64url').toString('utf8');
  return { payload, signature };
};

const sign = (payload: string) => {
  return createHmac('sha256', env.jwtSecret).update(payload).digest('base64url');
};

export type SessionClaims = {
  sub: number;
  email: string;
  fullName: string;
  role: string;
  clinicId: number;
  iat: number;
  exp: number;
};

export type PasswordHash = {
  hash: string;
  salt: string;
};

export const hashPassword = (password: string): string => {
  const salt = randomBytes(16).toString('base64url');
  const derived = pbkdf2Sync(password, salt, PBKDF2_ITERS, PBKDF2_KEYLEN, PBKDF2_DIGEST).toString('base64url');
  return `${salt}:${derived}`;
};

export const verifyPassword = (password: string, stored: string): boolean => {
  const [salt, hash] = stored.split(':');
  if (!salt || !hash) {
    return false;
  }
  const candidate = pbkdf2Sync(password, salt, PBKDF2_ITERS, PBKDF2_KEYLEN, PBKDF2_DIGEST).toString('base64url');
  const hashBuf = Buffer.from(hash, 'base64url');
  const candidateBuf = Buffer.from(candidate, 'base64url');
  if (hashBuf.length !== candidateBuf.length) {
    return false;
  }
  return timingSafeEqual(hashBuf, candidateBuf);
};

export const issueSessionToken = (input: Omit<SessionClaims, 'iat' | 'exp'>) => {
  const iat = Math.floor(Date.now() / 1000);
  const exp = iat + env.jwtExpiresInHours * 3600;
  const payload: SessionClaims = { ...input, iat, exp };
  const tokenPayload = JSON.stringify(payload);
  const payloadHash = createHash('sha256').update(tokenPayload).digest('hex');
  const signature = sign(`${tokenPayload}.${payloadHash}`);
  return { token: toTokenParts(tokenPayload, signature), expiresAt: payload.exp };
};

export const verifySessionToken = (token: string): SessionClaims | null => {
  const parsed = fromTokenParts(token);
  if (!parsed) {
    return null;
  }
  const { payload, signature } = parsed;
  const payloadObj = JSON.parse(payload) as SessionClaims;
  const expected = sign(`${payload}.${createHash('sha256').update(payload).digest('hex')}`);
  const expectedBuf = Buffer.from(expected);
  const actualBuf = Buffer.from(signature);
  if (expectedBuf.length !== actualBuf.length || !timingSafeEqual(expectedBuf, actualBuf)) {
    return null;
  }
  if (payloadObj.exp < Math.floor(Date.now() / 1000)) {
    return null;
  }
  return payloadObj;
};
