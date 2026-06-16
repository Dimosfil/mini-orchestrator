import { z } from 'zod';

export const launchInputSchema = z.object({
  brief: z.string().min(20, 'Please provide a richer brief so we can plan effectively.'),
  audience: z.string().min(3, 'Audience should include at least one primary segment.'),
  launchDate: z.string().min(6, 'Launch date is required for realistic planning.'),
  constraints: z.string().min(1, 'Constraints help us avoid risky plans.'),
  assets: z.array(z.string().transform((asset) => asset.trim())).default([]),
});

export type LaunchInput = z.infer<typeof launchInputSchema>;
