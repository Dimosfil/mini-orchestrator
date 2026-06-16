import { config } from 'dotenv';

config();

export const env = {
  openAiApiKey: process.env.OPENAI_API_KEY?.trim() ?? '',
  port: Number(process.env.PORT ?? '4000'),
  launchDeskModel: process.env.LAUNCH_DESK_MODEL?.trim() || process.env.OPENAI_DEFAULT_MODEL?.trim() || 'gpt-5.4-mini',
  openAiTracingApiKey: process.env.OPENAI_API_TRACING_KEY?.trim(),
  workflowName: process.env.LAUNCH_DESK_WORKFLOW_NAME ?? 'Launch Desk planning workflow',
  traceIncludeSensitiveData: process.env.LAUNCH_DESK_TRACE_INCLUDE_SENSITIVE_DATA !== 'false',
  tracingEnabled: process.env.LAUNCH_DESK_TRACING_DISABLED !== 'true',
};

export function assertConfig() {
  if (!env.openAiApiKey) {
    throw new Error(
      'OPENAI_API_KEY is required. Set it in launch-desk/.env (or process environment) before starting the backend.',
    );
  }
}
