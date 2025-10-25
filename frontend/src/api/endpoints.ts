import { STAGE_API_BASE_URL } from "@/config";

/**
 * Centralized API endpoints configuration
 * All API URLs are defined here for easy management and updates
 */

export const PROJECT_ENDPOINTS = {
  // Get projects for a member
  GET_PROJECTS: (businessId: string, memberId: string) =>
    `${STAGE_API_BASE_URL}/project/memberId?businessId=${businessId}&memberId=${memberId}`,

  // Get project members
  GET_PROJECT_MEMBERS: (projectId: string) =>
    `${STAGE_API_BASE_URL}/project/${projectId}/member`,

  // Create project (if needed in future)
  CREATE_PROJECT: () =>
    `${STAGE_API_BASE_URL}/project`,

  // Update project (if needed in future)
  UPDATE_PROJECT: (projectId: string) =>
    `${STAGE_API_BASE_URL}/project/${projectId}`,

  // Delete project (if needed in future)
  DELETE_PROJECT: (projectId: string) =>
    `${STAGE_API_BASE_URL}/project/${projectId}`,
};

export const CYCLE_ENDPOINTS = {
  // Get all cycles
  GET_ALL_CYCLES: (businessId: string, projectId?: string) => {
    const url = new URL(`${STAGE_API_BASE_URL}/project/cycle/get-all`);
    url.searchParams.set('businessId', businessId);
    if (projectId) {
      url.searchParams.set('projectId', projectId);
    }
    return url.toString();
  },

  // Create cycle (if needed in future)
  CREATE_CYCLE: () =>
    `${STAGE_API_BASE_URL}/project/cycle`,

  // Update cycle (if needed in future)
  UPDATE_CYCLE: (cycleId: string) =>
    `${STAGE_API_BASE_URL}/project/cycle/${cycleId}`,

  // Delete cycle (if needed in future)
  DELETE_CYCLE: (cycleId: string) =>
    `${STAGE_API_BASE_URL}/project/cycle/${cycleId}`,
};

export const WORKITEM_ENDPOINTS = {
  // Create work item (if needed in future)
  CREATE_WORKITEM: () =>
    `${STAGE_API_BASE_URL}/work-item`,

  // Get work items (if needed in future)
  GET_WORKITEMS: (projectId: string) =>
    `${STAGE_API_BASE_URL}/project/${projectId}/work-items`,

  // Update work item (if needed in future)
  UPDATE_WORKITEM: (workItemId: string) =>
    `${STAGE_API_BASE_URL}/work-item/${workItemId}`,

  // Delete work item (if needed in future)
  DELETE_WORKITEM: (workItemId: string) =>
    `${STAGE_API_BASE_URL}/work-item/${workItemId}`,
};

export const MODULE_ENDPOINTS = {
  // Get all modules
  GET_ALL_MODULES: (businessId: string, projectId?: string) => {
    const url = new URL(`${STAGE_API_BASE_URL}/project/module/get-all`);
    url.searchParams.set('businessId', businessId);
    if (projectId) {
      url.searchParams.set('projectId', projectId);
    }
    return url.toString();
  },

  // Create module (if needed in future)
  CREATE_MODULE: (projectId: string) =>
    `${STAGE_API_BASE_URL}/project/${projectId}/modules`,

  // Update module (if needed in future)
  UPDATE_MODULE: (projectId: string, moduleId: string) =>
    `${STAGE_API_BASE_URL}/project/${projectId}/modules/${moduleId}`,

  // Delete module (if needed in future)
  DELETE_MODULE: (projectId: string, moduleId: string) =>
    `${STAGE_API_BASE_URL}/project/${projectId}/modules/${moduleId}`,
};

export const PAGE_ENDPOINTS = {
  // Get pages (if needed in future)
  GET_PAGES: (projectId: string) =>
    `${STAGE_API_BASE_URL}/project/${projectId}/pages`,

  // Create page (if needed in future)
  CREATE_PAGE: (projectId?: string) =>
    projectId
      ? `${STAGE_API_BASE_URL}/project/${projectId}/pages`
      : `${STAGE_API_BASE_URL}/project/pages`,

  // Update page (if needed in future)
  UPDATE_PAGE: (projectId: string, pageId: string) =>
    `${STAGE_API_BASE_URL}/project/${projectId}/pages/${pageId}`,

  // Delete page (if needed in future)
  DELETE_PAGE: (projectId: string, pageId: string) =>
    `${STAGE_API_BASE_URL}/project/${projectId}/pages/${pageId}`,
};

export const SUBSTATE_ENDPOINTS = {
  // Get sub-states for a project
  GET_SUBSTATES: (projectId: string) =>
    `${STAGE_API_BASE_URL}/project/states/${projectId}/sub-states`,
};
