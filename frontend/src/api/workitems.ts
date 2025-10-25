import { API_HTTP_URL } from "@/config";

export type CreateWorkItemRequest = {
  title: string;
  description?: string;
  projectIdentifier?: string;
  projectId?: string;
  cycleId?: string;
  assignees?: string[];
  startDate?: string;
  endDate?: string;
  createdBy?: string;
};

export type CreateWorkItemWithMembersRequest = {
  title: string;
  description?: string;
  projectIdentifier?: string;
  projectId?: string;
  cycleId?: string;
  assignees?: { id: string; name: string }[];
  startDate?: string;
  endDate?: string;
  createdBy?: string;
};

export type CreateWorkItemResponse = {
  id: string;
  title: string;
  description: string;
  projectIdentifier?: string;
  sequenceId?: string | number;
  link?: string;
};

export async function createWorkItem(payload: CreateWorkItemRequest): Promise<CreateWorkItemResponse> {
  const res = await fetch(`${API_HTTP_URL}/work-items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description || "",
      project_identifier: payload.projectIdentifier,
      project_id: payload.projectId,
      cycle_id: payload.cycleId,
      assignees: payload.assignees,
      start_date: payload.startDate,
      end_date: payload.endDate,
      created_by: payload.createdBy,
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create work item (${res.status})`);
  }
  return res.json();
}

export async function createWorkItemWithMembers(payload: CreateWorkItemWithMembersRequest): Promise<CreateWorkItemResponse> {
  const res = await fetch(`${API_HTTP_URL}/work-items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description || "",
      project_identifier: payload.projectIdentifier,
      project_id: payload.projectId,
      cycle_id: payload.cycleId,
      assignees: payload.assignees?.map(a => a.id),
      start_date: payload.startDate,
      end_date: payload.endDate,
      created_by: payload.createdBy,
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create work item (${res.status})`);
  }
  return res.json();
}

