import { API_HTTP_URL } from "@/config";

export type CreateWorkItemInput = {
  title: string;
  description?: string;
  projectIdentifier?: string;
  projectId?: string;
  createdBy?: string;
};

export type CreateWorkItemResponse = {
  id: string;
  title: string;
  description: string;
  projectIdentifier?: string;
  sequenceId?: number;
  link?: string | null;
};

export async function createWorkItem(input: CreateWorkItemInput): Promise<CreateWorkItemResponse> {
  const res = await fetch(`${API_HTTP_URL}/work-items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: input.title,
      description: input.description || "",
      project_identifier: input.projectIdentifier,
      project_id: input.projectId,
      created_by: input.createdBy,
    }),
  });
  if (!res.ok) {
    throw new Error(`Failed to create work item (${res.status})`);
  }
  return (await res.json()) as CreateWorkItemResponse;
}

import { API_HTTP_URL } from "@/config";

export type CreateWorkItemRequest = {
  title: string;
  description: string;
  projectId?: string;
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
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create work item (${res.status})`);
  }
  return res.json();
}
