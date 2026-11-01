let activeOrganizationId: number | null = null;
let csrfToken: string | null = null;

function readableCsrfCookie() {
  const cookie = document.cookie.split("; ").find((item) => item.startsWith("vantage_csrf="));
  return cookie ? decodeURIComponent(cookie.slice("vantage_csrf=".length)) : null;
}

export function setActiveOrganizationId(organizationId: number | null) {
  activeOrganizationId = organizationId;
}

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly detail?: unknown) {
    super(message);
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl = import.meta.env.VITE_API_URL ?? "";
  const headers = new Headers(init?.headers);
  const isAuthRequest = path.startsWith("/auth/");
  if (!isAuthRequest && activeOrganizationId !== null) headers.set("X-Organization-ID", String(activeOrganizationId));
  if (init?.method && !["GET", "HEAD", "OPTIONS"].includes(init.method.toUpperCase())) {
    const token = csrfToken || readableCsrfCookie();
    if (token) headers.set("X-CSRF-Token", token);
  }
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const url = path.startsWith("/api/v1/") ? `${apiUrl}${path}` : `${apiUrl}/api/v1${path}`;
  const response = await fetch(url, {
    ...init,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && !isAuthRequest) {
    window.dispatchEvent(new Event("vantage-auth-expired"));
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new ApiError(
      typeof detail === "string" ? detail : detail?.message || `Request failed (${response.status})`,
      response.status,
      detail,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
