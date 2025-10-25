import { MODULE_ENDPOINTS } from "@/api/endpoints";
import { getBusinessId } from "@/config";

export type Module = {
  id: string;
  title: string;
  description?: string;
  projectId?: string;
  subStateId?: string;
  startDate?: string;
  endDate?: string;
  lead?: {
    id: string;
    name: string;
    email?: string;
  };
  members?: {
    id: string;
    name: string;
    email?: string;
  }[];
  createdTimeStamp?: string;
  updatedTimeStamp?: string;
  link?: string;
  // Make properties optional to handle different API response formats
  [key: string]: any;
};

export type GetAllModulesResponse = {
  data: Module[];
};

export type CreateModuleRequest = {
  title: string;
  description?: string;
  projectId?: string;
  subStateId?: string;
  startDate?: string;
  endDate?: string;
  lead?: string;
  members?: string[];
  createdBy?: string;
};

export type CreateModuleWithMembersRequest = {
  title: string;
  description?: string;
  projectId?: string;
  subStateId?: string;
  startDate?: string;
  endDate?: string;
  lead?: { id: string; name: string };
  members?: { id: string; name: string }[];
  createdBy?: string;
};

export type CreateModuleResponse = {
  id: string;
  title: string;
  description: string;
  projectId?: string;
  link?: string;
};

export async function createModule(payload: CreateModuleRequest): Promise<CreateModuleResponse> {
  const endpoint = MODULE_ENDPOINTS.CREATE_MODULE(payload.projectId || "");

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description || "",
      project_id: payload.projectId,
      sub_state_id: payload.subStateId,
      start_date: payload.startDate,
      end_date: payload.endDate,
      lead: payload.lead,
      members: payload.members,
      created_by: payload.createdBy,
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create module (${res.status})`);
  }
  return res.json();
}

export async function getAllModules(projectId: string): Promise<GetAllModulesResponse> {
  const businessId = getBusinessId();
  const endpoint = MODULE_ENDPOINTS.GET_ALL_MODULES();

  const res = await fetch(endpoint, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      projectId: projectId,
      businessId: businessId,
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to fetch modules (${res.status})`);
  }

  const response = await res.json();

  // Handle the response format from the API
  if (response.data && Array.isArray(response.data)) {
    return { data: response.data };
  }

  // Fallback for different response formats
  return {
    data: []
  };
}

export async function createModuleWithMembers(payload: CreateModuleWithMembersRequest): Promise<CreateModuleResponse> {
  const endpoint = MODULE_ENDPOINTS.CREATE_MODULE(payload.projectId || "");

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description || "",
      project_id: payload.projectId,
      sub_state_id: payload.subStateId,
      start_date: payload.startDate,
      end_date: payload.endDate,
      lead: payload.lead?.id,
      members: payload.members?.map(m => m.id),
      created_by: payload.createdBy,
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create module (${res.status})`);
  }
  return res.json();
}
