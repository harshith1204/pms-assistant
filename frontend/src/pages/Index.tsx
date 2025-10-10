import { useState } from "react";
import { cn } from "@/lib/utils";
import { ChatSidebar } from "@/components/ChatSidebar";
import { ChatMessage } from "@/components/ChatMessage";
import { ChatInput } from "@/components/ChatInput";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sparkles } from "lucide-react";
import PromptLibrary from "@/components/PromptLibrary";
import Settings from "@/pages/Settings";

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
  const [conversations, setConversations] = useState<Conversation[]>([
    {
      id: "1",
      title: "Product Roadmap Planning",
      timestamp: new Date(Date.now() - 86400000),
    },
    {
      id: "2",
      title: "Sprint Task Breakdown",
      timestamp: new Date(Date.now() - 172800000),
    },
  ]);
  
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [showGettingStarted, setShowGettingStarted] = useState<boolean>(false);
  const [showPersonalization, setShowPersonalization] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState(false);
  const isEmpty = messages.length === 0;

  const handleNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setShowGettingStarted(false);
    setShowPersonalization(false);
  };

  const handleSelectConversation = (id: string) => {
    setActiveConversationId(id);
    // In a real app, load messages for this conversation
    setMessages([
      {
        id: "1",
        role: "assistant",
        content: "Hello! I'm your AI Project Manager assistant. I can help you create pages, manage tasks, plan sprints, and organize your product development workflow. What would you like to work on today?",
      },
    ]);
    setShowGettingStarted(false);
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

    // Simulate AI response with streaming effect
    setTimeout(() => {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "I understand you want to work on that. As your AI Project Manager, I can help you break this down into actionable tasks, create a structured plan, and organize it into our canvas. Let me help you get started with a detailed breakdown...",
        isStreaming: true,
        internalActivity: {
          summary: "Actions",
          bullets: [
            "The user wants a plan; include UI/UX vocabulary",
            "Provide structured phases and keep tone professional"
          ],
          doneLabel: "Done",
          body: "Below is a high-level blueprint for building a flexible, scalable design system that spans both web and mobile. I've organized it into four phases—Strategy, Foundations, Components & Patterns, and Governance & Documentation—and used UI/UX professional vocabulary throughout.",
        },
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);

      // Create new conversation if this is the first message
      if (!activeConversationId) {
        const newConversation: Conversation = {
          id: Date.now().toString(),
          title: content.slice(0, 30) + (content.length > 30 ? "..." : ""),
          timestamp: new Date(),
        };
        setConversations((prev) => [newConversation, ...prev]);
        setActiveConversationId(newConversation.id);
      }
    }, 1000);
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
