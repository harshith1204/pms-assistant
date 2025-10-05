import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, StopCircle, Brain, Eye, EyeOff, Wifi, WifiOff, Wrench } from "lucide-react";
import { ChatMessage } from "./ChatMessage";
import { useToast } from "@/hooks/use-toast";
import { useWebSocket } from "@/hooks/use-websocket";

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
  const [showToolOutputs, setShowToolOutputs] = useState(true);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState<string>("");
  const [currentStreamingId, setCurrentStreamingId] = useState<string | null>(null);
  const [currentThoughtMessage, setCurrentThoughtMessage] = useState<string>("");
  const [currentThoughtId, setCurrentThoughtId] = useState<string | null>(null);
  const [isInThinkingMode, setIsInThinkingMode] = useState<boolean>(false);
  const currentStreamingMessageRef = useRef<string>("");
  const currentStreamingIdRef = useRef<string | null>(null);
  const currentThoughtMessageRef = useRef<string>("");
  const currentThoughtIdRef = useRef<string | null>(null);
  const isInThinkingModeRef = useRef<boolean>(false);
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
        currentStreamingIdRef.current = messageId;
        setCurrentStreamingMessage("");
        currentStreamingMessageRef.current = "";
        setCurrentThoughtMessage("");
        currentThoughtMessageRef.current = "";
        setCurrentThoughtId(null);
        currentThoughtIdRef.current = null;
        setIsInThinkingMode(false);
        isInThinkingModeRef.current = false;
        break;

      case "token":
        const token = data.content;
        
        // Check for think tags
        if (!isInThinkingModeRef.current) {
          // Not in thinking mode - check if we're starting
          const currentFullContent = currentStreamingMessageRef.current + token;
          
          if (currentFullContent.includes('<think>')) {
            // Starting thinking mode
            const thinkStartIndex = currentFullContent.indexOf('<think>');
            const beforeThink = currentFullContent.substring(0, thinkStartIndex);
            const afterThink = currentFullContent.substring(thinkStartIndex + 7); // 7 is length of '<think>'

            // Add content before <think> to regular message
            if (beforeThink) {
              setCurrentStreamingMessage(beforeThink);
              currentStreamingMessageRef.current = beforeThink;
            }

            // Start thought message
            const thoughtId = Date.now().toString();
            setCurrentThoughtId(thoughtId);
            currentThoughtIdRef.current = thoughtId;
            setCurrentThoughtMessage(afterThink);
            currentThoughtMessageRef.current = afterThink;
            setIsInThinkingMode(true);
            isInThinkingModeRef.current = true;
          } else {
            // Regular content
            setCurrentStreamingMessage(prev => prev + token);
            currentStreamingMessageRef.current += token;
          }
        } else {
          // In thinking mode - check if we're ending
          const currentThoughtContent = currentThoughtMessageRef.current + token;
          
          if (currentThoughtContent.includes('</think>')) {
            // Ending thinking mode
            const thinkEndIndex = currentThoughtContent.indexOf('</think>');
            const thoughtContent = currentThoughtContent.substring(0, thinkEndIndex);
            const afterEndThink = currentThoughtContent.substring(thinkEndIndex + 8); // 8 is length of '</think>'

            // Update thought message
            setCurrentThoughtMessage(thoughtContent);
            currentThoughtMessageRef.current = thoughtContent;

          // Add thought message to messages array
          if (currentThoughtIdRef.current && thoughtContent) {
            const thoughtMessage: Message = {
              id: currentThoughtIdRef.current,
              type: "thought",
              content: thoughtContent,
              timestamp,
            };
            console.log("Adding thought message on </think>:", thoughtMessage);
            setMessages(prev => {
              console.log("Previous messages count:", prev.length);
              console.log("Previous messages types:", prev.map(m => m.type));
              const newMessages = [...prev, thoughtMessage];
              console.log("New messages count:", newMessages.length);
              console.log("New messages types:", newMessages.map(m => m.type));
              return newMessages;
            });
          }

          // Reset thought state
          setCurrentThoughtMessage("");
          currentThoughtMessageRef.current = "";
          setCurrentThoughtId(null);
          currentThoughtIdRef.current = null;
          setIsInThinkingMode(false);
          isInThinkingModeRef.current = false;

            // Add remaining content after </think> to regular message
            if (afterEndThink) {
              setCurrentStreamingMessage(prev => prev + afterEndThink);
              currentStreamingMessageRef.current = currentStreamingMessageRef.current + afterEndThink;
            }
          } else {
            // Accumulate thought content
            setCurrentThoughtMessage(prev => prev + token);
            currentThoughtMessageRef.current += token;
          }
        }
        break;

      case "llm_end":
        console.log("LLM_END event received");
        console.log("isInThinkingMode:", isInThinkingModeRef.current);
        console.log("currentThoughtId:", currentThoughtIdRef.current);
        console.log("currentThoughtMessage:", currentThoughtMessageRef.current);
        
        // Handle any remaining thought content
        if (isInThinkingModeRef.current && currentThoughtIdRef.current && currentThoughtMessageRef.current) {
          const thoughtMessage: Message = {
            id: currentThoughtIdRef.current,
            type: "thought",
            content: currentThoughtMessageRef.current,
            timestamp,
          };
          console.log("Adding thought message on llm_end:", thoughtMessage);
          setMessages(prev => {
            console.log("Previous messages count before thought:", prev.length);
            console.log("Previous messages types:", prev.map(m => m.type));
            const newMessages = [...prev, thoughtMessage];
            console.log("New messages count after thought:", newMessages.length);
            console.log("New messages types:", newMessages.map(m => m.type));
            return newMessages;
          });
        }

        // Add final assistant message if there's content
        if (currentStreamingIdRef.current && currentStreamingMessageRef.current) {
          const newMessage: Message = {
            id: currentStreamingIdRef.current,
            type: "assistant",
            content: currentStreamingMessageRef.current,
            timestamp,
          };
          setMessages(prev => [...prev, newMessage]);
        }

        // Clear all streaming state
        setCurrentStreamingMessage("");
        currentStreamingMessageRef.current = "";
        setCurrentStreamingId(null);
        currentStreamingIdRef.current = null;
        setCurrentThoughtMessage("");
        currentThoughtMessageRef.current = "";
        setCurrentThoughtId(null);
        currentThoughtIdRef.current = null;
        setIsInThinkingMode(false);
        isInThinkingModeRef.current = false;
        setIsLoading(false);
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
          content: data.output || "Tool execution completed",
          timestamp,
          toolOutput: data.output,
          toolName: data.tool_name,
        };
        // Attach optional metadata for export re-run
        (toolEndMessage as any).args = data.args;
        (toolEndMessage as any).input = data.input;
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
  }, [toast]);
  
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

  // Sync refs with state
  useEffect(() => {
    currentStreamingMessageRef.current = currentStreamingMessage;
  }, [currentStreamingMessage]);

  useEffect(() => {
    currentStreamingIdRef.current = currentStreamingId;
  }, [currentStreamingId]);

  useEffect(() => {
    currentThoughtMessageRef.current = currentThoughtMessage;
  }, [currentThoughtMessage]);

  useEffect(() => {
    currentThoughtIdRef.current = currentThoughtId;
  }, [currentThoughtId]);

  useEffect(() => {
    isInThinkingModeRef.current = isInThinkingMode;
  }, [isInThinkingMode]);

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
          {(() => {
            const allMessages = messages;
            const filteredMessages = allMessages.filter((message) => showThinking || message.type !== "thought");
            console.log("All messages:", allMessages.length, allMessages.map(m => ({ type: m.type, content: m.content.substring(0, 50) + "..." })));
            console.log("Filtered messages (showThinking=" + showThinking + "):", filteredMessages.length);
            return filteredMessages.map((message) => (
              <ChatMessage key={message.id} message={message} showToolOutputs={showToolOutputs} />
            ));
          })()}
            
          {/* Show streaming thought message if available */}
          {currentThoughtMessage && currentThoughtId && (
            <ChatMessage
              message={{
                id: currentThoughtId,
                type: "thought",
                content: currentThoughtMessage,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              }}
            />
          )}

          {/* Show streaming message if available */}
          {currentStreamingMessage && currentStreamingId && (
            <ChatMessage
              message={{
                id: currentStreamingId,
                type: "assistant",
                content: currentStreamingMessage,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              }}
            />
          )}

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
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setShowToolOutputs(!showToolOutputs)}
                className="h-6 px-2 text-xs"
              >
                <Wrench className="h-3 w-3 mr-1" />
                {showToolOutputs ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                <span className="ml-1">{showToolOutputs ? "Hide" : "Show"} Tool Outputs</span>
              </Button>
            </div>
            <span>{input.length}/2000</span>
          </div>
        </form>
      </div>
    </div>
  );
}