import type { ApiResource } from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function getResource<T>(path: string, signal?: AbortSignal): Promise<ApiResource<T>> {
  const response = await fetch(path, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal
  });
  if (!response.ok) {
    throw new ApiError(`Local API returned HTTP ${response.status}.`, response.status);
  }
  return (await response.json()) as ApiResource<T>;
}

export async function postResource<TResponse, TBody>(path: string, body: TBody): Promise<ApiResource<TResponse>> {
  const response = await fetch(path, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: { message?: string } } | null;
    throw new ApiError(payload?.detail?.message || `Local API returned HTTP ${response.status}.`, response.status);
  }
  return (await response.json()) as ApiResource<TResponse>;
}
