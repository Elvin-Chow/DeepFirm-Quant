import { API_BASE_URL } from "@/lib/constants";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function postApi<T>(endpoint: string, payload: object): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
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
    throw new ApiError(response.status, message);
  }

  return response.json() as Promise<T>;
}
