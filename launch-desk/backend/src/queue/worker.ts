import { env } from '../config/env.js';
import { runWorkerOnce } from '../services/queue.js';

let timer: NodeJS.Timeout | null = null;

const loop = () => {
  try {
    const count = runWorkerOnce();
    if (count > 0) {
      process.stdout.write(`[worker] processed ${count} jobs\n`);
    }
  } catch (error) {
    console.error('[worker] processing failed:', error instanceof Error ? error.message : error);
  }
};

const stop = () => {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
  process.exit(0);
};

process.on('SIGINT', stop);
process.on('SIGTERM', stop);

timer = setInterval(loop, env.workerPollIntervalMs);
loop();
console.log(`Dental CRM worker started, pollIntervalMs=${env.workerPollIntervalMs}`);
