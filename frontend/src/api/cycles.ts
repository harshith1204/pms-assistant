import { API_HTTP_URL } from "@/config";

export type Cycle = {
  id: string;
  title: string;
  description?: string;
  startDate?: string;
  endDate?: string;
  projectId?: string;
  link?: string;
};

export type GetAllCyclesResponse = {
  data: Cycle[];
};

// Hardcoded values for now - will be replaced with dynamic loading from parent website later
const getBusinessId = () => {
  return '1eff7f64-09ef-670e-8c7c-2b9676f8dbb6'; // BUSINESS_UUID from .env
};

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

export async function getAllCycles(projectId?: string): Promise<GetAllCyclesResponse> {
  const businessId = getBusinessId();

  const url = new URL('https://stage-project.simpo.ai/project/cycle/get-all');
  url.searchParams.set('businessId', businessId);
  if (projectId) {
    url.searchParams.set('projectId', projectId);
  }

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: { "accept": "application/json" },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to fetch cycles (${res.status})`);
  }

  return res.json();
}

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
