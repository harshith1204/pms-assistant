import { useEffect, useState } from "react";
import { Bot, User, Copy, ThumbsUp, ThumbsDown } from "lucide-react";
import { cn } from "@/lib/utils";
import SafeMarkdown from "@/components/SafeMarkdown";
import { Button } from "@/components/ui/button";
import { AgentActivity } from "@/components/AgentActivity";
import { usePersonalization } from "@/context/PersonalizationContext";

interface ChatMessageProps {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  liked?: boolean;
  onLike?: (messageId: string) => void;
  onDislike?: (messageId: string) => void;
  internalActivity?: {
    summary: string;
    bullets?: string[];
    doneLabel?: string;
    body?: string;
  };
  workItem?: {
    title: string;
    description?: string;
  };
}

import WorkItemCard from "@/components/WorkItemCard";

export const ChatMessage = ({ id, role, content, isStreaming = false, liked, onLike, onDislike, internalActivity, workItem }: ChatMessageProps) => {
  const { settings } = usePersonalization();
  const [displayedContent, setDisplayedContent] = useState("");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [copied, setCopied] = useState(false);
  const canShowActions = role === "assistant" && !isStreaming && (displayedContent?.trim()?.length ?? 0) > 0;

  useEffect(() => {
    if (role === "assistant" && isStreaming) {
      if (currentIndex < content.length) {
        const timeout = setTimeout(() => {
          setDisplayedContent(content.slice(0, currentIndex + 1));
          setCurrentIndex(currentIndex + 1);
        }, 20);
        return () => clearTimeout(timeout);
      }
    } else {
      setDisplayedContent(content);
    }
  }, [content, currentIndex, role, isStreaming]);

  const isUser = role === "user";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const handleThumbsUp = () => {
    if (isStreaming) return;
    onLike?.(id);
  };

  const handleThumbsDown = () => {
    if (isStreaming) return;
    onDislike?.(id);
  };

  const isLiked = liked === true;
  const isDisliked = liked === false;

  return (
    <div className="p-6 animate-fade-in">
      {isUser ? (
        <div className="flex gap-4 flex-row-reverse">
          <div className="flex-1 text-right">
            <div className="flex justify-end">
              <div className="inline-block max-w-[80%] px-5 py-1 rounded-full text-sm text-foreground leading-relaxed whitespace-pre-wrap bg-primary/10  text-right">
                {displayedContent}
                {isStreaming && currentIndex < content.length && (
                  <span className="inline-block w-1 h-4 ml-1 bg-primary animate-pulse" />
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {settings.showAgentInternals && internalActivity && (
            <AgentActivity
              summary={internalActivity.summary}
              bullets={internalActivity.bullets}
              doneLabel={internalActivity.doneLabel}
              body={internalActivity.body}
              defaultOpen={isStreaming}
              isStreaming={isStreaming}
            />
          )}

          {workItem ? (
            <WorkItemCard title={workItem.title} description={workItem.description} className="mt-1" />
          ) : (
            <SafeMarkdown
              content={displayedContent}
              className="prose prose-sm max-w-none dark:prose-invert"
            />
          )}
          {isStreaming && currentIndex < content.length && (
            <span className="inline-block w-1 h-4 ml-1 bg-primary animate-pulse" />
          )}

          {/* Action buttons for assistant messages */}
          {canShowActions && (
            <div className="flex items-center gap-1 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCopy}
                className={cn(
                  "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-primary/10 transition-all duration-200 rounded-md",
                  copied && "text-green-600 bg-green-600/10"
                )}
              >
                <Copy className="h-4 w-4" />
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleThumbsUp}
                className={cn(
                  "h-8 px-2 transition-all duration-200 rounded-md",
                  isLiked
                    ? "text-green-600 hover:text-green-700 bg-green-600/10"
                    : "text-muted-foreground hover:text-foreground hover:bg-primary/10"
                )}
              >
                <ThumbsUp className={cn("h-4 w-4", isLiked && "fill-current")} />
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleThumbsDown}
                className={cn(
                  "h-8 px-2 transition-all duration-200 rounded-md",
                  isDisliked
                    ? "text-red-600 hover:text-red-700 bg-red-600/10"
                    : "text-muted-foreground hover:text-foreground hover:bg-primary/10"
                )}
              >
                <ThumbsDown className={cn("h-4 w-4", isDisliked && "fill-current")} />
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
