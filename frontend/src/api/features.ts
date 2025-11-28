import { FEATURE_ENDPOINTS } from "@/api/endpoints";
import { getBusinessId, getMemberId, getStaffName } from "@/config";

export type Feature = {
  id: string;
  title?: string;
  basicInfo?: {
    title: string;
    description?: string;
    epicId?: string;
    moduleId?: string;
    status?: string;
  };
  problemInfo?: {
    statement?: string;
    objective?: string;
    successCriteria?: string[];
  };
  scope?: {
    inScope?: string[];
    outOfScope?: string[];
  };
  requirements?: {
    functionalRequirements?: {
      requirementId: string;
      priorityLevel: string;
      description: string;
    }[];
    nonFunctionalRequirements?: {
      requirementId: string;
      priorityLevel: string;
      description: string;
    }[];
  };
  riskAndDependencies?: {
    dependencies?: string[];
    risks?: {
      riskId: string;
      problemLevel: string;
      impactLevel: string;
      description: string;
      strategy: string;
      riskOwner?: { id: string; name: string };
    }[];
  };
  goals?: string[];
  painPoints?: string[];
  displayBugNo?: string;
  priority?: string;
  state?: { id: string; name: string };
  assignee?: { id: string; name: string }[];
  label?: { id: string; name: string; color: string }[];
  epic?: { id: string; name: string };
  modules?: { id: string; name: string };
  startDate?: string;
  endDate?: string;
};

export type CreateFeatureRequest = {
  title: string;
  description?: string;
  projectId?: string;
  projectName?: string;
  problemStatement?: string;
  objective?: string;
  successCriteria?: string[];
  goals?: string[];
  painPoints?: string[];
  inScope?: string[];
  outOfScope?: string[];
  functionalRequirements?: {
    requirementId: string;
    priorityLevel: string;
    description: string;
  }[];
  nonFunctionalRequirements?: {
    requirementId: string;
    priorityLevel: string;
    description: string;
  }[];
  dependencies?: string[];
  risks?: {
    riskId: string;
    problemLevel: string;
    impactLevel: string;
    description: string;
    strategy: string;
    riskOwner?: { id: string; name: string };
  }[];
  priority?: string;
  stateId?: string;
  stateName?: string;
  assignees?: { id: string; name: string }[];
  labels?: { id: string; name: string; color: string }[];
  epicId?: string;
  epicName?: string;
  moduleId?: string;
  moduleName?: string;
  startDate?: string;
  endDate?: string;
  createdBy?: { id: string; name: string };
};

export type CreateFeatureResponse = {
  id: string;
  title: string;
  description: string;
  displayBugNo?: string;
  link?: string;
};

export async function createFeature(payload: CreateFeatureRequest): Promise<CreateFeatureResponse> {
  const endpoint = FEATURE_ENDPOINTS.CREATE_FEATURE();

  const res = await fetch(endpoint, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      basicInfo: {
        title: payload.title,
        description: payload.description || "",
        epicId: payload.epicId,
        moduleId: payload.moduleId,
        status: "PLANNING"
      },
      problemInfo: {
        statement: payload.problemStatement || "",
        objective: payload.objective || "",
        successCriteria: payload.successCriteria || []
      },
      scope: {
        inScope: payload.inScope || [],
        outOfScope: payload.outOfScope || []
      },
      requirements: {
        functionalRequirements: payload.functionalRequirements || [],
        nonFunctionalRequirements: payload.nonFunctionalRequirements || []
      },
      riskAndDependencies: {
        dependencies: payload.dependencies || [],
        risks: payload.risks || []
      },
      goals: payload.goals || [],
      painPoints: payload.painPoints || [],
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
    throw new Error(text || `Failed to create feature (${res.status})`);
  }

  return res.json();
}

export async function getFeatures(projectId: string): Promise<Feature[]> {
  const endpoint = FEATURE_ENDPOINTS.GET_FEATURES(projectId);

  const res = await fetch(endpoint, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get features (${res.status})`);
  }

  return res.json();
}
