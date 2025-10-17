import { http } from "@/api/http";

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
  const res = await http(`/pages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: {
      title: payload.title,
      content: payload.content,
      project_id: payload.projectId,
      created_by: payload.createdBy,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to create page (${res.status})`);
  }
  return res.json();
}

