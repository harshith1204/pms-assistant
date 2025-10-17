import { getToken } from "@/auth/token";
import { API_HTTP_URL } from "@/config";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type RequestOptions = {
  method?: HttpMethod;
  headers?: Record<string, string>;
  body?: any;
  // If true, don't attach Authorization header
  anonymous?: boolean;
};

export async function http(path: string, options: RequestOptions = {}) {
  const url = path.startsWith("http") ? path : `${API_HTTP_URL}${path.startsWith("/") ? "" : "/"}${path}`;

  const headers: Record<string, string> = {
    ...(options.headers || {}),
  };

  if (!options.anonymous) {
    const token = getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  const init: RequestInit = {
    method: options.method || (options.body ? "POST" : "GET"),
    headers,
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
