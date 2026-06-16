export type LaunchBrief = {
  brief: string;
  audience: string;
  launchDate?: string;
  constraints?: string;
  assets?: string[];
};

export type TaskItem = {
  title: string;
  ownerHint?: string;
  ownerSuggestion: string;
  priority: 'Critical' | 'High' | 'Medium' | 'Low';
  rationale: string;
};

export type RiskItem = {
  risk: string;
  owner: string;
  likelihood: 'High' | 'Medium' | 'Low';
  impact: 'High' | 'Medium' | 'Low';
  mitigation: string;
};

export const channelTonePresets = ['formal', 'friendly', 'enterprise'] as const;

export const copyPromptsByChannel: Record<string, string> = {
  email: 'Launch announcement email',
  blog: 'Release blog post paragraph',
  social: 'Social launch message',
  changelog: 'Release notes snippet',
};

const normalizeArray = (value: string | string[] | undefined | null): string[] => {
  if (!value) {
    return [];
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
};

const splitIntoChunks = (text: string): string[] =>
  text
    .split(/\n|;|\.|\r/)
    .map((chunk) => chunk.trim())
    .filter(Boolean);

export const inferTasksFromBrief = (input: LaunchBrief): TaskItem[] => {
  const combined = [
    input.brief,
    input.audience,
    input.constraints,
    input.assets ? input.assets.join('\n') : '',
  ]
    .filter(Boolean)
    .join('\n');

  const chunks = splitIntoChunks(combined);
  const fallback = [
    'Create launch plan and owner assignment',
    'Prepare QA and release checklist',
    'Prepare monitoring dashboards and rollback plan',
    'Coordinate communications across channels',
    'Finalize go-live runbook',
  ];

  const candidates = chunks.length ? chunks : fallback;

  return candidates.slice(0, 7).map((chunk, idx) => ({
    title: `${idx + 1}. ${chunk.charAt(0).toUpperCase()}${chunk.slice(1).toLowerCase()}`,
    ownerSuggestion: inferOwner(chunk, idx),
    ownerHint: chunk.length > 80 ? chunk.slice(0, 77) + '...' : chunk,
    priority: idx < 2 ? 'Critical' : idx < 4 ? 'High' : 'Medium',
    rationale: `Derived from launch inputs and dependency scope in your brief.`,
  }));
};

const inferOwner = (chunk: string, idx: number): string => {
  const lower = chunk.toLowerCase();
  if (lower.includes('test') || lower.includes('qa') || lower.includes('bug')) {
    return 'QA';
  }
  if (lower.includes('api') || lower.includes('backend') || lower.includes('infra')) {
    return 'Backend';
  }
  if (lower.includes('ui') || lower.includes('frontend') || lower.includes('design')) {
    return 'Frontend';
  }
  if (lower.includes('doc') || lower.includes('content') || lower.includes('copy')) {
    return 'Marketing';
  }
  if (lower.includes('monitor') || lower.includes('sre') || lower.includes('incident')) {
    return 'SRE';
  }
  return ['PM', 'Eng', 'Design', 'QA', 'Data'][idx % 5];
};

export const readinessRubric = (input: LaunchBrief) => {
  const checklist = [
    'Requirements finalized and approved',
    'Implementation complete and peer reviewed',
    'Automated tests passing',
    'Release rollback path defined',
    'Monitoring and alerts pre-configured',
    'Communication schedule ready',
  ];

  const missing: string[] = [];
  if (!input.audience || input.audience.trim().length < 3) {
    missing.push('Audience definition');
  }
  if (!input.launchDate) {
    missing.push('Launch date');
  }
  if (!input.assets || input.assets.length === 0) {
    missing.push('Available launch assets');
  }

  const completed = checklist.filter((item) => !missing.some((m) => m.toLowerCase().includes(item.toLowerCase())));
  const score = Math.max(0, Math.round((completed.length / checklist.length) * 100));
  return {
    score,
    checklist,
    completed: completed.length,
    totalChecklistItems: checklist.length,
    blockingGaps: missing,
    recommendation: score >= 80 ? 'Launch-ready with minimal open risks.' : 'Not ready yet: resolve missing inputs before plan finalization.',
  };
};

export const ownerChecklist = (tasks: TaskItem[]) => {
  const owners = new Map<string, string[]>();
  for (const task of tasks) {
    const owner = task.ownerSuggestion ?? 'Platform';
    const list = owners.get(owner) ?? [];
    list.push(task.title);
    owners.set(owner, list);
  }
  return Array.from(owners, ([owner, items]) => ({
    owner,
    items,
    status: 'not started',
  }));
};

export const draftLaunchCopy = (input: LaunchBrief, tone: string, channel: string) => {
  const assets = normalizeArray(input.assets).join(', ');
  const target = input.audience || 'customers and internal stakeholders';
  const date = input.launchDate || 'upcoming';
  const channelName = copyPromptsByChannel[channel] || 'Launch message';

  return {
    channel,
    channelName,
    tone,
    draft: `${channelName} (${tone}): Launching ${input.brief.slice(0, 90)}. ${target} should receive this message before ${date}.` +
      `${assets ? ` Built with assets: ${assets}.` : ''} ` +
      `Available now for preview, with rollout support from product and engineering.`,
  };
};

export const buildFollowUpQuestions = (input: LaunchBrief): string[] => {
  const questions: string[] = [];
  if (!input.brief || input.brief.trim().length < 20) {
    questions.push('Can you share a longer product brief with target user outcomes and success metrics?');
  }
  if (!input.audience || input.audience.trim().length < 3) {
    questions.push('Who is the primary launch audience segment for this release?');
  }
  if (!input.launchDate) {
    questions.push('What is the target launch date and timezone?');
  }
  if (!input.constraints || input.constraints.trim().length < 5) {
    questions.push('What technical/commercial constraints should be considered as hard blockers?');
  }
  return questions;
};
