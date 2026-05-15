import { API_BASE_URL, DEFAULT_API_BASE_URL_IN_USE } from "@/lib/constants";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

const DEFAULT_GET_TIMEOUT_MS = 45_000;
const DEFAULT_POST_TIMEOUT_MS = 240_000;
const DEFAULT_HEALTH_TIMEOUT_MS = 2_500;

function requestTimeoutMs(defaultTimeoutMs: number): number {
  const rawValue = process.env.NEXT_PUBLIC_API_TIMEOUT_MS;
  const parsed = rawValue ? Number(rawValue) : defaultTimeoutMs;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : defaultTimeoutMs;
}

function healthTimeoutMs(): number {
  const rawValue = process.env.NEXT_PUBLIC_API_HEALTH_TIMEOUT_MS;
  const parsed = rawValue ? Number(rawValue) : DEFAULT_HEALTH_TIMEOUT_MS;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_HEALTH_TIMEOUT_MS;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function isHostedFrontend(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return !["localhost", "127.0.0.1"].includes(window.location.hostname);
}

function normalizeFetchError(error: unknown, timedOut: boolean): Error {
  if (error instanceof ApiError) {
    return error;
  }
  if (timedOut || isAbortError(error)) {
    return new ApiError(
      408,
      "The analysis request timed out while waiting for the hosted API. Please retry shortly."
    );
  }
  if (error instanceof TypeError) {
    if (DEFAULT_API_BASE_URL_IN_USE && isHostedFrontend()) {
      return new ApiError(
        0,
        "The hosted frontend is pointing to the local API. Set NEXT_PUBLIC_API_BASE_URL to the hosted API URL and redeploy."
      );
    }
    return new ApiError(
      0,
      "The hosted API did not return a valid browser response. Check the API URL and CORS configuration, then retry shortly."
    );
  }
  return error instanceof Error ? error : new Error("Request failed.");
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
  externalSignal?: AbortSignal
): Promise<Response> {
  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const abortFromExternalSignal = () => controller.abort();

  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort();
    } else {
      externalSignal.addEventListener("abort", abortFromExternalSignal, { once: true });
    }
  }

  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    throw normalizeFetchError(error, timedOut);
  } finally {
    clearTimeout(timeoutId);
    externalSignal?.removeEventListener("abort", abortFromExternalSignal);
  }
}

async function parseResponseError(response: Response): Promise<ApiError> {
  const text = await response.text();
  let message = text || `HTTP ${response.status}`;
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed?.detail === "string") {
      message = parsed.detail;
    }
  } catch {
    message = text || `HTTP ${response.status}`;
  }
  return new ApiError(response.status, message);
}

export async function postApi<T>(endpoint: string, payload: object): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetchWithTimeout(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  }, requestTimeoutMs(DEFAULT_POST_TIMEOUT_MS));

  if (!response.ok) {
    throw await parseResponseError(response);
  }

  return response.json() as Promise<T>;
}

export async function getApi<T>(endpoint: string, signal?: AbortSignal): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetchWithTimeout(
    url,
    { cache: "no-store" },
    requestTimeoutMs(DEFAULT_GET_TIMEOUT_MS),
    signal
  );

  if (!response.ok) {
    throw await parseResponseError(response);
  }

  return response.json() as Promise<T>;
}

export async function checkApiHealth(signal?: AbortSignal): Promise<void> {
  const response = await fetchWithTimeout(
    `${API_BASE_URL}/health?_ts=${Date.now()}`,
    {
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    },
    healthTimeoutMs(),
    signal
  );

  if (!response.ok) {
    throw await parseResponseError(response);
  }

  const payload = await response.json().catch(() => null) as { status?: unknown } | null;
  if (payload?.status !== "ok") {
    throw new ApiError(502, "Backend health response is not ok.");
  }
}
