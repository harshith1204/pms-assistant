import { API_HTTP_URL, getMemberId, getBusinessId } from "@/config";

// Type for saved artifact data returned from the API
export interface SavedArtifactData {
  link?: string;
  id?: string;
  [key: string]: unknown;
}

// Type for raw conversation message from the API
export interface RawConversationMessage {
  id: string;
  type: string;
  content: string;
  liked?: boolean;
  feedback?: string;
  isSaved?: boolean;
  savedData?: SavedArtifactData;
  workItem?: { title: string; description?: string; projectIdentifier?: string; sequenceId?: string | number; link?: string; isSaved?: boolean; savedData?: SavedArtifactData };
  page?: { title: string; blocks: { blocks: unknown[] }; isSaved?: boolean; savedData?: SavedArtifactData };
  cycle?: { title: string; description?: string; startDate?: string; endDate?: string; isSaved?: boolean; savedData?: SavedArtifactData };
  module?: { title: string; description?: string; projectName?: string; isSaved?: boolean; savedData?: SavedArtifactData };
  epic?: { title: string; description?: string; isSaved?: boolean; savedData?: SavedArtifactData };
  userStory?: { title: string; description?: string; persona?: string; user_goal?: string; userGoal?: string; demographics?: string; acceptance_criteria?: string[]; acceptanceCriteria?: string[]; isSaved?: boolean; savedData?: SavedArtifactData };
  feature?: { title: string; description?: string; problemStatement?: string; objective?: string; successCriteria?: string[]; goals?: string[]; painPoints?: string[]; inScope?: string[]; outOfScope?: string[]; functionalRequirements?: Array<{ requirementId: string; priorityLevel: string; description: string }>; nonFunctionalRequirements?: Array<{ requirementId: string; priorityLevel: string; description: string }>; isSaved?: boolean; savedData?: SavedArtifactData };
  project?: { name: string; projectId?: string; description?: string; isSaved?: boolean; savedData?: SavedArtifactData };
}

export async function getConversations(): Promise<Array<{ id: string; title: string; updatedAt?: string }>> {
  try {
    const userId = getMemberId();
    const businessId = getBusinessId();
    
    if (!userId || !businessId) {
      console.warn("Missing user_id or business_id for conversations API");
      return [];
    }
    
    const url = new URL(`${API_HTTP_URL}/conversations`);
    url.searchParams.set('user_id', userId);
    url.searchParams.set('business_id', businessId);
    
    const res = await fetch(url.toString(), {
      headers: {
        'accept': 'application/json',
      },
    });
    
    if (!res.ok) throw new Error("failed");
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export async function getConversationMessages(conversationId: string): Promise<RawConversationMessage[]> {
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

export async function reactToMessage(args: { conversationId: string; messageId: string; liked?: boolean; feedback?: string }): Promise<boolean> {
  try {
    const res = await fetch(`${API_HTTP_URL}/conversations/reaction`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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

export async function markArtifactSaved(args: { 
  conversationId: string; 
  messageId: string; 
  artifactType: string;
  savedData?: SavedArtifactData;
}): Promise<boolean> {
  try {
    const res = await fetch(`${API_HTTP_URL}/conversations/artifact-saved`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: args.conversationId,
        message_id: args.messageId,
        artifact_type: args.artifactType,
        is_saved: true,
        saved_data: args.savedData ?? undefined,
      }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    return !!data?.ok;
  } catch {
    return false;
  }
}

