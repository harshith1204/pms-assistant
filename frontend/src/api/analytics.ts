import { API_HTTP_URL } from "@/config";

export type SelectResponse =
  | { type: "dashboard_embed_url"; dashboard_id: number; embed_url: string; params?: Record<string, any> }
  | { type: "table_preview_fallback"; reason?: string; alternatives?: number[]; columns?: string[]; rows?: any[][] };

export async function selectDashboard(prompt: string, params?: Record<string, any>): Promise<SelectResponse> {
  const res = await fetch(`${API_HTTP_URL}/analytics/select`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, params }),
  });
  if (!res.ok) {
    throw new Error(`Select failed: ${res.status}`);
  }
  return res.json();
}
