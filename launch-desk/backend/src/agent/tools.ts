import { z } from 'zod';
import { tool } from '@openai/agents';
import { channelTonePresets, draftLaunchCopy as buildCopyDraft, inferTasksFromBrief, readinessRubric, ownerChecklist, buildFollowUpQuestions, LaunchBrief } from './toolHelpers';

export const extractTasksTool = tool({
  name: 'extract_tasks',
  description:
    'Extract a realistic, prioritized launch task list from a rough idea brief. Return compact bullets with owner hints.',
  strict: true,
  parameters: z.object({
    brief: z.string().min(20).describe('Rough product brief text from the user.'),
    audience: z.string().describe('Audience description from the user.'),
    launchDate: z.string().describe('Planned launch date in natural language or ISO format.'),
    constraints: z.string().describe('Technical and commercial constraints.'),
    assets: z.array(z.string()).default([]).describe('Available launch assets as a list.'),
  }),
  needsApproval: async () => false,
  invoke: async (_runContext, input) => {
    const parsed = input as LaunchBrief;
    const tasks = inferTasksFromBrief(parsed);
    const byPriority = tasks.reduce<Record<string, string[]>>((acc, item) => {
      if (!acc[item.priority]) {
        acc[item.priority] = [];
      }
      acc[item.priority].push(`${item.title} (Owner: ${item.ownerSuggestion})`);
      return acc;
    }, {});
    return JSON.stringify({ tasks, byPriority });
  },
});

export const readinessRubricTool = tool({
  name: 'check_launch_readiness',
  description:
    'Evaluate the launch plan against a rubric and return a risk-based readiness score.',
  strict: true,
  parameters: z.object({
    brief: z.string().min(20),
    audience: z.string(),
    launchDate: z.string(),
    constraints: z.string(),
    assets: z.array(z.string()).default([]),
  }),
  needsApproval: async () => false,
  invoke: async (_runContext, input) => {
    const parsed = input as LaunchBrief;
    const readyness = readinessRubric(parsed);
    return JSON.stringify(readyness);
  },
});

export const ownerChecklistTool = tool({
  name: 'generate_owner_checklist',
  description:
    'Produce an owner-centric checklist for the launch tasks and dependencies.',
  strict: true,
  parameters: z.object({
    tasks: z.array(
      z.object({
        title: z.string(),
        ownerSuggestion: z.string(),
        priority: z.enum(['Critical', 'High', 'Medium', 'Low']),
      }),
    ),
  }),
  needsApproval: async () => false,
  invoke: async (_runContext, input) => {
    const data = input as { tasks: { title: string; ownerSuggestion: string; priority: 'Critical' | 'High' | 'Medium' | 'Low' }[] };
    return JSON.stringify(ownerChecklist(
      data.tasks.map((task) => ({
        title: task.title,
        ownerSuggestion: task.ownerSuggestion,
        priority: task.priority,
        rationale: 'Derived for team handoff clarity.',
        ownerHint: 'auto',
      })),
    ));
  },
});

export const channelCopyTool = tool({
  name: 'draft_channel_launch_copy',
  description:
    'Draft launch copy for a specific channel using requested tone, with messaging constraints in mind.',
  strict: true,
  parameters: z.object({
    brief: z.string().min(20),
    audience: z.string(),
    launchDate: z.string(),
    assets: z.array(z.string()).default([]),
    channel: z.enum(['email', 'social', 'blog', 'changelog']),
    tone: z.enum(channelTonePresets),
  }),
  needsApproval: async () => false,
  invoke: async (_runContext, input) => {
    const { brief, audience, launchDate, assets, channel, tone } = input as {
      brief: string;
      audience: string;
      launchDate: string;
      assets: string[];
      channel: string;
      tone: string;
    };
    const result = buildCopyDraft({ brief, audience, launchDate, assets }, tone, channel);
    return JSON.stringify(result);
  },
});

export const launchPlanTools = [
  extractTasksTool,
  readinessRubricTool,
  ownerChecklistTool,
  channelCopyTool,
];

export const followUpTool = tool({
  name: 'generate_follow_up_questions',
  description:
    'Generate follow-up questions when the initial brief is incomplete.',
  strict: true,
  parameters: z.object({
    brief: z.string().min(10),
    audience: z.string(),
    launchDate: z.string(),
    constraints: z.string(),
    assets: z.array(z.string()).default([]),
  }),
  needsApproval: async () => false,
  invoke: async (_runContext, input) => {
    const parsed = input as LaunchBrief;
    const questions = buildFollowUpQuestions(parsed);
    return JSON.stringify({ questions });
  },
});

export const allLaunchTools = [extractTasksTool, readinessRubricTool, ownerChecklistTool, channelCopyTool, followUpTool];
