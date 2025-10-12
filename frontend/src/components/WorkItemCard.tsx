import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Copy } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";

export type WorkItemCardProps = {
  title: string;
  description?: string;
  onCopy?: (field: "title" | "description") => void;
  className?: string;
};

export const WorkItemCard: React.FC<WorkItemCardProps> = ({ title, description = "", onCopy, className }) => {
  const [copied, setCopied] = React.useState<null | "title" | "description">(null);

  const handleCopy = async (field: "title" | "description") => {
    try {
      await navigator.clipboard.writeText(field === "title" ? title : description);
      setCopied(field);
      onCopy?.(field);
      window.setTimeout(() => setCopied(null), 2000);
    } catch {}
  };

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="text-lg leading-snug break-words">{title}</CardTitle>
            <CardDescription className="mt-1">Generated work item</CardDescription>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => handleCopy("title")}
              title="Copy title"
            >
              <Copy className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => handleCopy("description")}
              title="Copy description"
            >
              <Copy className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      {description && (
        <CardContent className="pt-0">
          <SafeMarkdown content={description} className="prose prose-sm max-w-none dark:prose-invert" />
        </CardContent>
      )}
    </Card>
  );
};

export default WorkItemCard;
