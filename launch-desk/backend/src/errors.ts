export type ErrorCode =
  | 'BAD_REQUEST'
  | 'UNAUTHORIZED'
  | 'FORBIDDEN'
  | 'NOT_FOUND'
  | 'CONFLICT'
  | 'INTERNAL';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: ErrorCode,
    message: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export const badRequest = (message: string, details?: unknown) => new ApiError(400, 'BAD_REQUEST', message, details);
export const unauthorized = (message: string, details?: unknown) => new ApiError(401, 'UNAUTHORIZED', message, details);
export const forbidden = (message: string, details?: unknown) => new ApiError(403, 'FORBIDDEN', message, details);
export const notFound = (message: string, details?: unknown) => new ApiError(404, 'NOT_FOUND', message, details);
export const conflict = (message: string, details?: unknown) => new ApiError(409, 'CONFLICT', message, details);
