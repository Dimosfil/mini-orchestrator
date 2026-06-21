import express from 'express';
import cors from 'cors';
import { env, assertConfig } from './config/env.js';
import routes from './routes.js';
import { requestId } from './middleware/requestContext.js';
import { ApiError } from './errors.js';
import { runWorkerOnce } from './services/queue.js';
import { db, getRow, runQuery } from './db.js';
import { env as _env } from 'node:process';

assertConfig();

const app = express();
app.use(requestId);
app.use(cors({ origin: env.corsOrigin, credentials: true }));
app.use(express.json({ limit: '1mb' }));

app.get('/api/health', (_req, res) => {
  const migration = getRow<{ total: number }>(`SELECT COUNT(*) AS total FROM schema_migrations`);
  const queueCount = getRow<{ count: number }>(`SELECT COUNT(*) AS count FROM background_jobs WHERE status='pending'`);
  const dbPath = env.databasePath;
  res.json({
    ok: true,
    service: 'dental-crm-backend',
    version: '1.0.0',
    database: { path: dbPath, migrations: migration?.total ?? 0 },
    queue: { pending: queueCount?.count ?? 0 },
    nodeVersion: _env.NODE_VERSION ?? process.version,
  });
});

app.use('/api', routes);
if (env.workerEnabled) {
  setInterval(() => {
    runWorkerOnce();
  }, env.workerPollIntervalMs);
}

app.use((err: Error, _req: express.Request, res: express.Response, next: express.NextFunction) => {
  if (err instanceof ApiError) {
    res.status(err.status).json({ error: { code: err.code, message: err.message, details: err.details } });
    return;
  }
  console.error('[dental-crm] unexpected error', err);
  res.status(500).json({ error: { code: 'INTERNAL', message: 'Unexpected error' } });
});

app.use((_req, res) => {
  res.status(404).json({ error: { code: 'NOT_FOUND', message: 'Not found' } });
});

app.listen(env.port, () => {
  db.get();
  console.log(`Dental CRM backend listening on http://localhost:${env.port}`);
});
