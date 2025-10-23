import { API_HTTP_URL } from "@/config";

export type WorkItemState = {
  id: string;
  name: string;
};

export type WorkItemAssignee = {
  id: string;
  name: string;
};

export type WorkItemLabel = {
  id: string;
  name: string;
};

export type WorkItemProject = {
  id: string;
  name: string;
};

export type WorkItemBusiness = {
  id: string;
  name: string;
};

export type WorkItemModule = {
  id: string;
  name: string;
};

export type WorkItemCycle = {
  id: string;
  name: string;
};

export type WorkItemParent = {
  id: string;
  name: string;
};

export type CreateWorkItemRequest = {
  title: string;
  description?: string;
  startDate?: string;
  endDate?: string;
  label?: WorkItemLabel[];
  state?: WorkItemState;
  priority?: string;
  estimate?: any;
  estimateSystem?: string;
  status?: string;
  assignee?: WorkItemAssignee[];
  modules?: WorkItemModule;
  cycle?: WorkItemCycle;
  parent?: WorkItemParent;
  project: WorkItemProject;
  business: WorkItemBusiness;
  createdBy: {
    id: string;
    name: string;
  };
};

export type CreateWorkItemResponse = {
  id: string;
  title: string;
  description: string;
  projectId?: string;
  link?: string;
  data?: any;
};

export async function createWorkItem(payload: CreateWorkItemRequest): Promise<CreateWorkItemResponse> {
  const res = await fetch(`${API_HTTP_URL}/project/work-item`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create work item (${res.status})`);
  }
  return res.json();
}

export async function getAllWorkItems(payload: any): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/project/workItem`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get work items (${res.status})`);
  }
  return res.json();
}

export async function updateWorkItem(payload: any): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/project/work-item`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to update work item (${res.status})`);
  }
  return res.json();
}

export async function deleteWorkItem(workItemId: string): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/project/workItem?id=${workItemId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to delete work item (${res.status})`);
  }
  return res.json();
}

