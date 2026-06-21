import path from 'node:path';
import { config } from 'dotenv';

config();

const toNumber = (value: string | undefined, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

export const env = {
  nodeEnv: process.env.NODE_ENV ?? 'development',
  port: toNumber(process.env.PORT, 4000),
  databasePath: path.resolve(process.cwd(), process.env.DATABASE_PATH ?? 'data/dental-crm.sqlite'),
  jwtSecret: process.env.JWT_SECRET ?? '',
  jwtExpiresInHours: toNumber(process.env.JWT_EXPIRES_IN_HOURS, 12),
  corsOrigin: process.env.CORS_ORIGIN ?? 'http://localhost:5173',
  authRateLimitWindowMs: toNumber(process.env.AUTH_RATE_LIMIT_WINDOW_MS, 60_000),
  authRateLimitMaxAttempts: toNumber(process.env.AUTH_RATE_LIMIT_MAX_ATTEMPTS, 12),
  seedClinicName: process.env.SEED_CLINIC_NAME ?? 'Main Dental Clinic',
  seedAdminEmail: process.env.SEED_ADMIN_EMAIL ?? 'owner@dental.local',
  seedAdminPassword: process.env.SEED_ADMIN_PASSWORD ?? 'change-me',
  seedAdminName: process.env.SEED_ADMIN_NAME ?? 'System Owner',
  workerPollIntervalMs: toNumber(process.env.WORKER_POLL_INTERVAL_MS, 5_000),
  workerEnabled: process.env.WORKER_ENABLED !== 'false',
  logLevel: process.env.LOG_LEVEL ?? 'info',
};

export function assertConfig() {
  if (!env.jwtSecret) {
    throw new Error('JWT_SECRET is required in .env');
  }
  if (env.jwtSecret.length < 24) {
    throw new Error('JWT_SECRET must be at least 24 characters');
  }
  if (!env.seedAdminPassword || env.seedAdminPassword === 'change-me') {
    throw new Error('SEED_ADMIN_PASSWORD must be set for first boot seeding');
  }
}
