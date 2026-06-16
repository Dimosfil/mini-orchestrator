import { type Request, type Response } from 'express';
import { run } from '@openai/agents';
import { z } from 'zod';
import { launchPlannerAgent } from '../agent/planner';
import { launchInputSchema, LaunchInput } from '../agent/schema';
import { env } from '../config/env';

type StreamEvent = {
  event?: string;
  type?: string;
  data: unknown;
};

const launchPrompt = (payload: LaunchInput): string => `
You are working with this rough launch input:
- Product brief: ${payload.brief}
- Audience: ${payload.audience}
- Launch date: ${payload.launchDate}
- Constraints: ${payload.constraints}
- Available assets: ${payload.assets.join(', ') || 'None listed'}

Create:
1) prioritized plan
2) risk register (impact x likelihood)
3) owner checklist
4) launch copy snippets (email + social + changelog/blog)
5) follow-up questions for missing details.

Return concise, structured sections with concrete owners, suggested owners, dependencies, and acceptance criteria.
`.trim();

const normalizeEventPayload = (value: unknown) => {
  if (typeof value === 'string') {
    return value;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
};

const sendSse = (res: Response, eventName: string, payload: Record<string, unknown>) => {
  const body = JSON.stringify({ event: eventName, ...payload });
  res.write(`event: ${eventName}\n`);
  res.write(`data: ${body}\n\n`);
};

const extractTextDelta = (rawEvent: { type?: string; delta?: unknown; [key: string]: unknown }) => {
  if (!rawEvent || rawEvent.type !== 'response.output_text.delta') {
    return '';
  }
  if (typeof rawEvent.delta === 'string') {
    return rawEvent.delta;
  }
  if (rawEvent.delta && typeof rawEvent.delta === 'object' && typeof (rawEvent.delta as { text?: string }).text === 'string') {
    return (rawEvent.delta as { text?: string }).text ?? '';
  }
  if (typeof (rawEvent as { text?: string }).text === 'string') {
    return (rawEvent as { text?: string }).text ?? '';
  }
  return '';
};

export const createPlan = async (req: Request, res: Response) => {
  const parsed = launchInputSchema.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({
      error: 'Invalid launch payload',
      details: parsed.error.flatten(),
    });
    return;
  }

  const payload = parsed.data;

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache, no-transform');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  sendSse(res, 'connection', { message: 'connected_to_launch_desk', status: 'streaming' });

  try {
    const result = await run(launchPlannerAgent, launchPrompt(payload), {
      stream: true,
      workflowName: env.workflowName,
      maxTurns: 10,
      traceIncludeSensitiveData: env.traceIncludeSensitiveData,
      tracingDisabled: !env.tracingEnabled,
      ...(env.openAiTracingApiKey
        ? { tracing: { apiKey: env.openAiTracingApiKey } }
        : {}),
      groupId: `launch-desk-${new Date().toISOString().slice(0, 10)}`,
      traceMetadata: { source: 'launch-desk-ui' },
    });

    let emittedTextDelta = false;
    let emittedToolEvent = false;

    for await (const event of result as AsyncIterable<unknown>) {
      const typed = event as StreamEvent;
      if (typed.event === 'tool_called' || typed.type === 'run_item_stream_event') {
        if (!emittedToolEvent) {
          emittedToolEvent = true;
        }
        sendSse(res, 'tool_progress', {
          message: 'tool call',
          status: 'running',
          payload: typed.data ?? typed,
        });
        continue;
      }

      if (typed.type === 'raw_model_stream_event') {
        const rawEvent = (typed as { data?: unknown }).data as {
          type?: string;
          delta?: unknown;
          text?: unknown;
          [key: string]: unknown;
        };
        const delta = extractTextDelta(rawEvent);
        if (delta) {
          emittedTextDelta = true;
          sendSse(res, 'model_delta', { text: delta });
        }
      }
    }

    await result.completed;

    const finalOutput = result.finalOutput ?? '';
    const finalText = normalizeEventPayload(finalOutput);

    sendSse(res, 'final', {
      finalOutput: finalText,
      events: {
        toolProgress: emittedToolEvent,
        modelTextDelta: emittedTextDelta,
      },
      status: 'completed',
    });

    if (!emittedToolEvent || !emittedTextDelta) {
      const fallbackChunk = finalText
        .split('\n')
        .filter((line) => !!line.trim())
        .slice(0, 8)
        .join('\n');
      if (!emittedTextDelta && fallbackChunk) {
        sendSse(res, 'model_delta', { text: fallbackChunk });
      }
      if (!emittedToolEvent) {
        sendSse(res, 'tool_progress', { message: 'tool-call-summary', status: 'no_tool_delta_detected' });
      }
    }

    sendSse(res, 'done', { status: 'ok' });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unexpected planner error';
    const isAuth = message.includes('api key') || message.includes('Invalid API key');
    res.statusCode = isAuth ? 401 : 500;
    sendSse(res, 'error', { status: 'failed', message });
  } finally {
    res.end();
  }
};
