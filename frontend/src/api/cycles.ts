import { API_HTTP_URL } from "@/config";

export type CreateCycleRequest = {
  title: string;
  description?: string;
  projectId?: string;
  startDate?: string;
  endDate?: string;
  createdBy?: string;
};

export type CreateCycleResponse = {
  id: string;
  title: string;
  description: string;
  projectId?: string;
  link?: string;
};

export async function createCycle(payload: CreateCycleRequest): Promise<CreateCycleResponse> {
  const res = await fetch(`${API_HTTP_URL}/cycles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description || "",
      project_id: payload.projectId,
      start_date: payload.startDate,
      end_date: payload.endDate,
      created_by: payload.createdBy,
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create cycle (${res.status})`);
  }
  return res.json();
}
