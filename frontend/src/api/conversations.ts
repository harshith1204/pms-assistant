import { API_HTTP_URL } from "@/config";

export async function getConversations(): Promise<Array<{ id: string; title: string; updatedAt?: string }>> {
  // Backend doesn't yet expose list; return empty for now to avoid breaking UI.
  // Hooked for future extension when endpoints are available.
  try {
    const res = await fetch(`${API_HTTP_URL}/conversations`);
    if (!res.ok) throw new Error("failed");
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export async function getConversationMessages(conversationId: string): Promise<Array<{ id: string; type: string; content: string }>> {
  try {
    const res = await fetch(`${API_HTTP_URL}/conversations/${encodeURIComponent(conversationId)}`);
    if (!res.ok) throw new Error("failed");
    const data = await res.json();
    if (data && Array.isArray(data.messages)) return data.messages;
    return [];
  } catch {
    return [];
  }
}

