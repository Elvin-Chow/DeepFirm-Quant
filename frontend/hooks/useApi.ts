import { API_BASE_URL } from "@/lib/constants";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

const DEFAULT_GET_TIMEOUT_MS = 45_000;
const DEFAULT_POST_TIMEOUT_MS = 240_000;

function requestTimeoutMs(defaultTimeoutMs: number): number {
  const rawValue = process.env.NEXT_PUBLIC_API_TIMEOUT_MS;
  const parsed = rawValue ? Number(rawValue) : defaultTimeoutMs;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : defaultTimeoutMs;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
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
    return new ApiError(
      0,
      "The hosted API did not return a valid response. Please retry shortly."
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
