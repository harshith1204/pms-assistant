import React from "react";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Copy, Flag, Target, Users, Lightbulb, Boxes } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";
import { cn } from "@/lib/utils";

export type UserStoryCardProps = {
  title: string;
  description?: string;
  displayBugNo?: string;
  persona?: string;
  userGoal?: string;
  demographics?: string;
  acceptanceCriteria?: string;
  priority?: string | null;
  state?: string | null;
  assignees?: string[];
  epic?: string | null;
  feature?: string | null;
  module?: string | null;
  labels?: string[];
  link?: string | null;
  onCopy?: (field: "title" | "description" | "link") => void;
  className?: string;
};

export const UserStoryCard: React.FC<UserStoryCardProps> = ({
  title,
  description = "",
  displayBugNo,
  persona,
  userGoal,
  demographics,
  acceptanceCriteria,
  priority,
  state,
  assignees = [],
  epic,
  feature,
  module,
  labels = [],
  link,
  onCopy,
  className
}) => {
  const [copied, setCopied] = React.useState<null | "title" | "description" | "link">(null);

  const handleCopy = async (field: "title" | "description" | "link") => {
    try {
      const text = field === "title" ? title : field === "description" ? description : link || "";
      if (!text) return;
      await navigator.clipboard.writeText(text);
      setCopied(field);
      onCopy?.(field);
      window.setTimeout(() => setCopied(null), 2000);
    } catch {
      // Clipboard write failed, ignore silently
    }
  };

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>User Story</span>
              {displayBugNo && (
                <Badge variant="outline" className="text-xs">{displayBugNo}</Badge>
              )}
            </div>
            <div className="mt-0.5 text-base font-semibold leading-snug break-words">{title}</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {priority && priority !== "NONE" && (
                <Badge variant="outline" className="text-xs gap-1">
                  <Flag className="h-3 w-3" />
                  {priority}
                </Badge>
              )}
              {state && (
                <Badge variant="outline" className="text-xs gap-1">
                  <Target className="h-3 w-3" />
                  {state}
                </Badge>
              )}
              {assignees.length > 0 && (
                <Badge variant="outline" className="text-xs gap-1">
                  <Users className="h-3 w-3" />
                  {assignees.length} assignee{assignees.length > 1 ? 's' : ''}
                </Badge>
              )}
              {epic && (
                <Badge variant="secondary" className="text-xs gap-1">
                  <Target className="h-3 w-3" />
                  {epic}
                </Badge>
              )}
              {feature && (
                <Badge variant="secondary" className="text-xs gap-1">
                  <Lightbulb className="h-3 w-3" />
                  {feature}
                </Badge>
              )}
              {module && (
                <Badge variant="secondary" className="text-xs gap-1">
                  <Boxes className="h-3 w-3" />
                  {module}
                </Badge>
              )}
              {labels.map((label) => (
                <Badge key={label} variant="secondary" className="text-xs">
                  {label}
                </Badge>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1 text-xs">
            {link && (
              <a
                href={link}
                target="_blank"
                rel="noopener noreferrer"
                className={cn("px-2 py-1 rounded hover:bg-muted transition-colors text-primary")}
              >
                View story
              </a>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2"
              onClick={() => handleCopy(link ? "link" : "title")}
              title="Copy"
            >
              <Copy className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        {description && (
          <div>
            <h4 className="text-sm font-medium mb-1">Description</h4>
            <SafeMarkdown content={description} className="prose prose-sm max-w-none dark:prose-invert" />
          </div>
        )}
        {persona && (
          <div>
            <h4 className="text-sm font-medium mb-1">Persona</h4>
            <p className="text-sm text-muted-foreground">{persona}</p>
          </div>
        )}
        {userGoal && (
          <div>
            <h4 className="text-sm font-medium mb-1">User Goal</h4>
            <p className="text-sm text-muted-foreground">{userGoal}</p>
          </div>
        )}
        {demographics && (
          <div>
            <h4 className="text-sm font-medium mb-1">Demographics</h4>
            <p className="text-sm text-muted-foreground">{demographics}</p>
          </div>
        )}
        {acceptanceCriteria && (
          <div>
            <h4 className="text-sm font-medium mb-1">Acceptance Criteria</h4>
            <p className="text-sm text-muted-foreground">{acceptanceCriteria}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default UserStoryCard;
