import { FormEvent, useMemo, useState } from 'react';
import { LaunchInput } from './types';
import { readLaunchSseStream } from './utils/stream';

const initialInput: LaunchInput = {
  brief: 'We plan to introduce a new feature that notifies teams when feature flags are flipped and lets users self-assign rollout waves.',
  audience: 'Enterprise beta customers and internal platform users',
  launchDate: '2026-07-18',
  constraints: 'No regression on existing dashboards. Launch must be behind a feature flag and support rollback within 10 minutes.',
  assets: ['release-notes.md', 'screenshot pack', 'email copy draft'],
};

const formatSection = (title: string, raw: string) => {
  const lines = raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) {
    return null;
  }
  return (
    <div className="panel">
      <h3>{title}</h3>
      <ul>
        {lines.map((line, index) => (
          <li key={line + index}>{line}</li>
        ))}
      </ul>
    </div>
  );
};

const splitSections = (output: string) => {
  const lines = output.split('\n').map((line) => line.trim()).filter(Boolean);
  const buckets: Record<string, string[]> = {
    Plan: [],
    'Risk Register': [],
    'Owner Checklist': [],
    'Launch Copy': [],
    'Follow-up Questions': [],
  };
  let active = 'Plan';
  for (const line of lines) {
    const lower = line.toLowerCase();
    if (lower.startsWith('##') || lower.startsWith('1)') || lower.startsWith('prioritized') || lower.startsWith('1. prioritized')) {
      if (lower.includes('risk')) active = 'Risk Register';
      else if (lower.includes('owner')) active = 'Owner Checklist';
      else if (lower.includes('copy')) active = 'Launch Copy';
      else if (lower.includes('follow') || lower.includes('question')) active = 'Follow-up Questions';
      else if (lower.includes('plan') || lower.includes('prioritized')) active = 'Plan';
      continue;
    }
    if (line.startsWith('-') || line.startsWith('*') || /^\d+\./.test(line)) {
      buckets[active].push(line.replace(/^[-*]\s?/, '').replace(/^\d+\.\s?/, ''));
    } else {
      buckets[active].push(line);
    }
  }
  return buckets;
};

export default function App() {
  const [form, setForm] = useState<LaunchInput>(initialInput);
  const [streamText, setStreamText] = useState('');
  const [toolProgress, setToolProgress] = useState<string[]>([]);
  const [status, setStatus] = useState('Ready');
  const [loading, setLoading] = useState(false);
  const [finalOutput, setFinalOutput] = useState('');
  const [errors, setErrors] = useState('');
  const [lastStreamFlags, setLastStreamFlags] = useState({
    toolProgress: false,
    modelTextDelta: false,
  });

  const sections = useMemo(() => splitSections(finalOutput), [finalOutput]);

  const updateAssetInput = (value: string) => {
    const assets = value
      .split(',')
      .map((asset) => asset.trim())
      .filter(Boolean);
    setForm((prev) => ({ ...prev, assets }));
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setErrors('');
    setToolProgress([]);
    setStreamText('');
    setFinalOutput('');
    setLastStreamFlags({ toolProgress: false, modelTextDelta: false });

    try {
      setStatus('Streaming agent progress...');
      const response = await fetch('/api/plan', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(form),
      });

      await readLaunchSseStream(response, (msg) => {
        switch (msg.event) {
          case 'tool_progress':
            setLastStreamFlags((previous) => ({ ...previous, toolProgress: true }));
            setToolProgress((previous) => [...previous, JSON.stringify({ ...msg })].slice(-20));
            break;
          case 'model_delta':
            setLastStreamFlags((previous) => ({ ...previous, modelTextDelta: true }));
            setStreamText((previous) => `${previous}${msg.text ?? ''}`);
            break;
          case 'final':
            if (typeof msg.finalOutput === 'string') {
              setFinalOutput(msg.finalOutput);
            }
            setStatus('Completed');
            setTimeout(() => {
              setStatus('Ready');
            }, 1500);
            break;
          case 'done':
            setStatus(typeof msg.status === 'string' ? msg.status : 'Done');
            break;
          case 'error':
            setErrors(String(msg.message ?? 'Unknown error'));
            setStatus('Error');
            break;
          default:
            break;
        }
      });
    } catch (error) {
      setErrors(error instanceof Error ? error.message : 'Unexpected error');
      setStatus('Error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <p className="eyebrow">Launch Planner</p>
          <h1>Launch Desk</h1>
          <p>Turn ideas into rollout-ready launch plans with live tool and model progress.</p>
        </div>
        <div className="status">
          <span>{status}</span>
          <span>
            {lastStreamFlags.toolProgress ? '✅ tool progress' : '⏳ waiting tool'}
          </span>
          <span>
            {lastStreamFlags.modelTextDelta ? '✅ model delta' : '⏳ waiting model'}
          </span>
        </div>
      </header>

      <main className="layout">
        <section className="panel form-panel">
          <h2>Launch Inputs</h2>
          <form onSubmit={onSubmit}>
            <label>
              Product brief
              <textarea
                required
                rows={5}
                value={form.brief}
                onChange={(event) => setForm((prev) => ({ ...prev, brief: event.target.value }))}
              />
            </label>
            <label>
              Audience
              <input
                required
                value={form.audience}
                onChange={(event) => setForm((prev) => ({ ...prev, audience: event.target.value }))}
              />
            </label>
            <label>
              Target launch date
              <input
                required
                type="date"
                value={form.launchDate}
                onChange={(event) => setForm((prev) => ({ ...prev, launchDate: event.target.value }))}
              />
            </label>
            <label>
              Constraints (compliance, release, compliance, risks)
              <textarea
                required
                rows={3}
                value={form.constraints}
                onChange={(event) => setForm((prev) => ({ ...prev, constraints: event.target.value }))}
              />
            </label>
            <label>
              Assets (comma-separated)
              <input
                value={form.assets.join(', ')}
                onChange={(event) => updateAssetInput(event.target.value)}
              />
            </label>
            <button type="submit" disabled={loading}>
              {loading ? 'Generating...' : 'Build Launch Plan'}
            </button>
          </form>
        </section>

        <section className="panel output-panel">
          <h2>Launch Desk Output</h2>
          <div className="live-log">
            <pre>{streamText || 'Waiting for stream...'}</pre>
          </div>
          <div className="tool-events">
            <h3>Tool progress events</h3>
            <ul>
              {toolProgress.map((item, idx) => (
                <li key={`${item}-${idx}`}>{item}</li>
              ))}
            </ul>
          </div>
          <div className="cards">
            {formatSection('Prioritized Plan', sections.Plan.join('\n'))}
            {formatSection('Risk Register', sections['Risk Register'].join('\n'))}
            {formatSection('Owner Checklist', sections['Owner Checklist'].join('\n'))}
            {formatSection('Launch Copy', sections['Launch Copy'].join('\n'))}
            {formatSection('Follow-up Questions', sections['Follow-up Questions'].join('\n'))}
          </div>
          {errors ? <p className="error">Error: {errors}</p> : null}
        </section>
      </main>
    </div>
  );
}
