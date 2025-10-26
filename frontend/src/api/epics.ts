import { API_HTTP_URL } from \"@/config\";
import { getBusinessId, getMemberId } from \"@/config\";

export type Epic = {
  id: string;
  title: string;
  description?: string;
  projectId?: string;
  status: \"NEW\" | \"IN_PROGRESS\" | \"COMPLETED\" | \"CANCELLED\";
  priority: \"LOW\" | \"MEDIUM\" | \"HIGH\" | \"URGENT\";
  startDate?: string;
  endDate?: string;
  createdTimeStamp: string;
  updatedTimeStamp: string;
  business?: {
    id: string;
    name?: string;
  };
  project?: {
    id: string;
    name?: string;
  };
  assignee?: {
    id: string;
    name?: string;
  };
  label?: Array<{
    id: string;
    name: string;
    color: string;
  }>;
  // Make properties optional to handle different API response formats
  [key: string]: any;
};

export type EpicsByStatus = {
  NEW: Epic[];
  IN_PROGRESS: Epic[];
  COMPLETED: Epic[];
  CANCELLED: Epic[];
};

export type GetAllEpicsResponse = {
  data: EpicsByStatus;
};

export type CreateEpicRequest = {
  title: string;
  description?: string;
  projectId?: string;
  status?: string;
  priority?: string;
  startDate?: string;
  endDate?: string;
};

export type CreateEpicResponse = {
  id: string;
  title: string;
  description: string;
  projectId?: string;
  link?: string;
};

export async function getAllEpics(projectId?: string): Promise<GetAllEpicsResponse> {
  const businessId = getBusinessId();
  const url = new URL(`${API_HTTP_URL}/epics`);
  url.searchParams.set('businessId', businessId);
  if (projectId) {
    url.searchParams.set('projectId', projectId);
  }

  const res = await fetch(url.toString(), {
    method: \"GET\",
    headers: { \"accept\": \"application/json\" },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => \"\");
    throw new Error(text || `Failed to fetch epics (${res.status})`);
  }

  const response = await res.json();

  // Handle the grouped response format from the API
  if (response.data && typeof response.data === 'object') {
    const epicsByStatus: EpicsByStatus = {
      NEW: Array.isArray(response.data.NEW) ? response.data.NEW : [],
      IN_PROGRESS: Array.isArray(response.data.IN_PROGRESS) ? response.data.IN_PROGRESS : [],
      COMPLETED: Array.isArray(response.data.COMPLETED) ? response.data.COMPLETED : [],
      CANCELLED: Array.isArray(response.data.CANCELLED) ? response.data.CANCELLED : []
    };
    return { data: epicsByStatus };
  }

  // Fallback for different response formats
  return {
    data: {
      NEW: [],
      IN_PROGRESS: [],
      COMPLETED: [],
      CANCELLED: []
    }
  };
}

// Helper function to get all epics as a flat array (for backward compatibility)
export function getAllEpicsAsArray(epicsResponse: GetAllEpicsResponse): Epic[] {
  const { data } = epicsResponse;
  return [
    ...data.NEW,
    ...data.IN_PROGRESS,
    ...data.COMPLETED,
    ...data.CANCELLED
  ];
}

export async function createEpic(payload: CreateEpicRequest): Promise<CreateEpicResponse> {
  const endpoint = `${API_HTTP_URL}/epics`;

  const res = await fetch(endpoint, {
    method: \"POST\",
    headers: { \"Content-Type\": \"application/json\" },
    body: JSON.stringify({
      projectId: payload.projectId,
      businessId: getBusinessId(),
      title: payload.title,
      description: payload.description || \"\",
      status: payload.status || \"NEW\",
      priority: payload.priority || \"MEDIUM\",
      startDate: payload.startDate,
      endDate: payload.endDate,
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => \"\");
    throw new Error(text || `Failed to create epic (${res.status})`);
  }
  return res.json();
}