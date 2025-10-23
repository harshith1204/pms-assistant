import { API_HTTP_URL } from "@/config";

export type CreateCycleRequest = {
  title: string;
  description?: string;
  startDate?: string;
  endDate?: string;
  projectId: string;
  businessId: string;
  createdBy?: {
    id: string;
    name: string;
  };
};

export type CreateCycleResponse = {
  id: string;
  title: string;
  description: string;
  projectId?: string;
  link?: string;
  data?: any;
};

export async function createCycle(payload: CreateCycleRequest): Promise<CreateCycleResponse> {
  const res = await fetch(`${API_HTTP_URL}/project/cycle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create cycle (${res.status})`);
  }
  return res.json();
}

export async function getProjectCycles(businessId: string, projectId: string): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/project/cycle/get-all?businessId=${businessId}&projectId=${projectId}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get cycles (${res.status})`);
  }
  return res.json();
}

export async function deleteCycle(cycleId: string): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/project/cycle?id=${cycleId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to delete cycle (${res.status})`);
  }
  return res.json();
}

export async function getDefaultCycle(): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/project/default-cycle`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get default cycle (${res.status})`);
  }
  return res.json();
}
