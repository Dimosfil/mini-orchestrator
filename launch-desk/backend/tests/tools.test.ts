import { describe, expect, it } from 'vitest';
import { inferTasksFromBrief, readinessRubric, ownerChecklist, buildFollowUpQuestions, draftLaunchCopy } from '../src/agent/toolHelpers';

describe('Launch Desk tool helpers', () => {
  it('extracts tasks from a short brief', () => {
    const tasks = inferTasksFromBrief({
      brief: 'Roll out new onboarding flow. Run load tests. Fix API timeout errors in staging. Prepare customer-facing changelog.',
      audience: 'Beta users in enterprise accounts',
      launchDate: '2026-07-01',
      constraints: 'No downtime, no more than 2 releases/week',
      assets: ['release notes', 'one-pager'],
    });
    expect(tasks.length).toBeGreaterThan(0);
    expect(tasks[0].priority).toBe('Critical');
  });

  it('builds a readiness score with missing context', () => {
    const readiness = readinessRubric({
      brief: 'Launch a new feature for release notes and notifications.',
      audience: '',
      launchDate: '',
      constraints: '',
      assets: [],
    });
    expect(readiness.score).toBeLessThan(100);
    expect(readiness.blockingGaps.length).toBeGreaterThan(0);
  });

  it('groups tasks by owner checklist', () => {
    const tasks = [
      { title: 'Task A', ownerSuggestion: 'QA', priority: 'High', rationale: 'x', ownerHint: 'a' },
      { title: 'Task B', ownerSuggestion: 'QA', priority: 'Medium', rationale: 'y', ownerHint: 'b' },
      { title: 'Task C', ownerSuggestion: 'Backend', priority: 'Critical', rationale: 'z', ownerHint: 'c' },
    ];
    const owners = ownerChecklist(tasks);
    const qa = owners.find((entry) => entry.owner === 'QA');
    expect(qa?.items.length).toBe(2);
    expect(owners.length).toBe(2);
  });

  it('asks follow-up questions when audience is missing', () => {
    const questions = buildFollowUpQuestions({
      brief: 'Short brief',
      audience: '',
      launchDate: '',
      constraints: '',
      assets: [],
    });
    expect(questions.length).toBeGreaterThan(1);
  });

  it('drafts channel copy', () => {
    const draft = draftLaunchCopy(
      {
        brief: 'Feature to track feature flags in one place.',
        audience: 'Platform engineers',
        launchDate: '2026-07-15',
        assets: ['Figma pack'],
      },
      'friendly',
      'email',
    );
    expect(draft.channel).toBe('email');
    expect(draft.draft).toContain('Launch');
  });
});
