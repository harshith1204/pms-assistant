import { API_HTTP_URL } from "@/config";

export type ProjectMember = {
  id: string;
  name: string;
  memberId?: string;
};

export type ProjectState = {
  id: string;
  name: string;
  subStates?: ProjectSubState[];
};

export type ProjectSubState = {
  id: string;
  name: string;
  stateName?: string;
  stateId?: string;
};

export type ProjectLabel = {
  id: string;
  name: string;
};

export type ProjectSettings = {
  projectId: string;
  businessId: string;
  states?: ProjectState[];
  labels?: ProjectLabel[];
  members?: ProjectMember[];
};

export async function getProjectSettings(projectId: string, businessId: string): Promise<ProjectSettings> {
  const res = await fetch(`${API_HTTP_URL}/project/setting?projectId=${projectId}&businessId=${businessId}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get project settings (${res.status})`);
  }
  return res.json();
}

export async function getAllMembers(projectId: string): Promise<{ data: ProjectMember[] }> {
  const res = await fetch(`${API_HTTP_URL}/project/${projectId}/member`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get project members (${res.status})`);
  }
  return res.json();
}

export async function getAllLabels(projectId: string): Promise<{ data: ProjectLabel[] }> {
  const res = await fetch(`${API_HTTP_URL}/project/${projectId}/label`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get labels (${res.status})`);
  }
  return res.json();
}

export async function getAllSubStatesList(projectId: string): Promise<{ data: ProjectState[] }> {
  const res = await fetch(`${API_HTTP_URL}/project/states/${projectId}/sub-states`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get sub-states (${res.status})`);
  }
  return res.json();
}

export async function getEstimation(projectId: string): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/project/${projectId}/estimation`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get estimation (${res.status})`);
  }
  return res.json();
}

export async function getAllEpicProperties(projectId: string): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/project/epic/getAll-property?projectId=${projectId}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get epic properties (${res.status})`);
  }
  return res.json();
}