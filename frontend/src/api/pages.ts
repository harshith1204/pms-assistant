import { API_HTTP_URL } from "@/config";

export type PageProject = {
  id: string;
  name: string;
};

export type PageBusiness = {
  id: string;
  name: string;
};

export type PageCreatedBy = {
  id: string;
  name: string;
};

export type PageCycle = {
  id: string;
  name: string;
};

export type PageModule = {
  id: string;
  name: string;
};

export type PageMember = {
  id: string;
  name: string;
};

export type CreatePageRequest = {
  title: string;
  content: string; // stringified Editor.js JSON
  business: PageBusiness;
  project: PageProject;
  createdBy: PageCreatedBy;
  visibility?: 'PUBLIC' | 'PRIVATE' | 'ARCHIVED';
  locked?: boolean;
  favourite?: boolean;
  readTime?: string;
  wordCount?: number;
  linkedCycle?: PageCycle[];
  linkedModule?: PageModule[];
  linkedMembers?: PageMember[];
  linkedPages?: any[];
};

export type CreatePageResponse = {
  id: string;
  title: string;
  content: string;
  link?: string;
  data?: any;
};

export async function createPage(payload: CreatePageRequest): Promise<CreatePageResponse> {
  const res = await fetch(`${API_HTTP_URL}/page`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create page (${res.status})`);
  }
  return res.json();
}

export async function getAllPages(projectId: string, payload: any): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/page/${projectId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get pages (${res.status})`);
  }
  return res.json();
}

export async function getPageDetailsById(pageId: string): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/page/detail/${pageId}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to get page details (${res.status})`);
  }
  return res.json();
}

export async function deletePage(pageId: string): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/page/${pageId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to delete page (${res.status})`);
  }
  return res.json();
}

export async function markFavPage(pageId: string, isFavourite: boolean): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/page/${pageId}/favourite?isFav=${isFavourite}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to mark page as favorite (${res.status})`);
  }
  return res.json();
}

export async function lockUnlockPage(pageId: string, isLocked: boolean): Promise<any> {
  const res = await fetch(`${API_HTTP_URL}/page/${pageId}/lock-unlock?isLocked=${isLocked}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to lock/unlock page (${res.status})`);
  }
  return res.json();
}

