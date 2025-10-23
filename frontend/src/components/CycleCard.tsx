import React from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Copy, Calendar } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";
import { cn } from "@/lib/utils";

export type CycleCardProps = {
  title: string;
  description?: string;
  startDate?: string;
  endDate?: string;
  link?: string;
  onCopy?: (field: "title" | "description" | "link") => void;
  className?: string;
};

export const CycleCard: React.FC<CycleCardProps> = ({ 
  title, 
  description = "", 
  startDate, 
  endDate, 
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
    } catch {}
  };

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
              <Calendar className="h-3.5 w-3.5" />
              <span className="font-medium">Cycle</span>
            </div>
            <div className="text-base font-semibold leading-snug break-words">{title}</div>
            {(startDate || endDate) && (
              <div className="mt-1 text-xs text-muted-foreground">
                {startDate && <span>{new Date(startDate).toLocaleDateString()}</span>}
                {startDate && endDate && <span> → </span>}
                {endDate && <span>{new Date(endDate).toLocaleDateString()}</span>}
              </div>
            )}
          </div>
          <div className="flex items-center gap-1 text-xs">
            {link && (
              <a
                href={link}
                target="_blank"
                rel="noopener noreferrer"
                className={cn("px-2 py-1 rounded hover:bg-muted transition-colors text-primary")}
              >
                View cycle
              </a>
            )}
            {link && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2"
                onClick={() => handleCopy("link")}
                title="Copy link"
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
            )}
            {!link && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2"
                onClick={() => handleCopy("title")}
                title="Copy title"
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
            )}
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

export default CycleCard;
