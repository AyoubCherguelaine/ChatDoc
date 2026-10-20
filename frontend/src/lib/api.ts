const BASE = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"
).replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const TOKEN_KEY = "docuchat_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

export function clearToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export async function api<T = unknown>(
  path: string,
  opts: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers = new Headers(opts.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const isMultipart =
    typeof FormData !== "undefined" && opts.body instanceof FormData;
  if (!isMultipart) headers.set("Content-Type", "application/json");

  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers,
    credentials: "include",
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let msg = text;
    try {
      msg = JSON.parse(text).detail || JSON.parse(text).message || text;
    } catch {
      msg = text || res.statusText;
    }
    throw new ApiError(res.status, msg);
  }

  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as unknown as T;
  }
  return res.json() as Promise<T>;
}

export interface LoginPayload {
  email: string;
  password: string;
}
export interface RegisterPayload extends LoginPayload {
  name: string;
}

export interface AuthResponse {
  accessToken: string;
  user: import("./types").User;
}

export function login(p: LoginPayload) {
  return api<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(p),
  });
}

export function register(p: RegisterPayload) {
  return api<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(p),
  });
}

export function fetchMe() {
  return api<import("./types").User>("/auth/me", { method: "GET" });
}

export function fetchDocuments() {
  return api<import("./types").Document[]>("/documents", { method: "GET" });
}

export function uploadDocument(file: File) {
  const form = new FormData();
  form.append("file", file);
  return api<{
    id: string;
    filename: string;
    pageCount: number;
    chunkCount: number;
  }>("/documents/upload", { method: "POST", body: form });
}

export function fetchDocumentSessions(docId: string) {
  return api<import("./types").ChatSession[]>(`/documents/${docId}/sessions`, {
    method: "GET",
  });
}

export function createSession(documentId: string, title?: string) {
  return api<{ id: string; title: string; documentId: string }>(`/sessions`, {
    method: "POST",
    body: JSON.stringify({ documentId, title }),
  });
}

export function fetchSession(id: string) {
  return api<{
    id: string;
    title: string;
    document: import("./types").Document;
    messages: import("./types").Message[];
  }>(`/sessions/${id}`, { method: "GET" });
}

export async function* streamChat(
  sessionId: string,
  message: string,
  mode: import("./types").ChatMode = "conversational",
  options: {
    model?: string;
    responseStyle?: string;
    signal?: AbortSignal;
  } = {},
): AsyncGenerator<string, void, unknown> {
  const token = getToken();
  const res = await fetch(`${BASE}/sessions/${sessionId}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token ?? ""}`,
    },
    body: JSON.stringify({
      message,
      mode,
      model: options.model,
      responseStyle: options.responseStyle,
    }),
    signal: options.signal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || res.statusText);
  }

  if (!res.body) return;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      yield decoder.decode(value, { stream: true });
    }
    const tail = decoder.decode();
    if (tail) yield tail;
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export function fetchCapabilities() {
  return api<{
    models: string[];
    defaultModel: string;
    formats: string[];
    maxUploadMB: number;
  }>("/capabilities");
}
export function fetchPage(documentId: string, page: number) {
  return api<{
    page: number;
    totalPages: number;
    text: string;
    filename: string;
  }>(`/documents/${documentId}/pages/${page}`);
}

export function fetchSessions() {
  return api<import("./types").ChatSession[]>("/sessions");
}
