import { WORKITEM_ENDPOINTS } from "@/api/endpoints";

export type CreateWorkItemRequest = {
  title: string;
  description?: string;
  projectIdentifier?: string;
  projectId?: string;
  cycleId?: string;
  subStateId?: string;
  moduleId?: string;
  assignees?: string[];
  labels?: { id: string; name: string; color: string }[];
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
  subStateId?: string;
  moduleId?: string;
  assignees?: { id: string; name: string }[];
  labels?: { id: string; name: string; color: string }[];
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
  const endpoint = WORKITEM_ENDPOINTS.CREATE_WORKITEM();

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description || "",
      project_identifier: payload.projectIdentifier,
      project_id: payload.projectId,
      cycle_id: payload.cycleId,
      sub_state_id: payload.subStateId,
      module_id: payload.moduleId,
      assignees: payload.assignees,
      labels: payload.labels,
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
  const endpoint = WORKITEM_ENDPOINTS.CREATE_WORKITEM();

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description || "",
      project_identifier: payload.projectIdentifier,
      project_id: payload.projectId,
      cycle_id: payload.cycleId,
      sub_state_id: payload.subStateId,
      module_id: payload.moduleId,
      assignees: payload.assignees?.map(a => a.id),
      labels: payload.labels,
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

