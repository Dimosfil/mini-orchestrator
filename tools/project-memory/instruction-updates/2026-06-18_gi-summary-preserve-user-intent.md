# GI recommendation: preserve user intent in `gi summary`

Date: 2026-06-18

## Problem

`gi summary` / `ги саммари` currently ensures that a handoff file is written, but
it does not explicitly require the agent to preserve the user's deeper intent
when the thread is about future integration, architecture direction, or a
decision path.

This can produce a technically correct handoff that lists facts and next steps
but misses the reason the user cared about the discussion.

## Recommended Rule

When writing a `gi summary`, include an explicit `User Intent` or `Why This
Matters` section whenever the conversation includes:

- a planned integration or migration;
- repeated questions comparing an external project/pattern to the current
  project;
- user wording such as "I want to integrate", "we need to adopt", "how does
  this map to us", or similar intent signals;
- screenshots or follow-up corrections that point to a missing architectural
  implication.

The summary should preserve not only what was discussed, but also what the user
is trying to do with that discussion.

## Suggested `gi summary` Checklist

- What concrete task or project direction was the user exploring?
- Was the discussion informational, or was it preparation for implementation?
- What external project, article, pattern, or tool is being considered for
  integration?
- Which current local components map to that external pattern?
- What should a future agent not miss when continuing the work?
- Which conclusions are decisions, and which are still hypotheses?

## Example Rule Text

For `gi summary`, do not reduce architecture or research conversations to a
generic list of facts. If the user is evaluating an external project, article,
or tool as a possible integration target, the handoff must state that
integration intent explicitly and map the external concepts to current project
components. Preserve strong user-facing conclusions and corrections as
continuation-critical context.
