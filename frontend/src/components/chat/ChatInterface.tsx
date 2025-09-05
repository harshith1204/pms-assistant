import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, StopCircle, Brain, Eye, EyeOff, Wifi, WifiOff } from "lucide-react";
import { ChatMessage } from "./ChatMessage";
import { useToast } from "@/hooks/use-toast";
import { useWebSocket } from "@/hooks/use-websocket";
import { parseThinkTags } from "@/lib/message-parser";

interface Message {
  id: string;
  type: "user" | "assistant" | "thought" | "tool";
  content: string;
  timestamp: string;
  toolName?: string;
  toolOutput?: any;
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
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState<string>("");
  const [currentStreamingId, setCurrentStreamingId] = useState<string | null>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { toast } = useToast();
  
  // WebSocket connection
  const wsUrl = `ws://${window.location.hostname}:8000/ws/chat`;
  
  const handleWebSocketMessage = useCallback((data: any) => {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    switch (data.type) {
      case "connected":
        console.log("Connected to chat server", data.client_id);
        break;
        
      case "user_message":
        setConversationId(data.conversation_id);
        break;
        
      case "llm_start":
        setIsLoading(true);
        const messageId = Date.now().toString();
        setCurrentStreamingId(messageId);
        setCurrentStreamingMessage("");
        break;
        
      case "token":
        setCurrentStreamingMessage(prev => prev + data.content);
        break;
        
      case "llm_end":
        if (currentStreamingId && currentStreamingMessage) {
          // Parse think tags from the accumulated message
          const parsed = parseThinkTags(currentStreamingMessage);
          const newMessages: Message[] = [];
          
          // Add thought messages if any
          parsed.thoughts.forEach((thought, index) => {
            newMessages.push({
              id: `${currentStreamingId}-thought-${index}`,
              type: "thought",
              content: thought,
              timestamp,
            });
          });
          
          // Add the main assistant message (without think tags)
          if (parsed.mainContent) {
            newMessages.push({
              id: currentStreamingId,
              type: "assistant",
              content: parsed.mainContent,
              timestamp,
            });
          }
          
          // Add all messages at once
          setMessages(prev => [...prev, ...newMessages]);
          setCurrentStreamingMessage("");
          setCurrentStreamingId(null);
        }
        break;
        
      case "tool_start":
        const toolStartMessage: Message = {
          id: Date.now().toString(),
          type: "tool",
          content: `Calling ${data.tool_name}...`,
          timestamp,
          toolName: data.tool_name,
        };
        setMessages(prev => [...prev, toolStartMessage]);
        break;
        
      case "tool_end":
        const toolEndMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: "tool",
          content: data.output,
          timestamp,
          toolOutput: data.output,
        };
        setMessages(prev => [...prev, toolEndMessage]);
        break;
        
      case "complete":
        setIsLoading(false);
        break;
        
      case "error":
        toast({
          title: "Error",
          description: data.message || "An error occurred",
          variant: "destructive",
        });
        setIsLoading(false);
        break;
    }
  }, [currentStreamingId, currentStreamingMessage, toast]);
  
  const { isConnected, isConnecting, sendMessage } = useWebSocket({
    url: wsUrl,
    onMessage: handleWebSocketMessage,
    onOpen: () => {
      toast({
        title: "Connected",
        description: "Connected to chat server",
      });
    },
    onClose: () => {
      console.log("Disconnected from chat server");
    },
    onError: (error) => {
      console.error("WebSocket error:", error);
      toast({
        title: "Connection Error",
        description: "Failed to connect to chat server",
        variant: "destructive",
      });
    },
  });

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
    if (!input.trim() || isLoading || !isConnected) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: input.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages(prev => [...prev, userMessage]);
    const currentInput = input.trim();
    setInput("");
    
    // Send message via WebSocket
    const success = sendMessage({
      type: "message",
      message: currentInput,
      conversation_id: conversationId,
    });
    
    if (!success) {
      toast({
        title: "Error",
        description: "Failed to send message. Not connected to server.",
        variant: "destructive",
      });
      setInput(currentInput);
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
          {messages
            .filter((message) => showThinking || message.type !== "thought")
            .map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            
          {/* Show streaming message if available */}
          {currentStreamingMessage && (() => {
            // Parse think tags from the streaming content
            const parsed = parseThinkTags(currentStreamingMessage);
            const streamingMessages: JSX.Element[] = [];
            
            // Show thought messages if any complete think tags are found
            parsed.thoughts.forEach((thought, index) => {
              if (showThinking) {
                streamingMessages.push(
                  <ChatMessage
                    key={`streaming-thought-${index}`}
                    message={{
                      id: `streaming-thought-${index}`,
                      type: "thought",
                      content: thought,
                      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    }}
                  />
                );
              }
            });
            
            // Show main content (which may still have incomplete think tags)
            if (parsed.mainContent || (!parsed.thoughts.length && currentStreamingMessage)) {
              streamingMessages.push(
                <ChatMessage
                  key="streaming-main"
                  message={{
                    id: currentStreamingId || "streaming",
                    type: "assistant",
                    content: parsed.mainContent || currentStreamingMessage,
                    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                  }}
                />
              );
            }
            
            return streamingMessages;
          })()}

          {isLoading && !currentStreamingMessage && (
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
                    disabled={!input.trim() || !isConnected}
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
              <span className="flex items-center gap-1">
                {isConnected ? (
                  <Wifi className="h-3 w-3 text-green-500" />
                ) : isConnecting ? (
                  <Wifi className="h-3 w-3 text-yellow-500 animate-pulse" />
                ) : (
                  <WifiOff className="h-3 w-3 text-red-500" />
                )}
                {isConnected ? "Connected" : isConnecting ? "Connecting..." : "Disconnected"}
              </span>
              <span className="mx-2">•</span>
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