import React from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Copy, FileText, NotebookPen, FlaskConical, BookOpen } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";
import { cn } from "@/lib/utils";

export type PageCardProps = {
  title: string;
  content: string; // stringified Editor.js JSON
  link?: string;
  className?: string;
  // Optional explicit page type; if not provided we'll infer from content
  type?: string; // e.g., "doc" | "note" | "spec" | "guide"
};

function editorJsToMarkdownString(jsonStr?: string): string {
  try {
    const parsed = jsonStr ? JSON.parse(jsonStr) : { blocks: [] };
    const blocks: any[] = Array.isArray(parsed?.blocks) ? parsed.blocks : [];
    const lines: string[] = [];
    for (const b of blocks) {
      const type = b?.type;
      const data = b?.data || {};
      if (type === "header") {
        const level = Math.min(6, Number(data.level) || 2);
        lines.push(`${"#".repeat(level)} ${String(data.text || "").replace(/<[^>]+>/g, "")}`);
        continue;
      }
      if (type === "list") {
        const style = data.style === "ordered" ? "ol" : "ul";
        const items: string[] = Array.isArray(data.items) ? data.items : [];
        for (let i = 0; i < items.length; i++) {
          const prefix = style === "ol" ? `${i + 1}. ` : "- ";
          lines.push(prefix + String(items[i] || "").replace(/<[^>]+>/g, ""));
        }
        continue;
      }
      if (type === "table") {
        const content: string[][] = Array.isArray(data.content) ? data.content : [];
        for (const row of content) {
          lines.push(`| ${row.map((c) => String(c || "").replace(/<[^>]+>/g, "")).join(" | ")} |`);
        }
        continue;
      }
      // paragraph or fallback
      const text = String(data.text || "").replace(/<[^>]+>/g, "");
      if (text) lines.push(text);
    }
    return lines.join("\n\n").trim();
  } catch {
    return "";
  }
}

export const PageCard: React.FC<PageCardProps> = ({ title, content, link, className }) => {
  const [copied, setCopied] = React.useState(false);
  const md = React.useMemo(() => editorJsToMarkdownString(content), [content]);

  // Lightweight heuristic to infer page type based on title/content
  const inferredType = React.useMemo(() => {
    const source = `${title}\n${md}`.toLowerCase();
    if (/\b(rfc|spec|specification|design doc|adr)\b/.test(source)) return "spec";
    if (/\b(meeting|notes?|minutes)\b/.test(source)) return "note";
    if (/\b(guide|how[-\s]?to|tutorial|walkthrough)\b/.test(source)) return "guide";
    if (/\b(doc|documentation|overview|readme)\b/.test(source)) return "doc";
    return "doc"; // sensible default
  }, [title, md]);

  const pageType = inferredType as "doc" | "note" | "spec" | "guide";

  const typeIcon = {
    doc: FileText,
    note: NotebookPen,
    spec: FlaskConical,
    guide: BookOpen,
  }[pageType];

  const typeBadgeVariant = {
    doc: "accent",
    note: "secondary",
    spec: "default",
    guide: "outline",
  } as const;

  const containerAccent = {
    doc: "ring-1 ring-accent/20",
    note: "ring-1 ring-secondary/20",
    spec: "ring-1 ring-primary/20",
    guide: "ring-1 ring-muted/30",
  }[pageType];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(md || title || "");
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <Card className={cn("relative overflow-hidden rounded-xl border bg-card text-card-foreground shadow-sm", containerAccent, className)}>
      {/* subtle left accent bar for quick visual cue */}
      <div className="absolute left-0 top-0 h-full w-1 bg-primary/20" aria-hidden />
      <CardHeader className="px-6 py-5 border-b">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              {typeIcon ? (
                <span className="shrink-0 text-muted-foreground">
                  {React.createElement(typeIcon, { className: "h-4.5 w-4.5" as any })}
                </span>
              ) : null}
              <Badge variant={typeBadgeVariant[pageType]} className="shrink-0">
                {pageType}
              </Badge>
            </div>
            <div className="mt-2 text-lg md:text-xl font-semibold leading-tight break-words">
              {title}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {link && (
              <Button asChild variant="outline" size="sm" className="h-8">
                <a href={link} target="_blank" rel="noopener noreferrer">View</a>
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className={cn("h-8 px-2", copied && "text-green-600 bg-green-600/10")}
              onClick={handleCopy}
              title="Copy content"
            >
              <Copy className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      {md && (
        <CardContent className="px-6 py-5">
          <SafeMarkdown
            content={md}
            className="prose prose-base md:prose-lg max-w-none dark:prose-invert leading-relaxed"
          />
        </CardContent>
      )}
    </Card>
  );
};

export default PageCard;

