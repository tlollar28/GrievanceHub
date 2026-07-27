import { apiRequest } from './client'

/** Matches FastAPI GET /health in app/main.py. */
export type HealthResponse = {
  status: string
  service: string
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health', { signal })
}

export function isHealthyResponse(payload: HealthResponse): boolean {
  return payload.status === 'healthy'
}
