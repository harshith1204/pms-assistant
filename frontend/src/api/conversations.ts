import { API_HTTP_URL } from "@/config";

function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function getConversations(): Promise<Array<{ id: string; title: string; updatedAt?: string }>> {
  // Backend doesn't yet expose list; return empty for now to avoid breaking UI.
  // Hooked for future extension when endpoints are available.
  try {
    const res = await fetch(`${API_HTTP_URL}/conversations`, { headers: { ...authHeaders() } });
    if (!res.ok) throw new Error("failed");
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export async function getConversationMessages(conversationId: string): Promise<Array<{
  id: string;
  type: string;
  content: string;
  liked?: boolean;
  feedback?: string;
  workItem?: { title: string; description?: string; projectIdentifier?: string; sequenceId?: string | number; link?: string };
  page?: { title: string; blocks: { blocks: any[] } };
}>> {
  try {
    const res = await fetch(`${API_HTTP_URL}/conversations/${encodeURIComponent(conversationId)}`, { headers: { ...authHeaders() } });
    if (!res.ok) throw new Error("failed");
    const data = await res.json();
    if (data && Array.isArray(data.messages)) return data.messages;
    return [];
  } catch {
    return [];
  }
}

export async function reactToMessage(args: { conversationId: string; messageId: string; liked?: boolean; feedback?: string }): Promise<boolean> {
  try {
    const res = await fetch(`${API_HTTP_URL}/conversations/reaction`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        conversation_id: args.conversationId,
        message_id: args.messageId,
        liked: args.liked,
        feedback: args.feedback ?? undefined,
      }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    return !!data?.ok;
  } catch {
    return false;
  }
}

