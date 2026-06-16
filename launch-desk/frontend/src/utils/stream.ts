import { ToolEvent } from '../types';

export type LaunchSSEMessage = {
  event: string;
  [key: string]: unknown;
};

export async function readLaunchSseStream(
  response: Response,
  onEvent: (event: LaunchSSEMessage) => void,
): Promise<void> {
  if (!response.ok || !response.body) {
    const payload = await response.text();
    throw new Error(`Plan request failed: ${response.status} ${payload}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const chunk = await reader.read();
    if (chunk.done) {
      break;
    }
    buffer += decoder.decode(chunk.value, { stream: true });
    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + 2);
      if (block.length) {
        const lines = block.split('\n').map((line) => line.trim());
        let eventName = 'message';
        const payloadLines: string[] = [];
        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventName = line.substring(6).trim();
          } else if (line.startsWith('data:')) {
            payloadLines.push(line.substring(5).trim());
          }
        }

        const payloadText = payloadLines.join('\n');
        try {
          const payload = payloadText ? (JSON.parse(payloadText) as LaunchSSEMessage) : { event: eventName };
          onEvent({
            event: payload.event ?? eventName,
            ...payload,
          });
        } catch (err) {
          onEvent({
            event: eventName,
            message: payloadText,
          } as ToolEvent);
        }
      }
      boundary = buffer.indexOf('\n\n');
    }
  }
}
