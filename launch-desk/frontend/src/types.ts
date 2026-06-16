export type LaunchInput = {
  brief: string;
  audience: string;
  launchDate: string;
  constraints: string;
  assets: string[];
};

export type ToolEvent = {
  event: string;
  status?: string;
  message?: string;
  payload?: unknown;
};
