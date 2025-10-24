import { API_HTTP_URL } from "@/config";

export type CreateModuleRequest = {
  title: string;
  description?: string;
  projectId?: string;
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
  const res = await fetch(`${API_HTTP_URL}/modules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description || "",
      project_id: payload.projectId,
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

export async function createModuleWithMembers(payload: CreateModuleWithMembersRequest): Promise<CreateModuleResponse> {
  const res = await fetch(`${API_HTTP_URL}/modules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description || "",
      project_id: payload.projectId,
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
