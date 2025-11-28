import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { ChatSidebar } from "@/components/ChatSidebar";
import { ChatMessage } from "@/components/ChatMessage";
import { ChatInput } from "@/components/ChatInput";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sparkles, LucideMenu } from "lucide-react";
import Settings from "@/pages/Settings";
import { useChatSocket, type ChatEvent } from "@/hooks/useChatSocket";
import { getConversations, getConversationMessages, reactToMessage, markArtifactSaved, SavedArtifactData, RawConversationMessage } from "@/api/conversations";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getMemberId, getBusinessId } from "@/config";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  liked?: boolean;
  feedback?: string;
  internalActivity?: {
    summary: string;
    bullets?: string[];
    doneLabel?: string;
    body?: string;
  };
  workItem?: {
    title: string;
    description?: string;
    projectIdentifier?: string;
    sequenceId?: string | number;
    link?: string;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  page?: {
    title: string;
    blocks: { blocks: unknown[] };
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  cycle?: {
    title: string;
    description?: string;
    startDate?: string;
    endDate?: string;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  module?: {
    title: string;
    description?: string;
    projectName?: string;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  epic?: {
    title: string;
    description?: string;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  userStory?: {
    title: string;
    description?: string;
    persona?: string;
    userGoal?: string;
    demographics?: string;
    acceptanceCriteria?: string[];
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  feature?: {
    title: string;
    description?: string;
    problemStatement?: string;
    objective?: string;
    successCriteria?: string[];
    goals?: string[];
    painPoints?: string[];
    inScope?: string[];
    outOfScope?: string[];
    functionalRequirements?: Array<{ requirementId: string; priorityLevel: string; description: string }>;
    nonFunctionalRequirements?: Array<{ requirementId: string; priorityLevel: string; description: string }>;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  project?: {
    name: string;
    projectId?: string;
    description?: string;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
}

interface Conversation {
  id: string;
  title: string;
  timestamp: Date;
}

// Use URL query params to persist UI state across reloads/navigation
const CONV_QUERY_PARAM = "conversationId";
const VIEW_QUERY_PARAM = "view";
const VIEW_SETTINGS = "settings";

const Index = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [showPersonalization, setShowPersonalization] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState(false);
  // Consider empty only when no active conversation is selected
  const isEmpty = messages.length === 0 && !activeConversationId;
  const [feedbackTargetId, setFeedbackTargetId] = useState<string | null>(null);
  const [feedbackText, setFeedbackText] = useState<string>("");
  const endRef = useRef<HTMLDivElement | null>(null);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);  

  // Track the current streaming assistant message id
  const streamingAssistantIdRef = useRef<string | null>(null);
  // Track the current active conversation id to avoid stale closures
  const activeConversationIdRef = useRef<string | null>(null);

  // URL helpers for syncing conversation id
  const getConversationIdFromUrl = () => {
    try {
      const url = new URL(window.location.href);
      return url.searchParams.get(CONV_QUERY_PARAM);
    } catch {
      return null;
    }
  };

  const setConversationIdInUrl = (id: string | null, options?: { replace?: boolean }) => {
    try {
      const url = new URL(window.location.href);
      if (id) {
        url.searchParams.set(CONV_QUERY_PARAM, id);
      } else {
        url.searchParams.delete(CONV_QUERY_PARAM);
      }
      const href = url.toString();
      if (options?.replace) {
        window.history.replaceState(null, "", href);
      } else {
        window.history.pushState(null, "", href);
      }
    } catch {
      // ignore URL update errors
    }
  };

  const getViewFromUrl = () => {
    try {
      const url = new URL(window.location.href);
      const view = url.searchParams.get(VIEW_QUERY_PARAM);
      if (view === VIEW_SETTINGS) return view;
      return null;
    } catch {
      return null;
    }
  };

  const setViewInUrl = (
    view: typeof VIEW_SETTINGS | null,
    options?: { replace?: boolean }
  ) => {
    try {
      const url = new URL(window.location.href);
      if (view) {
        url.searchParams.set(VIEW_QUERY_PARAM, view);
      } else {
        url.searchParams.delete(VIEW_QUERY_PARAM);
      }
      const href = url.toString();
      if (options?.replace) {
        window.history.replaceState(null, "", href);
      } else {
        window.history.pushState(null, "", href);
      }
    } catch {
      // ignore URL update errors
    }
  };

  // Helper: transform backend messages to UI messages with internal actions grouped
  const transformConversationMessages = useCallback((raw: RawConversationMessage[]): Message[] => {
    const result: Message[] = [];
    let pendingActionBullets: string[] = [];

    const flushPendingIntoLastAssistant = () => {
      if (pendingActionBullets.length === 0) return;
      // Attach to the most recent assistant message if available
      for (let i = result.length - 1; i >= 0; i--) {
        if (result[i].role === "assistant") {
          const prev = result[i];
          const mergedBullets = [
            ...((prev.internalActivity && prev.internalActivity.bullets) || []),
            ...pendingActionBullets,
          ];
          result[i] = {
            ...prev,
            internalActivity: {
              summary: prev.internalActivity?.summary || "Actions",
              bullets: mergedBullets,
              doneLabel: prev.internalActivity?.doneLabel || "Done",
              body: prev.internalActivity?.body,
            },
          };
          pendingActionBullets = [];
          return;
        }
      }
      // If no assistant message exists yet, create a synthetic assistant-only actions block
      result.push({
        id: `actions-${Date.now()}`,
        role: "assistant",
        content: "",
        internalActivity: { summary: "Actions", bullets: [...pendingActionBullets], doneLabel: "Done" },
      });
      pendingActionBullets = [];
    };

    for (const m of raw || []) {
      const type = (m.type || "").toLowerCase();
      if (type === "action") {
        const text = (m.content || "").trim();
        if (text) pendingActionBullets.push(text);
        continue;
      }

      if (type === "assistant") {
        // Create assistant message and attach any pending actions to it
        const assistantMsg: Message = {
          id: m.id,
          role: "assistant",
          content: m.content || "",
          liked: m.liked,
          feedback: m.feedback,
        };
        if (pendingActionBullets.length > 0) {
          assistantMsg.internalActivity = { summary: "Actions", bullets: [...pendingActionBullets], doneLabel: "Done" };
          pendingActionBullets = [];
        }
        result.push(assistantMsg);
        continue;
      }

      if (type === "user") {
        // Do not flush pending actions here; they belong to the next assistant
        result.push({ id: m.id, role: "user", content: m.content || "" });
        continue;
      }

      if (type === "work_item" && m.workItem) {
        const wi = m.workItem;
        result.push({ id: m.id, role: "assistant", content: "", workItem: { ...wi, isSaved: wi.isSaved || m.isSaved, savedData: wi.savedData || m.savedData } });
        continue;
      }
      if (type === "page" && m.page) {
        const pg = m.page;
        result.push({ id: m.id, role: "assistant", content: "", page: { ...pg, isSaved: pg.isSaved || m.isSaved, savedData: pg.savedData || m.savedData } });
        continue;
      }
      if (type === "cycle" && m.cycle) {
        const cy = m.cycle;
        result.push({ id: m.id, role: "assistant", content: "", cycle: { ...cy, isSaved: cy.isSaved || m.isSaved, savedData: cy.savedData || m.savedData } });
        continue;
      }
      if (type === "module" && m.module) {
        const md = m.module;
        result.push({ id: m.id, role: "assistant", content: "", module: { ...md, isSaved: md.isSaved || m.isSaved, savedData: md.savedData || m.savedData } });
        continue;
      }
      if (type === "epic" && m.epic) {
        const ep = m.epic;
        result.push({ id: m.id, role: "assistant", content: "", epic: { ...ep, isSaved: ep.isSaved || m.isSaved, savedData: ep.savedData || m.savedData } });
        continue;
      }
      if (type === "user_story" && m.userStory) {
        const us = m.userStory;
        result.push({ 
          id: m.id, 
          role: "assistant", 
          content: "", 
          userStory: {
            title: us.title || "",
            description: us.description || "",
            persona: us.persona || "",
            userGoal: us.user_goal || us.userGoal || "",
            demographics: us.demographics || "",
            acceptanceCriteria: us.acceptance_criteria || us.acceptanceCriteria || [],
            isSaved: us.isSaved || m.isSaved,
            savedData: us.savedData || m.savedData,
          }
        });
        continue;
      }
      if (type === "feature" && m.feature) {
        const ft = m.feature;
        result.push({ 
          id: m.id, 
          role: "assistant", 
          content: "", 
          feature: {
            title: ft.title || "",
            description: ft.description || "",
            problemStatement: ft.problemStatement || "",
            objective: ft.objective || "",
            successCriteria: ft.successCriteria || [],
            goals: ft.goals || [],
            painPoints: ft.painPoints || [],
            inScope: ft.inScope || [],
            outOfScope: ft.outOfScope || [],
            functionalRequirements: ft.functionalRequirements || [],
            nonFunctionalRequirements: ft.nonFunctionalRequirements || [],
            isSaved: ft.isSaved || m.isSaved,
            savedData: ft.savedData || m.savedData,
          }
        });
        continue;
      }
      if (type === "project" && m.project) {
        const pj = m.project;
        result.push({ 
          id: m.id, 
          role: "assistant", 
          content: "", 
          project: {
            name: pj.name || "",
            projectId: pj.projectId || "",
            description: pj.description || "",
            isSaved: pj.isSaved || m.isSaved,
            savedData: pj.savedData || m.savedData,
          }
        });
        continue;
      }
      if (type === "project_data_loaded") {
        result.push({ id: m.id, role: "assistant", content: m.content || "" });
        continue;
      }
      // Fallback: treat unknown types as assistant text
      result.push({ id: m.id, role: "assistant", content: m.content || "" });
    }

    // If actions remain without a following assistant, attach to last assistant or create a block
    flushPendingIntoLastAssistant();
    return result;
  }, []);

  // Socket integration: handle backend events
  const handleSocketEvent = useCallback((evt: ChatEvent) => {
    // Suppress tool events from affecting UI
    if (evt.type === "tool_start" || evt.type === "tool_end") {
      return;
    }
    if (evt.type === "llm_start") {
      // Start a new assistant streaming message if not present
      if (!streamingAssistantIdRef.current) {
        const id = `assistant-${Date.now()}`;
        streamingAssistantIdRef.current = id;
        setMessages((prev) => [
          ...prev,
          { id, role: "assistant", content: "", isStreaming: true, internalActivity: { summary: "Actions", bullets: [], doneLabel: "Done" } },
        ]);
      }
    } else if (evt.type === "token") {
      const id = streamingAssistantIdRef.current;
      if (!id) return;
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, content: (m.content || "") + (evt.content || "") } : m)));
    } else if (evt.type === "llm_end") {
      // Keep loader and streaming state until we receive the final 'complete' event
    } else if (evt.type === "agent_action") {
      if (!streamingAssistantIdRef.current) {
        const id = `assistant-${Date.now()}`;
        streamingAssistantIdRef.current = id;
        setMessages((prev) => [
          ...prev,
          { id, role: "assistant", content: "", isStreaming: true, internalActivity: { summary: "Actions", bullets: [], doneLabel: "Done" } },
        ]);
      }
      const id = streamingAssistantIdRef.current;
      setMessages((prev) => prev.map((m) => (
        m.id === id
          ? {
              ...m,
              internalActivity: {
                summary: m.internalActivity?.summary || "Actions",
                bullets: [
                  ...(m.internalActivity?.bullets || []),
                  `${evt.text}`,
                ],
                doneLabel: m.internalActivity?.doneLabel || "Done",
                body: m.internalActivity?.body,
              },
            }
          : m
      )));
    } else if (evt.type === "content_generated") {
      // Render generated artifacts inline in conversation
      if (evt.content_type === "work_item" && evt.success && (evt as any).data) {
        const data: any = (evt as any).data;
        const id = `workitem-${Date.now()}`;
        const projectIdentifier = (data.projectIdentifier as string) || undefined;
        const sequenceId = (data.sequenceId as string | number) || undefined;
        const link = (data.link as string) || undefined;

        // Build candidate message
        const candidate = {
          id,
          role: "assistant" as const,
          content: "",
          workItem: {
            title: (data.title as string) || "Work item",
            description: (data.description as string) || "",
            projectIdentifier,
            sequenceId,
            link,
          },
        };

        // De-duplicate against the tail of current list to prevent duplicates
        setMessages((prev) => {
          const hash = (wi: NonNullable<Message['workItem']>) => [
            (wi.title || '').trim(),
            (wi.description || '').trim(),
            wi.projectIdentifier || '',
            wi.sequenceId === undefined || wi.sequenceId === null ? '' : String(wi.sequenceId),
            wi.link || ''
          ].join('|');
          const candidateHash = hash(candidate.workItem);
          const exists = prev.slice(-10).some((m) => m.workItem && hash(m.workItem) === candidateHash);
          if (exists) return prev;
          return [...prev, candidate];
        });
      } else if (evt.content_type === "page" && evt.success && (evt as any).data) {
        const data: any = (evt as any).data;
        const id = `page-${Date.now()}`;
        const title = (data.title as string) || "Generated Page";
        const blocks = typeof data === "object" && data && Array.isArray((data as any).blocks) ? { blocks: (data as any).blocks } : { blocks: [] };

        const candidate = {
          id,
          role: "assistant" as const,
          content: "",
          page: { title, blocks },
        };

        setMessages((prev) => {
          const hash = (pg: NonNullable<Message['page']>) => [
            (pg.title || '').trim(),
            JSON.stringify((pg.blocks && Array.isArray(pg.blocks.blocks)) ? pg.blocks.blocks : [])
          ].join('|');
          const candidateHash = hash(candidate.page!);
          const exists = prev.slice(-10).some((m) => m.page && hash(m.page) === candidateHash);
          if (exists) return prev;
          return [...prev, candidate];
        });
      } else if (evt.content_type === "cycle" && evt.success && (evt as any).data) {
        const data: any = (evt as any).data;
        const id = `cycle-${Date.now()}`;
        const candidate = {
          id,
          role: "assistant" as const,
          content: "",
          cycle: {
            title: (data.title as string) || "Cycle",
            description: (data.description as string) || "",
            startDate: (data.startDate as string) || undefined,
            endDate: (data.endDate as string) || undefined,
          },
        };

        setMessages((prev) => {
          const hash = (cy: NonNullable<Message['cycle']>) => [
            (cy.title || '').trim(),
            (cy.description || '').trim()
          ].join('|');
          const candidateHash = hash(candidate.cycle);
          const exists = prev.slice(-10).some((m) => m.cycle && hash(m.cycle) === candidateHash);
          if (exists) return prev;
          return [...prev, candidate];
        });
      } else if (evt.content_type === "module" && evt.success && (evt as any).data) {
        const data: any = (evt as any).data;
        const id = `module-${Date.now()}`;
        const candidate = {
          id,
          role: "assistant" as const,
          content: "",
          module: {
            title: (data.title as string) || "Module",
            description: (data.description as string) || "",
            projectName: (data.projectName as string) || undefined,
          },
        };

        setMessages((prev) => {
          const hash = (md: NonNullable<Message['module']>) => [
            (md.title || '').trim(),
            (md.description || '').trim()
          ].join('|');
          const candidateHash = hash(candidate.module);
          const exists = prev.slice(-10).some((m) => m.module && hash(m.module) === candidateHash);
          if (exists) return prev;
          return [...prev, candidate];
        });
      } else if (evt.content_type === "epic" && evt.success && (evt as any).data) {
        const data: any = (evt as any).data;
        const id = `epic-${Date.now()}`;
        const candidate = {
          id,
          role: "assistant" as const,
          content: "",
          epic: {
            title: (data.title as string) || "Epic",
            description: (data.description as string) || "",
          },
        };

        setMessages((prev) => {
          const hash = (ep: NonNullable<Message['epic']>) => [
            (ep.title || '').trim(),
            (ep.description || '').trim()
          ].join('|');
          const candidateHash = hash(candidate.epic);
          const exists = prev.slice(-10).some((m) => m.epic && hash(m.epic) === candidateHash);
          if (exists) return prev;
          return [...prev, candidate];
        });
      } else if (evt.content_type === "user_story" && evt.success && (evt as any).data) {
        const data: any = (evt as any).data;
        const id = `userstory-${Date.now()}`;
        const candidate = {
          id,
          role: "assistant" as const,
          content: "",
          userStory: {
            title: (data.title as string) || "User Story",
            description: (data.description as string) || "",
            persona: (data.persona as string) || "",
            userGoal: (data.user_goal as string) || "",
            demographics: (data.demographics as string) || "",
            acceptanceCriteria: Array.isArray(data.acceptance_criteria) ? data.acceptance_criteria : [],
          },
        };

        setMessages((prev) => {
          const hash = (us: NonNullable<Message['userStory']>) => [
            (us.title || '').trim(),
            (us.description || '').trim(),
            (us.persona || '').trim()
          ].join('|');
          const candidateHash = hash(candidate.userStory);
          const exists = prev.slice(-10).some((m) => m.userStory && hash(m.userStory) === candidateHash);
          if (exists) return prev;
          return [...prev, candidate];
        });
      } else if (evt.content_type === "feature" && evt.success && (evt as any).data) {
        const data: any = (evt as any).data;
        const id = `feature-${Date.now()}`;
        
        // Transform functional_requirements to match expected format
        const transformRequirements = (reqs: any[]): Array<{ requirementId: string; priorityLevel: string; description: string }> => {
          if (!Array.isArray(reqs)) return [];
          return reqs.map((req, idx) => ({
            requirementId: req.requirementId || req.requirement_id || `REQ-${idx + 1}`,
            priorityLevel: req.priorityLevel || req.priority_level || req.type || "should_have",
            description: req.description || req.requirement || "",
          }));
        };
        
        const candidate = {
          id,
          role: "assistant" as const,
          content: "",
          feature: {
            title: (data.feature_name as string) || "Feature",
            description: (data.description as string) || "",
            problemStatement: (data.problem_statement as string) || "",
            objective: (data.objective as string) || "",
            successCriteria: Array.isArray(data.success_criteria) ? data.success_criteria : [],
            goals: Array.isArray(data.goals) ? data.goals : [],
            painPoints: Array.isArray(data.pain_points) ? data.pain_points : [],
            inScope: Array.isArray(data.in_scope) ? data.in_scope : [],
            outOfScope: Array.isArray(data.out_of_scope) ? data.out_of_scope : [],
            functionalRequirements: transformRequirements(data.functional_requirements),
            nonFunctionalRequirements: transformRequirements(data.non_functional_requirements),
          },
        };

        setMessages((prev) => {
          const hash = (ft: NonNullable<Message['feature']>) => [
            (ft.title || '').trim(),
            (ft.description || '').trim()
          ].join('|');
          const candidateHash = hash(candidate.feature);
          const exists = prev.slice(-10).some((m) => m.feature && hash(m.feature) === candidateHash);
          if (exists) return prev;
          return [...prev, candidate];
        });
      } else if (evt.content_type === "project" && evt.success && (evt as any).data) {
        const data: any = (evt as any).data;
        const id = `project-${Date.now()}`;
        const candidate = {
          id,
          role: "assistant" as const,
          content: "",
          project: {
            name: (data.project_name as string) || "Project",
            projectId: (data.project_id as string) || "",
            description: (data.description as string) || "",
          },
        };

        setMessages((prev) => {
          const hash = (pj: NonNullable<Message['project']>) => [
            (pj.name || '').trim(),
            (pj.projectId || '').trim()
          ].join('|');
          const candidateHash = hash(candidate.project);
          const exists = prev.slice(-10).some((m) => m.project && hash(m.project) === candidateHash);
          if (exists) return prev;
          return [...prev, candidate];
        });
      } else if (evt.content_type === "project_data_loaded") {
        const id = `project-data-${Date.now()}`;
        setMessages((prev) => [
          ...prev,
          {
            id,
            role: "assistant",
            content: (evt as any).message || "Project data loaded successfully.",
          },
        ]);
      } else {
        const id = `assistant-${Date.now()}`;
        setMessages((prev) => [
          ...prev,
          {
            id,
            role: "assistant",
            content: evt.success
              ? `Generated ${String(evt.content_type || "content").replace("_", " ")} content.`
              : `Generation failed: ${(evt as any).error || "Unknown error"}`,
          },
        ]);
      }
    } else if (evt.type === "error") {
      const id = `assistant-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id, role: "assistant", content: `Error: ${evt.message}` },
      ]);
      setIsLoading(false);
      streamingAssistantIdRef.current = null;
    } else if (evt.type === "complete") {
      setIsLoading(false);
      streamingAssistantIdRef.current = null;
      // Reconcile to canonical conversation ID when provided by backend
      const canonicalId = (evt as any).conversation_id as string | undefined;
      const currentActive = activeConversationIdRef.current;
      if (canonicalId && currentActive && canonicalId !== currentActive) {
        setActiveConversationId(canonicalId);
        // Update/merge conversations list to replace ephemeral with canonical id
        setConversations((prev) => {
          const ephemeralIdx = prev.findIndex((c) => c.id === currentActive);
          const canonicalIdx = prev.findIndex((c) => c.id === canonicalId);
          if (ephemeralIdx !== -1 && canonicalIdx !== -1) {
            // Both exist; drop the ephemeral one
            const copy = [...prev];
            copy.splice(ephemeralIdx, 1);
            return copy;
          }
          if (ephemeralIdx !== -1) {
            const copy = [...prev];
            copy[ephemeralIdx] = { ...copy[ephemeralIdx], id: canonicalId };
            return copy;
          }
          return prev;
        });
        // Normalize URL to canonical id without adding a new history entry
        setConversationIdInUrl(canonicalId, { replace: true });
      }
      // Refresh messages from server to get canonical IDs so reactions persist
      const convId = canonicalId || currentActive;
      if (convId) {
        (async () => {
          try {
            const msgs = await getConversationMessages(convId);
            setMessages((prev) => {
              const transformed = transformConversationMessages(msgs);

              // De-duplicate ephemeral generated artifacts that were optimistically added
              // before the canonical conversation messages were fetched.
              const hashWorkItem = (wi: NonNullable<Message['workItem']>) => [
                (wi.title || '').trim(),
                (wi.description || '').trim(),
                wi.projectIdentifier || '',
                wi.sequenceId === undefined || wi.sequenceId === null ? '' : String(wi.sequenceId),
                wi.link || ''
              ].join('|');

              const hashPage = (pg: NonNullable<Message['page']>) => [
                (pg.title || '').trim(),
                JSON.stringify((pg.blocks && Array.isArray(pg.blocks.blocks)) ? pg.blocks.blocks : [])
              ].join('|');

              const serverWorkItemHashes = new Set(
                transformed.filter((m) => !!m.workItem).map((m) => hashWorkItem(m.workItem!))
              );
              const serverPageHashes = new Set(
                transformed.filter((m) => !!m.page).map((m) => hashPage(m.page!))
              );

              const remainingEphemeralWorkItems = prev.filter((m) => m.workItem)
                .filter((m) => !serverWorkItemHashes.has(hashWorkItem(m.workItem!)));
              const remainingEphemeralPages = prev.filter((m) => m.page)
                .filter((m) => !serverPageHashes.has(hashPage(m.page!)));

              return [...transformed, ...remainingEphemeralWorkItems, ...remainingEphemeralPages];
            });
          } catch {
            // ignore
          }
        })();
      }
    }
  }, []);

  const { connected, send } = useChatSocket({
    onEvent: handleSocketEvent,
    member_id: getMemberId(),
    business_id: getBusinessId()
  });

  // Load conversations on mount
  useEffect(() => {
    (async () => {
      try {
        const list = await getConversations();
        setConversations(
          list.map((c) => ({ id: c.id, title: c.title, timestamp: new Date(c.updatedAt || Date.now()) }))
        );
      } catch (e) {
        // ignore errors in dev
      }
    })();
  }, []);

  // Keep the ref in sync with the active conversation id
  useEffect(() => {
    activeConversationIdRef.current = activeConversationId;
  }, [activeConversationId]);

  // Load view or conversation from URL on mount
  useEffect(() => {
    const view = getViewFromUrl();
    if (view === VIEW_SETTINGS) {
      setShowPersonalization(true);
      setActiveConversationId(null);
      setMessages([]);
      return;
    }

    const id = getConversationIdFromUrl();
    if (id) {
      setActiveConversationId(id);
      setShowPersonalization(false);
      (async () => {
        try {
          const msgs = await getConversationMessages(id);
          setMessages(transformConversationMessages(msgs));
        } catch {
          setMessages([]);
        }
      })();
    }
  }, []);

  // Respond to back/forward navigation by syncing from URL
  useEffect(() => {
    const onPopState = () => {
      const view = getViewFromUrl();
      const id = getConversationIdFromUrl();
      const current = activeConversationIdRef.current;

      if (view === VIEW_SETTINGS) {
        setShowPersonalization(true);
        if (current) setActiveConversationId(null);
        setMessages([]);
        return;
      }

      // No view param: show conversation if present, otherwise clear
      if (id && id !== current) {
        setActiveConversationId(id);
        setShowPersonalization(false);
        (async () => {
          try {
            const msgs = await getConversationMessages(id);
            setMessages(transformConversationMessages(msgs));
          } catch {
            setMessages([]);
          }
        })();
      } else if (!id) {
        if (current) setActiveConversationId(null);
        setShowPersonalization(false);
        setMessages([]);
      }
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const handleNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setShowPersonalization(false);
    // Remove conversation id from URL
    setConversationIdInUrl(null);
    // Clear view as well
    setViewInUrl(null);
  };

  const handleSelectConversation = async (id: string) => {
    // Reflect selection in URL
    setConversationIdInUrl(id);
    // Clear any view param so conversation is shown
    setViewInUrl(null);
    setActiveConversationId(id);
    // Ensure we exit the settings view when a conversation is selected
    setShowPersonalization(false);
    try {
      const msgs = await getConversationMessages(id);
      setMessages(transformConversationMessages(msgs));
    } catch (e) {
      setMessages([]);
    }
  };

  const handleShowPersonalization = () => {
    setShowPersonalization(true);
    setActiveConversationId(null);
    setMessages([]);
    // Update URL to reflect settings view and clear any conversation
    setConversationIdInUrl(null);
    setViewInUrl(VIEW_SETTINGS);
  };

  const handleSendMessage = async (content: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    // Ensure we have an active conversation id
    let convId = activeConversationId;
    if (!convId) {
      convId = `conv_${Date.now()}`;
      setActiveConversationId(convId);
      // Push new conversation id into URL
      const currentInUrl = getConversationIdFromUrl();
      if (currentInUrl !== convId) {
        setConversationIdInUrl(convId);
      }
      const newConversation: Conversation = {
        id: convId,
        title: content.slice(0, 30) + (content.length > 30 ? "..." : ""),
        timestamp: new Date(),
      };
      setConversations((prev) => [newConversation, ...prev]);
    } else {
      // Ensure URL reflects existing active conversation id
      const currentInUrl = getConversationIdFromUrl();
      if (currentInUrl !== convId) {
        setConversationIdInUrl(convId);
      }
    }

    // Send to backend via WebSocket
    const mid = getMemberId();
    const bid = getBusinessId();
    const ok = send({
      message: content,
      conversation_id: convId,
      member_id: mid,
      business_id: bid
    });
    if (!ok) {
      // Fallback: show error and stop loading
      setMessages((prev) => [
        ...prev,
        { id: `assistant-${Date.now()}`, role: "assistant", content: "Connection error. Please try again." },
      ]);
      setIsLoading(false);
    }
  };

  const handleLike = async (messageId: string) => {
    if (!activeConversationId) return;
    const currentReaction = messages.find((m) => m.id === messageId)?.liked;

    if (currentReaction === true) {
      // Toggle off like (clear reaction)
      const ok = await reactToMessage({ conversationId: activeConversationId, messageId });
      if (ok) {
        setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, liked: undefined } : m)));
      }
      if (feedbackTargetId === messageId) {
        setFeedbackTargetId(null);
        setFeedbackText("");
      }
    } else {
      // Set like (and clear any open feedback box for this message)
      const ok = await reactToMessage({ conversationId: activeConversationId, messageId, liked: true });
      if (ok) {
        setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, liked: true } : m)));
      }
      if (feedbackTargetId === messageId) {
        setFeedbackTargetId(null);
        setFeedbackText("");
      }
    }
  };

  const handleDislike = async (messageId: string) => {
    if (!activeConversationId) return;
    const currentReaction = messages.find((m) => m.id === messageId)?.liked;

    if (currentReaction === false) {
      // Toggle off dislike (clear reaction) and close any feedback UI for this message
      const ok = await reactToMessage({ conversationId: activeConversationId, messageId });
      if (ok) {
        setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, liked: undefined } : m)));
      }
      if (feedbackTargetId === messageId) {
        setFeedbackTargetId(null);
        setFeedbackText("");
      }
    } else {
      // Set dislike and show optional feedback input
      setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, liked: false } : m)));
      await reactToMessage({ conversationId: activeConversationId, messageId, liked: false });
      setFeedbackTargetId(messageId);
      setFeedbackText("");
    }
  };

  const handleArtifactSaved = async (messageId: string, artifactType: string, savedData?: any) => {
    if (!activeConversationId) return;
    
    // Update local message state to mark artifact as saved
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== messageId) return m;
        
        // Update the appropriate artifact field with isSaved and savedData
        const updatedMessage = { ...m };
        if (artifactType === 'work_item' && m.workItem) {
          updatedMessage.workItem = { ...m.workItem, isSaved: true, savedData };
        } else if (artifactType === 'page' && m.page) {
          updatedMessage.page = { ...m.page, isSaved: true, savedData };
        } else if (artifactType === 'cycle' && m.cycle) {
          updatedMessage.cycle = { ...m.cycle, isSaved: true, savedData };
        } else if (artifactType === 'module' && m.module) {
          updatedMessage.module = { ...m.module, isSaved: true, savedData };
        } else if (artifactType === 'epic' && m.epic) {
          updatedMessage.epic = { ...m.epic, isSaved: true, savedData };
        } else if (artifactType === 'user_story' && m.userStory) {
          updatedMessage.userStory = { ...m.userStory, isSaved: true, savedData };
        } else if (artifactType === 'feature' && m.feature) {
          updatedMessage.feature = { ...m.feature, isSaved: true, savedData };
        } else if (artifactType === 'project' && m.project) {
          updatedMessage.project = { ...m.project, isSaved: true, savedData };
        }
        return updatedMessage;
      })
    );
    
    // Persist to backend
    try {
      await markArtifactSaved({
        conversationId: activeConversationId,
        messageId,
        artifactType,
        savedData,
      });
    } catch {
      // Ignore errors - the local state is already updated
    }
  };

  const submitFeedback = async () => {
    if (!activeConversationId || !feedbackTargetId) return;
    const text = feedbackText.trim();
    if (text.length === 0) {
      // Optional; simply close if empty
      setFeedbackTargetId(null);
      setFeedbackText("");
      return;
    }
    const ok = await reactToMessage({
      conversationId: activeConversationId,
      messageId: feedbackTargetId,
      liked: false,
      feedback: text,
    });
    if (ok) {
      setMessages((prev) => prev.map((m) => (m.id === feedbackTargetId ? { ...m, feedback: text } : m)));
    }
    setFeedbackTargetId(null);
    setFeedbackText("");
  };

  // Auto-scroll to bottom on message updates
  useEffect(() => {
    if (showPersonalization) return;
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, showPersonalization]);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background relative pb-4 md:pt-3">
      <button className="md:hidden absolute z-[60] w-full bg-background p-3"
        onClick={() => setMobileSidebarOpen(true)}
      >
        <LucideMenu className="w-6 h-6 text-foreground" />
      </button>
      <div className={cn(
          "fixed inset-0 bg-black/40 z-[55] transition-opacity md:hidden",
          mobileSidebarOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        onClick={() => setMobileSidebarOpen(false)}
      ></div>
      <div className={cn(
          "fixed top-0 left-0 h-full w-[90%] bg-background z-[60] shadow-xl transform transition-transform md:hidden",
          mobileSidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <ChatSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onNewChat={handleNewChat}
          onSelectConversation={(id) => {
            handleSelectConversation(id);
            setMobileSidebarOpen(false);
          }}
          onShowPersonalization={() => {
            handleShowPersonalization();
            setMobileSidebarOpen(false);
          }}
        />
      </div>
      <div
        className={cn(
          "absolute top-8 left-8 w-[550px] h-[550px] rounded-full bg-primary/45 blur-2xl pointer-events-none transition-opacity duration-1000 ease-in-out",
          isEmpty ? "opacity-100" : "opacity-0"
        )}
        style={{
          animation: isEmpty ? "4s ease-in-out 0s infinite alternate glow-pulse, 16s ease-in-out 0s infinite alternate float" : "none"
        }}
      />

      <div
        className={cn(
          "absolute top-1/3 right-12 w-[400px] h-[400px] rounded-full bg-accent/55 blur-xl pointer-events-none transition-opacity duration-1000 ease-in-out",
          isEmpty ? "opacity-100" : "opacity-0"
        )}
        style={{
          animation: isEmpty ? "5s ease-in-out 1.5s infinite alternate glow-pulse, 12s ease-in-out 3s infinite alternate float" : "none"
        }}
      />

      <div
        className={cn(
          "absolute bottom-12 right-8 w-[350px] h-[350px] rounded-full bg-primary/40 blur-lg pointer-events-none transition-opacity duration-1000 ease-in-out",
          isEmpty ? "opacity-100" : "opacity-0"
        )}
        style={{
          animation: isEmpty ? "6s ease-in-out 3s infinite alternate glow-pulse, 20s ease-in-out 6s infinite alternate float" : "none"
        }}
      />

      <div className="w-80 flex-shrink-0 relative z-10 hidden md:block">
        <ChatSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          onShowPersonalization={handleShowPersonalization}
        />
      </div>

      <div className="flex flex-1 flex-col relative z-10">
        {showPersonalization ? (
          <div className="flex items-start justify-center md:p-6 py-6 px-3 h-full overflow-y-auto relative" style={{ top: window.innerWidth < 768 ? "3rem" : undefined }}>
            <div className="md:w-full md:max-w-3xl ">
              <Settings />
            </div>
          </div>
        ) : isEmpty ? (
          <div className="flex flex-1 items-center justify-center p-8">
            <div className="text-center md:space-y-6 md:max-w-2xl animate-fade-in">
              <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-primary to-accent shadow-xl animate-pulse-glow">
                <Sparkles className="h-10 w-10 text-white" />
              </div>
              <div className="md:space-y-2">
                <h1 className="text-4xl font-bold text-gradient">
                  Project Lens
                </h1>
                <p className="text-md text-muted-foreground">
                Your AI copilot for planning, collaboration, and progress tracking
                </p>
              </div>
            </div>
          </div>
        ) : (
          <ScrollArea className="flex-1 scrollbar-thin">
            <div className="mx-auto max-w-4xl relative" style={{ top: window.innerWidth < 768 ? "3rem" : undefined }}>
              {messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  id={message.id}
                  role={message.role}
                  content={message.content}
                  isStreaming={message.isStreaming}
                  liked={message.liked}
                  internalActivity={message.internalActivity}
                  workItem={message.workItem}
                  page={message.page}
                  cycle={message.cycle}
                  module={message.module}
                  epic={message.epic}
                  userStory={message.userStory}
                  feature={message.feature}
                  project={message.project}
                  conversationId={activeConversationId || undefined}
                  onLike={handleLike}
                  onDislike={handleDislike}
                  onArtifactSaved={handleArtifactSaved}
                />
              ))}
              <div ref={endRef} />
            </div>
          </ScrollArea>
        )}

        {!showPersonalization && (
          <div
            className={cn(
              "relative z-20 transition-transform duration-500 ease-out",
              // Lift the prompt up under the hero on empty state; return to bottom after first send
              isEmpty ? "-translate-y-[35vh] md:-translate-y-[30vh]" : "translate-y-0"
            )}
          >
            {feedbackTargetId && (
              <div className="mx-auto max-w-4xl mb-3 px-4">
                <Card className="border-destructive/30 bg-destructive/5">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="flex-1">
                        <Textarea
                          value={feedbackText}
                          onChange={(e) => setFeedbackText(e.target.value)}
                          placeholder="Optional: Tell us what was wrong with the answer"
                          className="min-h-[44px]"
                        />
                      </div>
                      <div className="flex flex-col gap-2">
                        <Button size="sm" onClick={submitFeedback} className="whitespace-nowrap">Submit</Button>
                        <Button size="sm" variant="ghost" onClick={() => { setFeedbackTargetId(null); setFeedbackText(""); }}>Dismiss</Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
            <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} showSuggestedPrompts={isEmpty} />
          </div>
        )}
      </div>
    </div>
  );
};

export default Index;
