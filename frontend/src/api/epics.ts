import { EPIC_ENDPOINTS } from "@/api/endpoints";
import { getBusinessId, getMemberId, getStaffName } from "@/config";

export type Epic = {
  id: string;
  title: string;
  description?: string;
  bugNo?: string;
  priority?: string;
  state?: { id: string; name: string };
  assignee?: { id: string; name: string }[];
  label?: { id: string; name: string; color: string }[];
  cycle?: { id: string; name: string };
  startDate?: string;
  endDate?: string;
};

export type CreateEpicRequest = {
  title: string;
  description?: string;
  projectId?: string;
  projectName?: string;
  priority?: string;
  stateId?: string;
  stateName?: string;
  assignees?: { id: string; name: string }[];
  labels?: { id: string; name: string; color: string }[];
  cycleId?: string;
  cycleName?: string;
  startDate?: string;
  endDate?: string;
  estimatedTime?: string;
  createdBy?: { id: string; name: string };
};

export type CreateEpicResponse = {
  id: string;
  title: string;
  description: string;
  bugNo?: string;
  projectId?: string | null;
  state?: string | null;
  priority?: string | null;
  link?: string | null;
};

export async function createEpic(payload: CreateEpicRequest): Promise<CreateEpicResponse> {
  const endpoint = EPIC_ENDPOINTS.CREATE_EPIC();

  const memberId = getMemberId();
  const staffName = getStaffName();
  const businessId = getBusinessId();

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { 
      "Content-Type": "application/json",
      "accept": "application/json"
    },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description || "",
      startDate: payload.startDate,
      endDate: payload.endDate,
      priority: payload.priority || "NONE",
      state: payload.stateId ? {
        id: payload.stateId,
        name: payload.stateName || ""
      } : undefined,
      assignee: payload.assignees || [],
      label: payload.labels || [],
      cycle: payload.cycleId ? {
        id: payload.cycleId,
        name: payload.cycleName || ""
      } : undefined,
      project: {
        id: payload.projectId || "",
        name: payload.projectName || ""
      },
      business: {
        id: businessId,
        name: ""
      },
      createdBy: payload.createdBy || { id: memberId, name: staffName }
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create epic (${res.status})`);
  }

  const data = await res.json();
  return {
    id: data.id,
    title: data.title,
    description: data.description,
    bugNo: data.bugNo,
    projectId: data.projectId ?? null,
    state: data.state?.name ?? null,
    priority: data.priority ?? null,
    link: data.link ?? null,
  };
}

export async function getEpics(projectId: string): Promise<Epic[]> {
  const endpoint = EPIC_ENDPOINTS.GET_EPICS(projectId);

  const res = await fetch(endpoint, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get epics (${res.status})`);
  }

  return res.json();
}
