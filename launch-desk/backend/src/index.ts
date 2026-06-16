import express from 'express';
import cors from 'cors';
import { assertConfig, env } from './config/env';
import { createPlan } from './routes/plan';

const app = express();

app.use(cors({
  origin: true,
  credentials: true,
}));
app.use(express.json({ limit: '1mb' }));

app.get('/api/health', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'launch-desk-backend',
    tracingEnabled: env.tracingEnabled,
    model: env.launchDeskModel,
  });
});

app.post('/api/plan', createPlan);

app.get('/api/plan', (_req, res) => {
  res.json({
    message:
      'Send POST /api/plan with { brief, audience, launchDate, constraints, assets } to stream Launch Desk output.',
  });
});

try {
  assertConfig();
} catch (error) {
  if (error instanceof Error) {
    console.error(`[launch-desk] ${error.message}`);
  } else {
    console.error('[launch-desk] Backend configuration error');
  }
  process.exit(1);
}

app.listen(env.port, () => {
  console.log(`Launch Desk backend listening on http://localhost:${env.port}`);
});
