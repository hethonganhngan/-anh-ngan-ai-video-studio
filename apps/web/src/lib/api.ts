/** API client: cookie httpOnly + CSRF double-submit, lỗi chuẩn hoá {code, message, details}. */
declare global {
  interface Window { __ANNGAN_API_URL__?: string }
}

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function apiBase(): string {
  if (typeof window !== "undefined" && window.__ANNGAN_API_URL__ !== undefined) return window.__ANNGAN_API_URL__;
  return process.env.NEXT_PUBLIC_API_URL ?? "";
}

function csrf(): string | undefined {
  if (typeof document === "undefined") return undefined;
  return document.cookie.split("; ").find((c) => c.startsWith("an_csrf="))?.split("=")[1];
}

type Opts = { method?: string; body?: unknown; form?: FormData; headers?: Record<string, string>; raw?: boolean };

export async function api<T = unknown>(path: string, opts: Opts = {}): Promise<T> {
  const method = opts.method ?? (opts.body !== undefined || opts.form ? "POST" : "GET");
  const headers: Record<string, string> = { ...(opts.headers ?? {}) };
  if (method !== "GET") {
    const t = csrf();
    if (t) headers["X-CSRF-Token"] = t;
  }
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(`${apiBase()}/api/v1${path}`, { method, headers, body, credentials: "include" });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Không kết nối được máy chủ API. Kiểm tra mạng hoặc dịch vụ backend.");
  }
  if (opts.raw) return res as unknown as T;
  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    const err = (data as { error?: { code?: string; message?: string; details?: unknown } } | null)?.error;
    throw new ApiError(res.status, err?.code ?? `HTTP_${res.status}`, err?.message ?? `Lỗi ${res.status}`, err?.details);
  }
  return data as T;
}

function safeJson(t: string) {
  try { return JSON.parse(t); } catch { return t; }
}

export const assetUrl = (id: string | null | undefined, download = false) =>
  id ? `${apiBase()}/api/v1/assets/${id}/content${download ? "?download=true" : ""}` : "";

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    const d = e.details;
    if (Array.isArray(d) && d.length && typeof d[0] === "object" && d[0] && "message" in d[0]) {
      return `${e.message}: ${(d as { field?: string; message: string }[]).map((x) => (x.field ? `${x.field} — ${x.message}` : x.message)).join("; ")}`;
    }
    if (d && typeof d === "object" && "errors" in d && Array.isArray((d as { errors: unknown[] }).errors)) {
      return `${e.message}: ${(d as { errors: string[] }).errors.join("; ")}`;
    }
    if (Array.isArray(d) && d.length && typeof d[0] === "string") return `${e.message}: ${d.join("; ")}`;
    return e.message;
  }
  return e instanceof Error ? e.message : "Đã có lỗi xảy ra";
}
