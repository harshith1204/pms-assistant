import { API_HTTP_URL } from "@/config";
import { CYCLE_ENDPOINTS } from "@/api/endpoints";
import { getBusinessId } from "@/config";

export type Cycle = {
  id: string;
  title: string;
  description?: string;
  startDate?: string;
  endDate?: string;
  projectId?: string;
  status: "UPCOMING" | "ACTIVE" | "COMPLETED";
  createdTimeStamp: string;
  updatedTimeStamp: string;
  completionPercentage: number;
  default: boolean;
  favourite: boolean;
  business?: {
    id: string;
    name?: string;
  };
  project?: {
    id: string;
    name?: string;
  };
  // Make properties optional to handle different API response formats
  [key: string]: any;
};

export type CyclesByStatus = {
  UPCOMING: Cycle[];
  ACTIVE: Cycle[];
  COMPLETED: Cycle[];
};

export type GetAllCyclesResponse = {
  data: CyclesByStatus;
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
  const endpoint = CYCLE_ENDPOINTS.GET_ALL_CYCLES(businessId, projectId);

  const res = await fetch(endpoint, {
    method: "GET",
    headers: { "accept": "application/json" },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to fetch cycles (${res.status})`);
  }

  const response = await res.json();

  // Handle the grouped response format from the API
  if (response.data && typeof response.data === 'object') {
    const cyclesByStatus: CyclesByStatus = {
      UPCOMING: Array.isArray(response.data.UPCOMING) ? response.data.UPCOMING : [],
      ACTIVE: Array.isArray(response.data.ACTIVE) ? response.data.ACTIVE : [],
      COMPLETED: Array.isArray(response.data.COMPLETED) ? response.data.COMPLETED : []
    };
    return { data: cyclesByStatus };
  }

  // Fallback for different response formats
  return {
    data: {
      UPCOMING: [],
      ACTIVE: [],
      COMPLETED: []
    }
  };
}

// Helper function to get all cycles as a flat array (for backward compatibility)
export function getAllCyclesAsArray(cyclesResponse: GetAllCyclesResponse): Cycle[] {
  const { data } = cyclesResponse;
  return [
    ...data.UPCOMING,
    ...data.ACTIVE,
    ...data.COMPLETED
  ];
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
