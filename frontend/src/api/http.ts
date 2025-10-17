import { API_HTTP_URL } from "@/config";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type RequestOptions = {
  method?: HttpMethod;
  headers?: Record<string, string>;
  body?: any;
  // If true, skip CSRF header
  anonymous?: boolean;
};

export async function http(path: string, options: RequestOptions = {}) {
  const url = path.startsWith("http") ? path : `${API_HTTP_URL}${path.startsWith("/") ? "" : "/"}${path}`;

  const headers: Record<string, string> = {
    ...(options.headers || {}),
  };

  // Add CSRF header for state-changing requests when available (double-submit cookie)
  if (!options.anonymous) {
    const method = (options.method || (options.body ? "POST" : "GET")).toUpperCase();
    if (method !== "GET" && method !== "HEAD") {
      try {
        const csrf = getCookie("csrf");
        if (csrf && !headers["X-CSRF-Token"]) headers["X-CSRF-Token"] = csrf;
      } catch {}
    }
  }

  const init: RequestInit = {
    method: options.method || (options.body ? "POST" : "GET"),
    headers,
    credentials: "include",
  };

  if (options.body !== undefined) {
    if (typeof options.body === "string") {
      init.body = options.body;
    } else {
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
      init.body = JSON.stringify(options.body);
    }
  }

  const res = await fetch(url, init);
  return res;
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = document.cookie
    .split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith(name + "="));
  return value ? decodeURIComponent(value.split("=")[1]) : null;
}
