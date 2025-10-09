import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { User, Bot, Brain, Wrench, Clock, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { EditorJsViewer } from "@/components/ui/EditorJsViewer";

interface Message {
  id: string;
  type: "user" | "assistant" | "thought" | "tool" | "action" | "result" | "work_item" | "page";
  content: string;
  timestamp: string;
  toolName?: string;
  toolOutput?: unknown;
  // Optional rich payloads
  blocks?: unknown[]; // Editor.js blocks
  title?: string;
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
      case "work_item":
        return <Bot className="h-4 w-4" />;
      case "page":
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
      case "work_item":
      case "page":
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

    if (Array.isArray(message.toolOutput)) {
      return (
        <div className="mt-3 p-3 bg-muted/30 rounded-md">
          <p className="text-xs font-medium mb-2">Output:</p>
          <div className="space-y-1">
            {(message.toolOutput as unknown[]).map((item: unknown, index: number) => (
              <Badge key={index} variant="outline" className="text-xs mr-1 mb-1">
                {item}
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

    // Fallback for objects
    return (
      <div className="mt-3 p-3 bg-muted/30 rounded-md">
        <p className="text-xs font-medium mb-2">Output:</p>
        <pre className="text-xs font-mono whitespace-pre-wrap">{JSON.stringify(message.toolOutput as unknown, null, 2)}</pre>
      </div>
    );
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
                  Completed
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
            {/* Rich: work item or page preview */}
            {message.title && (
              <div className="text-base font-semibold mb-2">{message.title}</div>
            )}
            {message.type === "page" && Array.isArray(message.blocks) && message.blocks.length > 0 ? (
              <EditorJsViewer blocks={message.blocks} />
            ) : (
              <div className="whitespace-pre-wrap text-sm">
                {message.content}
              </div>
            )}

            {message.type === "tool" && showToolOutputs && renderToolOutput()}
          </div>
        </Card>
      </div>
    </div>
  );
}