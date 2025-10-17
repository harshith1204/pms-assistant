import { API_HTTP_URL } from "@/config";
import { http } from "@/api/http";

export async function createSession(token: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_HTTP_URL}/auth/session`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function logout(): Promise<boolean> {
  try {
    const res = await http(`/auth/logout`, { method: "POST", anonymous: true });
    return res.ok;
  } catch {
    return false;
  }
}
