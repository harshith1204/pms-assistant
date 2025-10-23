import { API_HTTP_URL } from "@/config";

export type ModuleState = {
  id: string;
  name: string;
};

export type ModuleAssignee = {
  id: string;
  name: string;
};

export type ModuleLead = {
  id: string;
  name: string;
};

export type ModuleProject = {
  id: string;
  name: string;
};

export type ModuleBusiness = {
  id: string;
  name: string;
};

export type CreateModuleRequest = {
  title: string;
  description?: string;
  state?: ModuleState;
  lead?: ModuleLead;
  assignee?: ModuleAssignee[];
  startDate?: string;
  endDate?: string;
  business: ModuleBusiness;
  project: ModuleProject;
  createdBy?: {
    id: string;
    name: string;
  };
};

export type CreateModuleResponse = {
  id: string;
  title: string;
  description: string;
  projectId?: string;
  link?: string;
  data?: any;
};

export async function createModule(payload: CreateModuleRequest): Promise<CreateModuleResponse> {
  const res = await fetch(`${API_HTTP_URL}/project/module`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create module (${res.status})`);
  }
  return res.json();
}

export async function getAllModules(payload: any): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/project/module`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get modules (${res.status})`);
  }
  return res.json();
}

export async function deleteModule(moduleId: string): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/project/module?id=${moduleId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to delete module (${res.status})`);
  }
  return res.json();
}

export async function getWorkitemByModule(moduleId: string): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/project/module/id?moduleId=${moduleId}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get work items by module (${res.status})`);
  }
  return res.json();
}
