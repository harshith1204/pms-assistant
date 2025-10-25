import { PAGE_ENDPOINTS } from "@/api/endpoints";

export type CreatePageRequest = {
  title: string;
  content: { blocks: any[] };
  projectId?: string;
  createdBy?: string;
};

export type CreatePageResponse = {
  id: string;
  title: string;
  content: string; // stringified Editor.js JSON
  link?: string;
};

export async function createPage(payload: CreatePageRequest): Promise<CreatePageResponse> {
  const endpoint = PAGE_ENDPOINTS.CREATE_PAGE(payload.projectId);

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: payload.title,
      content: payload.content,
      project_id: payload.projectId,
      created_by: payload.createdBy,
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create page (${res.status})`);
  }
  return res.json();
}

