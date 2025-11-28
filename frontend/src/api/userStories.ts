import { USER_STORY_ENDPOINTS, EPIC_ENDPOINTS } from "@/api/endpoints";
import { getBusinessId, getMemberId, getStaffName } from "@/config";

export type UserStory = {
  id: string;
  title: string;
  description?: string;
  displayBugNo?: string;
  userGoal?: string;
  persona?: string;
  demographics?: string;
  acceptanceCriteria?: string;
  priority?: string;
  state?: { id: string; name: string };
  assignee?: { id: string; name: string }[];
  label?: { id: string; name: string; color: string }[];
  epic?: { id: string; name: string };
  feature?: { id: string; name: string };
  modules?: { id: string; name: string };
  startDate?: string;
  endDate?: string;
};

export type CreateUserStoryRequest = {
  title: string;
  description?: string;
  projectId?: string;
  projectName?: string;
  userGoal?: string;
  persona?: string;
  demographics?: string;
  acceptanceCriteria?: string;
  priority?: string;
  stateId?: string;
  stateName?: string;
  assignees?: { id: string; name: string }[];
  labels?: { id: string; name: string; color: string }[];
  epicId?: string;
  epicName?: string;
  featureId?: string;
  featureName?: string;
  moduleId?: string;
  moduleName?: string;
  startDate?: string;
  endDate?: string;
  createdBy?: { id: string; name: string };
};

export type CreateUserStoryResponse = {
  id: string;
  title: string;
  description: string;
  displayBugNo?: string;
  link?: string;
};

export async function createUserStory(payload: CreateUserStoryRequest): Promise<CreateUserStoryResponse> {
  const endpoint = USER_STORY_ENDPOINTS.CREATE_USER_STORY();

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description || "",
      userGoal: payload.userGoal || "",
      persona: payload.persona || "",
      demographics: payload.demographics || "",
      acceptanceCriteria: payload.acceptanceCriteria || "",
      priority: payload.priority || "NONE",
      startDate: payload.startDate,
      endDate: payload.endDate,
      state: payload.stateId ? {
        id: payload.stateId,
        name: payload.stateName || ""
      } : undefined,
      assignee: payload.assignees || [],
      label: payload.labels || [],
      epic: payload.epicId ? {
        id: payload.epicId,
        name: payload.epicName || ""
      } : undefined,
      feature: payload.featureId ? {
        id: payload.featureId,
        name: payload.featureName || ""
      } : undefined,
      modules: payload.moduleId ? {
        id: payload.moduleId,
        name: payload.moduleName || ""
      } : undefined,
      project: {
        id: payload.projectId || "",
        name: payload.projectName || ""
      },
      business: {
        id: getBusinessId(),
        name: ""
      },
      createdBy: payload.createdBy || { id: getMemberId(), name: getStaffName() }
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create user story (${res.status})`);
  }

  return res.json();
}

export async function getUserStories(projectId: string): Promise<UserStory[]> {
  const endpoint = USER_STORY_ENDPOINTS.GET_USER_STORIES(projectId);

  const res = await fetch(endpoint, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get user stories (${res.status})`);
  }

  return res.json();
}
