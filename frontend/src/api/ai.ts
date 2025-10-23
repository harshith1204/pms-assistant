import { AI_TEMPLATE_SERVICE_URL } from "@/config";

export type GenerateWorkItemRequest = {
  prompt: string;
  template: {
    title: string;
    content: string;
  };
};

export type GenerateWorkItemResponse = {
  title?: string;
  description?: string;
  content?: string;
  [key: string]: any;
};

export async function generateWorkItemWithAI(payload: GenerateWorkItemRequest): Promise<GenerateWorkItemResponse> {
  const res = await fetch(`${AI_TEMPLATE_SERVICE_URL}/generate-work-item`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to generate work item with AI (${res.status})`);
  }
  return res.json();
}

export type GenerateWorkItemSurpriseRequest = {
  title: string;
  description: string;
};

export async function generateWithAiSurprise(payload: GenerateWorkItemSurpriseRequest): Promise<GenerateWorkItemResponse> {
  const res = await fetch(`${AI_TEMPLATE_SERVICE_URL}/generate-work-item-surprise-me`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to generate work item with AI surprise (${res.status})`);
  }
  return res.json();
}