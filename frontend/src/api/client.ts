export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly path: string

  constructor(options: {
    status: number
    message: string
    path: string
    code?: string
  }) {
    super(options.message)
    this.name = 'ApiError'
    this.status = options.status
    this.path = options.path
    this.code = options.code
  }
}

export type ApiRequestOptions = {
  method?: string
  body?: unknown
  signal?: AbortSignal
  headers?: Record<string, string>
}

function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim()
  if (configured && configured.length > 0) {
    return configured.replace(/\/$/, '')
  }
  return '/api'
}

function joinPath(base: string, path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${base}${normalizedPath}`
}

function safeErrorMessage(status: number, fallback?: string): string {
  if (fallback && fallback.trim().length > 0 && fallback.length < 300) {
    return fallback.trim()
  }
  if (status >= 500) {
    return 'The API returned a server error.'
  }
  if (status === 404) {
    return 'The requested resource was not found.'
  }
  if (status >= 400) {
    return 'The API rejected the request.'
  }
  return 'The API request failed.'
}

async function parseErrorBody(
  response: Response,
): Promise<{ message?: string; code?: string }> {
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    return {}
  }

  try {
    const payload: unknown = await response.json()
    if (!payload || typeof payload !== 'object') {
      return {}
    }

    const record = payload as Record<string, unknown>
    const detail = record.detail
    const message =
      typeof record.message === 'string'
        ? record.message
        : typeof detail === 'string'
          ? detail
          : undefined
    const code = typeof record.code === 'string' ? record.code : undefined
    return { message, code }
  } catch {
    return {}
  }
}

export type ApiMultipartRequestOptions = {
  method?: string
  formData: FormData
  signal?: AbortSignal
  headers?: Record<string, string>
}

async function handleApiResponse<T>(
  response: Response,
  path: string,
): Promise<T> {
  if (!response.ok) {
    const parsed = await parseErrorBody(response)
    throw new ApiError({
      status: response.status,
      path,
      code: parsed.code,
      message: safeErrorMessage(response.status, parsed.message),
    })
  }

  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    const text = await response.text()
    if (!text) {
      return undefined as T
    }
    throw new ApiError({
      status: response.status,
      path,
      message: 'The API returned a non-JSON response.',
    })
  }

  return (await response.json()) as T
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const baseUrl = getApiBaseUrl()
  const url = joinPath(baseUrl, path)
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...options.headers,
  }

  let body: string | undefined
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  let response: Response
  try {
    response = await fetch(url, {
      method: options.method ?? 'GET',
      headers,
      body,
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    throw new ApiError({
      status: 0,
      path,
      message: 'Unable to reach the API.',
    })
  }

  return handleApiResponse<T>(response, path)
}

/**
 * Multipart upload helper. Does not set Content-Type so the browser can
 * supply the multipart boundary.
 */
export async function apiMultipartRequest<T>(
  path: string,
  options: ApiMultipartRequestOptions,
): Promise<T> {
  const baseUrl = getApiBaseUrl()
  const url = joinPath(baseUrl, path)
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...options.headers,
  }
  // Intentionally omit Content-Type for FormData.
  delete headers['Content-Type']
  delete headers['content-type']

  let response: Response
  try {
    response = await fetch(url, {
      method: options.method ?? 'POST',
      headers,
      body: options.formData,
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    throw new ApiError({
      status: 0,
      path,
      message: 'Unable to reach the API.',
    })
  }

  return handleApiResponse<T>(response, path)
}

export type ApiBinaryRequestOptions = {
  method?: string
  signal?: AbortSignal
  headers?: Record<string, string>
  /** Expected content-type family, e.g. application/pdf or text/html. */
  accept?: string
}

export type ApiBinaryResult = {
  blob: Blob
  contentType: string
  filename: string | null
  printMode: string | null
}

function parseFilename(disposition: string | null): string | null {
  if (!disposition) {
    return null
  }
  const utfMatch = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
  if (utfMatch?.[1]) {
    try {
      return decodeURIComponent(utfMatch[1].trim())
    } catch {
      return utfMatch[1].trim()
    }
  }
  const plainMatch = /filename="?([^";]+)"?/i.exec(disposition)
  return plainMatch?.[1]?.trim() ?? null
}

/**
 * Binary/HTML export helper. Preserves ApiError normalization for failures.
 * Does not log response bodies.
 */
export async function apiBinaryRequest(
  path: string,
  options: ApiBinaryRequestOptions = {},
): Promise<ApiBinaryResult> {
  const baseUrl = getApiBaseUrl()
  const url = joinPath(baseUrl, path)
  const headers: Record<string, string> = {
    Accept: options.accept ?? '*/*',
    ...options.headers,
  }

  let response: Response
  try {
    response = await fetch(url, {
      method: options.method ?? 'GET',
      headers,
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    throw new ApiError({
      status: 0,
      path,
      message: 'Unable to reach the API.',
    })
  }

  if (!response.ok) {
    const parsed = await parseErrorBody(response)
    throw new ApiError({
      status: response.status,
      path,
      code: parsed.code,
      message: safeErrorMessage(response.status, parsed.message),
    })
  }

  const contentType = response.headers.get('content-type') ?? ''
  const blob = await response.blob()
  return {
    blob,
    contentType,
    filename: parseFilename(response.headers.get('content-disposition')),
    printMode: response.headers.get('x-grievancehub-print-mode'),
  }
}

export function getConfiguredApiBaseUrl(): string {
  return getApiBaseUrl()
}
