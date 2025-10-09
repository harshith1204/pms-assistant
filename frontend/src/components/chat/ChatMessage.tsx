import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { User, Bot, Brain, Wrench, Clock, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";

interface Message {
  id: string;
  type: "user" | "assistant" | "thought" | "tool" | "action" | "result";
  content: string;
  timestamp: string;
  toolName?: string;
  toolOutput?: unknown;
}

interface ChatMessageProps {
  message: Message;
  showToolOutputs?: boolean;
}

export function ChatMessage({ message, showToolOutputs = true }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getMessageIcon = () => {
    switch (message.type) {
      case "user":
        return <User className="h-4 w-4" />;
      case "assistant":
        return <Bot className="h-4 w-4" />;
      case "thought":
        return <Brain className="h-4 w-4" />;
      case "tool":
        return <Wrench className="h-4 w-4" />;
      case "action":
        return <Clock className="h-4 w-4" />;
      case "result":
        return <Check className="h-4 w-4" />;
      default:
        return <Bot className="h-4 w-4" />;
    }
  };

  const getMessageStyles = () => {
    switch (message.type) {
      case "user":
        return {
          container: "ml-auto max-w-[80%]",
          card: "bg-chat-bubble-user text-chat-bubble-user-foreground",
          icon: "bg-chat-bubble-user text-chat-bubble-user-foreground",
        };
      case "assistant":
        return {
          container: "mr-auto max-w-[80%]",
          card: "bg-chat-bubble-assistant text-chat-bubble-assistant-foreground border",
          icon: "bg-primary text-primary-foreground",
        };
      case "thought":
        return {
          container: "mr-auto max-w-[80%]",
          card: "bg-chat-bubble-thought text-chat-bubble-thought-foreground border border-accent/30",
          icon: "bg-accent text-accent-foreground",
        };
      case "tool":
        return {
          container: "mr-auto max-w-[80%]",
          card: "bg-chat-bubble-tool text-chat-bubble-tool-foreground border border-muted",
          icon: "bg-muted text-muted-foreground",
        };
      case "action":
        return {
          container: "mr-auto max-w-[80%]",
          card: "bg-muted/40 text-muted-foreground border border-muted/60",
          icon: "bg-muted text-muted-foreground",
        };
      case "result":
        return {
          container: "mr-auto max-w-[80%]",
          card: "bg-muted/30 text-foreground border border-muted/60",
          icon: "bg-green-500 text-white",
        };
      default:
        return {
          container: "mr-auto max-w-[80%]",
          card: "bg-card text-card-foreground border",
          icon: "bg-muted text-muted-foreground",
        };
    }
  };

  const styles = getMessageStyles();

  const renderToolOutput = () => {
    if (!message.toolOutput) return null;

    // Enhanced rendering for generated content and errors
    const renderGeneratedContent = (data: any) => {
      // Handle error objects
      if (data && data.error) {
        return (
          <div className="mt-3 p-3 bg-destructive/10 border border-destructive/20 rounded-md">
            <p className="text-xs font-medium mb-2 text-destructive">Generation Error:</p>
            <div className="text-xs text-destructive">
              <p><strong>Error:</strong> {data.error}</p>
              {data.contentType && <p><strong>Content Type:</strong> {data.contentType}</p>}
            </div>
          </div>
        );
      }

      if (!data || typeof data !== 'object') {
        return (
          <div className="mt-3 p-3 bg-muted/30 rounded-md">
            <p className="text-xs font-medium mb-2">Generated Content:</p>
            <pre className="text-xs font-mono whitespace-pre-wrap">{JSON.stringify(data, null, 2)}</pre>
          </div>
        );
      }

      // Extract meaningful information from generated content
      const contentInfo: string[] = [];

      if (data.title) contentInfo.push(`Title: ${data.title}`);
      if (data.name) contentInfo.push(`Name: ${data.name}`);
      if (data.content) contentInfo.push(`Content: ${data.content.substring(0, 200)}${data.content.length > 200 ? '...' : ''}`);
      if (data.description) contentInfo.push(`Description: ${data.description}`);
      if (data.status) contentInfo.push(`Status: ${data.status}`);
      if (data.priority) contentInfo.push(`Priority: ${data.priority}`);
      if (data.id) contentInfo.push(`ID: ${data.id}`);
      if (data.displayBugNo) contentInfo.push(`Bug #: ${data.displayBugNo}`);
      if (data.projectDisplayId) contentInfo.push(`Project: ${data.projectDisplayId}`);

      // If we have structured info, show it nicely
      if (contentInfo.length > 0) {
        return (
          <div className="mt-3 p-3 bg-muted/30 rounded-md">
            <p className="text-xs font-medium mb-2">Generated Content Details:</p>
            <div className="space-y-1">
              {contentInfo.map((info, index) => (
                <div key={index} className="text-xs p-2 bg-background/50 rounded border-l-2 border-primary/30">
                  {info}
                </div>
              ))}
            </div>
            {data.content && data.content.length > 200 && (
              <details className="mt-2">
                <summary className="text-xs font-medium cursor-pointer">View Full Content</summary>
                <pre className="text-xs font-mono whitespace-pre-wrap mt-2 p-2 bg-background/30 rounded">
                  {data.content}
                </pre>
              </details>
            )}
          </div>
        );
      }

      // Fallback for other objects
      return (
        <div className="mt-3 p-3 bg-muted/30 rounded-md">
          <p className="text-xs font-medium mb-2">Generated Content:</p>
          <pre className="text-xs font-mono whitespace-pre-wrap">{JSON.stringify(data, null, 2)}</pre>
        </div>
      );
    };

    if (Array.isArray(message.toolOutput)) {
      return (
        <div className="mt-3 p-3 bg-muted/30 rounded-md">
          <p className="text-xs font-medium mb-2">Output:</p>
          <div className="space-y-1">
            {(message.toolOutput as unknown[]).map((item: unknown, index: number) => (
              <Badge key={index} variant="outline" className="text-xs mr-1 mb-1">
                {typeof item === 'object' ? JSON.stringify(item) : String(item)}
              </Badge>
            ))}
          </div>
        </div>
      );
    }

    // If the tool output is a string, render it directly to preserve newlines and avoid JSON escaping
    if (typeof message.toolOutput === "string") {
      return (
        <div className="mt-3 p-3 bg-muted/30 rounded-md">
          <p className="text-xs font-medium mb-2">Output:</p>
          <pre className="text-xs font-mono whitespace-pre-wrap">{message.toolOutput}</pre>
        </div>
      );
    }

    // Handle generated content objects
    return renderGeneratedContent(message.toolOutput);
  };

  return (
    <div className={cn("flex gap-3", styles.container)}>
      {/* Avatar */}
      <div className={cn(
        "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
        styles.icon
      )}>
        {getMessageIcon()}
      </div>

      {/* Message Content */}
      <div className="flex-1 min-w-0">
        <Card className={cn("p-4", styles.card)}>
          {/* Header */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              {message.type === "thought" && (
                <Badge variant="secondary" className="text-xs">
                  <Brain className="h-3 w-3 mr-1" />
                  Thought Process
                </Badge>
              )}
              {message.type === "tool" && message.toolName && (
                <Badge variant="outline" className="text-xs">
                  <Wrench className="h-3 w-3 mr-1" />
                  {message.toolName}
                </Badge>
              )}
              {message.type === "action" && (
                <Badge variant="secondary" className="text-xs">
                  In progress
                </Badge>
              )}
              {message.type === "result" && (
                <Badge variant="outline" className="text-xs">
                  <Check className="h-3 w-3 mr-1" />
                  Generated
                </Badge>
              )}
            </div>
            
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 text-xs opacity-60">
                <Clock className="h-3 w-3" />
                {message.timestamp}
              </div>
              
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
                onClick={copyToClipboard}
              >
                {copied ? (
                  <Check className="h-3 w-3 text-green-500" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>
            </div>
          </div>

          {/* Content */}
          <div className="prose prose-sm max-w-none">
            <div className="whitespace-pre-wrap text-sm">
              {message.content}
            </div>
            
            {(message.type === "tool" || message.type === "result" || (message.type === "assistant" && message.toolOutput)) && showToolOutputs && renderToolOutput()}
          </div>
        </Card>
      </div>
    </div>
  );
}