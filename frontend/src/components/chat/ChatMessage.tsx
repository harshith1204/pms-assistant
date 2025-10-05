import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { User, Bot, Brain, Wrench, Clock, Copy, Check, FileDown, FileSpreadsheet, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";

interface Message {
  id: string;
  type: "user" | "assistant" | "thought" | "tool";
  content: string;
  timestamp: string;
  toolName?: string;
  toolOutput?: any;
  tools?: any[];
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

  const exportRows = async (format: "csv" | "xlsx" | "docx") => {
    try {
      const endpoint = `/export/${format}`;
      const isDocx = format === "docx";
      const body: any = {};
      // If we have tool metadata from backend events, pass them through to re-run
      // Our backend streams tool_end with optional tool_name, args
      const toolName = (message as any).toolName || (message as any).tool_name || undefined;
      const args = (message as any).args || undefined;
      const inputRaw = (message as any).input || undefined;
      const content = !toolName && typeof message.content === "string" ? message.content : undefined;

      if (toolName === "mongo_query" && args?.query) {
        body.tool = "mongo_query";
        body.query = args.query;
        body.params = args;
        body.title = "Mongo Query Export";
      } else if (isDocx && content) {
        // Fallback: export current assistant/tool text as DOCX paragraphs
        body.content = content;
        body.title = "Conversation Export";
      } else {
        // Try to parse toolOutput as JSON rows if possible
        try {
          const parsed = typeof message.toolOutput === "string" ? JSON.parse(message.toolOutput) : message.toolOutput;
          if (Array.isArray(parsed)) {
            body.rows = parsed;
          } else if (parsed && typeof parsed === "object") {
            body.rows = [parsed];
          }
        } catch {
          // ignore
        }
        body.title = "Export";
      }

      const res = await fetch(`/api${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        throw new Error(await res.text());
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `export.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Export failed", e);
      // no toast here to avoid importing hooks in this leaf component
    }
  };

  const exportFromAssistant = async (format: "csv" | "xlsx" | "docx") => {
    try {
      const endpoint = `/export/${format}`;
      const isDocx = format === "docx";
      const body: any = { title: "Assistant Export" };
      // Prefer mongo_query tool in this turn if present
      const tools = (message as any).tools as any[] | undefined;
      const mq = tools?.find(t => t?.tool_name === "mongo_query" && t?.args?.query);
      if (mq) {
        body.tool = "mongo_query";
        body.query = mq.args.query;
        body.params = mq.args;
      } else if (isDocx) {
        body.content = message.content;
      } else {
        // Try to parse lists rendered in content is out of scope; expect tool rows
        body.rows = [];
      }
      const res = await fetch(`/api${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `export.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Export failed", e);
    }
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
            {message.toolOutput.map((item: any, index: number) => (
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
        <pre className="text-xs font-mono whitespace-pre-wrap">{JSON.stringify(message.toolOutput, null, 2)}</pre>
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

            {(message.type === "tool" || message.type === "assistant") && (
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" className="h-6 px-2" onClick={() => (message.type === "assistant" ? exportFromAssistant("csv") : exportRows("csv"))} title="Export CSV">
                  <FileDown className="h-3 w-3" />
                </Button>
                <Button variant="ghost" size="sm" className="h-6 px-2" onClick={() => (message.type === "assistant" ? exportFromAssistant("xlsx") : exportRows("xlsx"))} title="Export Excel">
                  <FileSpreadsheet className="h-3 w-3" />
                </Button>
                <Button variant="ghost" size="sm" className="h-6 px-2" onClick={() => (message.type === "assistant" ? exportFromAssistant("docx") : exportRows("docx"))} title="Export Word">
                  <FileText className="h-3 w-3" />
                </Button>
              </div>
            )}
            </div>
          </div>

          {/* Content */}
          <div className="prose prose-sm max-w-none">
            <div className="whitespace-pre-wrap text-sm">
              {message.content}
            </div>
            
            {message.type === "tool" && showToolOutputs && renderToolOutput()}
          </div>
        </Card>
      </div>
    </div>
  );
}