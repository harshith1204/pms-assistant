import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { ChatSidebar } from "@/components/ChatSidebar";
import { ChatMessage } from "@/components/ChatMessage";
import { ChatInput } from "@/components/ChatInput";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sparkles } from "lucide-react";
import PromptLibrary from "@/components/PromptLibrary";
import Settings from "@/pages/Settings";
import { useChatSocket, type ChatEvent } from "@/hooks/useChatSocket";
import { getConversations, getConversationMessages } from "@/api/conversations";
import { ThinkingBubble } from "@/components/ThinkingBubble";
import { AnimatePresence } from "framer-motion";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  internalActivity?: {
    summary: string;
    bullets?: string[];
    doneLabel?: string;
    body?: string;
  };
}

interface Conversation {
  id: string;
  title: string;
  timestamp: Date;
}

const Index = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [showGettingStarted, setShowGettingStarted] = useState<boolean>(false);
  const [showPersonalization, setShowPersonalization] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const isEmpty = messages.length === 0;

  // Track the current streaming assistant message id
  const streamingAssistantIdRef = useRef<string | null>(null);

  // Socket integration: handle backend events
  const handleSocketEvent = useCallback((evt: ChatEvent) => {
    if (evt.type === "llm_start") {
      // Turn off thinking state when LLM starts
      setIsThinking(false);
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
      // Turn off thinking state when first token arrives
      setIsThinking(false);
      const id = streamingAssistantIdRef.current;
      if (!id) return;
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, content: (m.content || "") + (evt.content || "") } : m)));
    } else if (evt.type === "llm_end") {
      const id = streamingAssistantIdRef.current;
      if (!id) return;
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, isStreaming: false } : m)));
      streamingAssistantIdRef.current = null;
      setIsLoading(false);
    } else if (evt.type === "tool_start") {
      const id = streamingAssistantIdRef.current;
      if (!id) return;
      setMessages((prev) => prev.map((m) => (
        m.id === id
          ? {
              ...m,
              internalActivity: {
                summary: m.internalActivity?.summary || "Actions",
                bullets: [
                  ...(m.internalActivity?.bullets || []),
                  `Starting ${evt.tool_name || "tool"}`,
                ],
                doneLabel: m.internalActivity?.doneLabel || "Done",
                body: m.internalActivity?.body,
              },
            }
          : m
      )));
    } else if (evt.type === "tool_end") {
      const id = streamingAssistantIdRef.current;
      if (!id) return;
      const preview = (evt as any).output_preview || (evt as any).output || "Done";
      setMessages((prev) => prev.map((m) => (
        m.id === id
          ? {
              ...m,
              internalActivity: {
                summary: m.internalActivity?.summary || "Actions",
                bullets: [
                  ...(m.internalActivity?.bullets || []),
                  `Completed tool (${String(preview).slice(0, 80)}${String(preview).length > 80 ? "..." : ""})`,
                ],
                doneLabel: m.internalActivity?.doneLabel || "Done",
                body: m.internalActivity?.body,
              },
            }
          : m
      )));
    } else if (evt.type === "agent_action") {
      const id = streamingAssistantIdRef.current;
      if (!id) return;
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
    } else if (evt.type === "agent_result") {
      const id = streamingAssistantIdRef.current;
      if (!id) return;
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
      // Show a brief confirmation message
      const id = `assistant-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id,
          role: "assistant",
          content: evt.success
            ? `Generated ${evt.content_type.replace("_", " ")} content.`
            : `Generation failed: ${evt.error || "Unknown error"}`,
        },
      ]);
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
    }
  }, []);

  const { connected, send } = useChatSocket({ onEvent: handleSocketEvent });

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

  const handleNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setShowGettingStarted(false);
    setShowPersonalization(false);
  };

  const handleSelectConversation = async (id: string) => {
    setActiveConversationId(id);
    setShowGettingStarted(false);
    try {
      const msgs = await getConversationMessages(id);
      setMessages(
        msgs.map((m) => ({
          id: m.id,
          role: m.type === "user" ? "user" : "assistant",
          content: m.content || "",
        }))
      );
    } catch (e) {
      setMessages([]);
    }
  };

  const handleShowGettingStarted = () => {
    setShowGettingStarted(true);
    setShowPersonalization(false);
    setActiveConversationId(null);
    setMessages([]);
  };

  const handleShowPersonalization = () => {
    setShowPersonalization(true);
    setShowGettingStarted(false);
    setActiveConversationId(null);
    setMessages([]);
  };

  const handleSendMessage = async (content: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setIsThinking(true);

    // Ensure we have an active conversation id
    let convId = activeConversationId;
    if (!convId) {
      convId = `conv_${Date.now()}`;
      setActiveConversationId(convId);
      const newConversation: Conversation = {
        id: convId,
        title: content.slice(0, 30) + (content.length > 30 ? "..." : ""),
        timestamp: new Date(),
      };
      setConversations((prev) => [newConversation, ...prev]);
    }

    // Send to backend via WebSocket
    const ok = send({ message: content, conversation_id: convId });
    if (!ok) {
      // Fallback: show error and stop loading
      setMessages((prev) => [
        ...prev,
        { id: `assistant-${Date.now()}`, role: "assistant", content: "Connection error. Please try again." },
      ]);
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background relative pb-4 pt-3">
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

      <div className="w-80 flex-shrink-0 relative z-10">
        <ChatSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          onShowGettingStarted={handleShowGettingStarted}
          onShowPersonalization={handleShowPersonalization}
        />
      </div>

      <div className="flex flex-1 flex-col relative z-10">
        {showGettingStarted ? (
          <PromptLibrary onSelectPrompt={() => setShowGettingStarted(false)} />
        ) : showPersonalization ? (
          <div className="flex items-start justify-center p-6 h-full">
            <div className="w-full max-w-3xl">
              <Settings />
            </div>
          </div>
        ) : isEmpty ? (
          <div className="flex flex-1 items-center justify-center p-8">
            <div className="text-center space-y-6 max-w-2xl animate-fade-in">
              <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-primary to-accent shadow-xl animate-pulse-glow">
                <Sparkles className="h-10 w-10 text-white" />
              </div>
              <div className="space-y-2">
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
            <div className="mx-auto max-w-4xl">
              {messages.map((message) => (
                <ChatMessage key={message.id} {...message} />
              ))}
              <AnimatePresence>
                {isThinking && <ThinkingBubble />}
              </AnimatePresence>
            </div>
          </ScrollArea>
        )}

        {!showGettingStarted && !showPersonalization && (
          <div
            className={cn(
              "relative z-20 transition-transform duration-500 ease-out",
              // Lift the prompt up under the hero on empty state; return to bottom after first send
              isEmpty ? "-translate-y-[35vh] md:-translate-y-[30vh]" : "translate-y-0"
            )}
          >
            <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} showSuggestedPrompts={isEmpty} />
          </div>
        )}
      </div>
    </div>
  );
};

export default Index;
