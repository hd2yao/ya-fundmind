import type {
  ApiResource,
  FundDetailResponse,
  FundHistoryResponse,
  FundHistoryWindow,
  FundSearchParams,
  FundSearchResponse
} from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function parseResource<T>(payload: unknown): ApiResource<T> {
  if (
    payload === null ||
    typeof payload !== "object" ||
    !("data" in payload) ||
    payload.data === null ||
    typeof payload.data !== "object" ||
    !("availability" in payload) ||
    (payload.availability !== "available" && payload.availability !== "missing")
  ) {
    throw new ApiError("Local API returned an invalid resource payload.", 502);
  }
  return payload as ApiResource<T>;
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
  return parseResource<T>(await response.json());
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
  return parseResource<TResponse>(await response.json());
}

export async function searchFunds(
  params: FundSearchParams = {},
  signal?: AbortSignal
): Promise<FundSearchResponse> {
  const query = new URLSearchParams();
  appendQuery(query, "q", params.q);
  appendQuery(query, "fund_type", params.fundType);
  appendQuery(query, "theme", params.theme);
  appendQuery(query, "exchange_traded", params.exchangeTraded);
  appendQuery(query, "quality", params.quality);
  appendQuery(query, "sort", params.sort);
  appendQuery(query, "direction", params.direction);
  appendQuery(query, "page", params.page);
  appendQuery(query, "page_size", params.pageSize);
  const suffix = query.size ? `?${query.toString()}` : "";
  const payload = await getJson<FundSearchResponse>(`/api/funds/search${suffix}`, signal);
  if (!Array.isArray(payload.items) || typeof payload.total !== "number") {
    throw new ApiError("Local API returned an invalid fund search payload.", 502);
  }
  return payload;
}

export async function getFundDetail(code: string, signal?: AbortSignal): Promise<FundDetailResponse> {
  const payload = await getJson<FundDetailResponse>(`/api/funds/${encodeURIComponent(code)}`, signal);
  if (!payload.fund || typeof payload.fund !== "object" || !payload.fund.code) {
    throw new ApiError("Local API returned an invalid fund detail payload.", 502);
  }
  return payload;
}

export async function getFundHistory(
  code: string,
  window: FundHistoryWindow = "6m",
  signal?: AbortSignal
): Promise<FundHistoryResponse> {
  const payload = await getJson<FundHistoryResponse>(
    `/api/funds/${encodeURIComponent(code)}/history?range=${encodeURIComponent(window)}`,
    signal
  );
  if (
    payload.code !== code ||
    !Array.isArray(payload.points) ||
    typeof payload.point_count !== "number"
  ) {
    throw new ApiError("Local API returned an invalid fund history payload.", 502);
  }
  return payload;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: { message?: string } } | null;
    throw new ApiError(payload?.detail?.message || `Local API returned HTTP ${response.status}.`, response.status);
  }
  const payload = (await response.json()) as T;
  if (payload === null || typeof payload !== "object") {
    throw new ApiError("Local API returned an invalid JSON payload.", 502);
  }
  return payload;
}

function appendQuery(
  query: URLSearchParams,
  key: string,
  value: string | number | boolean | undefined
): void {
  if (value === undefined || value === "") return;
  query.set(key, String(value));
}
