import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, StopCircle, Brain, Eye, EyeOff } from "lucide-react";
import { ChatMessage } from "./ChatMessage";
import { useToast } from "@/hooks/use-toast";

interface Message {
  id: string;
  type: "user" | "assistant" | "tool";
  content: string;
  timestamp: string;
  toolName?: string;
  toolOutput?: any;
  thoughts?: string; // Optional field to store thinking content
}

const initialMessages: Message[] = [
  {
    id: "1",
    type: "assistant",
    content: "Hello! I'm your Project Management System Assistant. I can help you manage projects, tasks, and interact with your MongoDB database. What would you like to do?",
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  },
];

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [showThinking, setShowThinking] = useState(true);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { toast } = useToast();

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: input.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages(prev => [...prev, userMessage]);
    const currentInput = input.trim();
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: currentInput,
          conversation_id: conversationId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // Parse thinking content from response
      const responseContent = data.response;
      const thinkMatch = responseContent.match(/<think>([\s\S]*?)<\/think>/);

      let thinkingContent: string | undefined;
      let finalResponse: string;

      if (thinkMatch) {
        // Extract thinking content and final response
        thinkingContent = thinkMatch[1].trim();
        finalResponse = responseContent.replace(/<think>[\s\S]*?<\/think>/, '').trim();
      } else {
        // No thinking content
        finalResponse = responseContent;
      }

      // Add assistant message with optional thoughts
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: "assistant",
        content: finalResponse,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        thoughts: thinkingContent,
      };

      setMessages(prev => [...prev, assistantMessage]);

      setConversationId(data.conversation_id);

    } catch (error) {
      console.error("Error sending message:", error);
      toast({
        title: "Error",
        description: "Failed to send message. Please check if the backend is running.",
        variant: "destructive",
      });

      // Re-enable input on error
      setInput(currentInput);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  const stopGeneration = () => {
    setIsLoading(false);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <ScrollArea ref={scrollAreaRef} className="flex-1 p-4">
        <div className="space-y-4 max-w-4xl mx-auto">
          {messages.map((message) => (
            <ChatMessage 
              key={message.id} 
              message={message} 
              showThinking={showThinking}
            />
          ))}

          {isLoading && (
            <div className="flex justify-center">
              <div className="flex items-center gap-2 text-muted-foreground">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                <span className="text-sm">Agent is thinking...</span>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input Area */}
      <div className="border-t bg-card p-4">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your message..."
                className="min-h-[60px] max-h-[120px] resize-none pr-12"
                disabled={isLoading}
              />
              <div className="absolute bottom-2 right-2 flex gap-1">
                {isLoading ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={stopGeneration}
                    className="h-8 w-8 p-0"
                  >
                    <StopCircle className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!input.trim()}
                    className="h-8 w-8 p-0"
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
          </div>
          <div className="flex justify-between items-center mt-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <span>Press Enter to send, Shift+Enter for new line</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setShowThinking(!showThinking)}
                className="h-6 px-2 text-xs"
              >
                <Brain className="h-3 w-3 mr-1" />
                {showThinking ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                <span className="ml-1">{showThinking ? "Hide" : "Show"} Thinking</span>
              </Button>
            </div>
            <span>{input.length}/2000</span>
          </div>
        </form>
      </div>
    </div>
  );
}