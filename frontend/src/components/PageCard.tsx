import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Copy, ChevronDown, ChevronRight } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";
import { cn } from "@/lib/utils";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

export type PageCardProps = {
  title: string;
  content: string; // stringified Editor.js JSON
  link?: string;
  className?: string;
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
  const [copied, setCopied] = React.useState<null | "title" | "content" | "link">(null);
  const [open, setOpen] = React.useState<boolean>(false);
  const md = React.useMemo(() => editorJsToMarkdownString(content), [content]);

  const PREVIEW_LINES = 8;
  const { previewMd, hasMore } = React.useMemo(() => {
    if (!md) return { previewMd: "", hasMore: false };
    const lines = md.split(/\r?\n/);
    if (lines.length <= PREVIEW_LINES) return { previewMd: md, hasMore: false };
    const shortened = lines.slice(0, PREVIEW_LINES).join("\n").trim() + "\n\n…";
    return { previewMd: shortened, hasMore: true };
  }, [md]);

  const handleCopy = async (field: "title" | "content" | "link") => {
    try {
      const text = field === "title" ? title : field === "content" ? md : link || "";
      if (!text) return;
      await navigator.clipboard.writeText(text);
      setCopied(field);
      window.setTimeout(() => setCopied(null), 2000);
    } catch {}
  };

  return (
    <Card className={className}>
      <Collapsible open={open} onOpenChange={setOpen}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <CardTitle className="mt-0.5 text-base font-semibold leading-snug break-words">{title}</CardTitle>
            </div>
            <div className="flex items-center gap-1 text-xs">
              {hasMore && (
                <CollapsibleTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2"
                    title={open ? "Collapse" : "Preview"}
                  >
                    {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                    <span className="ml-1">{open ? "Collapse" : "Preview"}</span>
                  </Button>
                </CollapsibleTrigger>
              )}
              {link && (
                <a
                  href={link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn("px-2 py-1 rounded hover:bg-muted transition-colors text-primary")}
                >
                  View page
                </a>
              )}
              {link && (
                <Button
                  variant="ghost"
                  size="sm"
                  className={cn("h-7 px-2", copied === "link" && "text-green-600 bg-green-600/10")}
                  onClick={() => handleCopy("link")}
                  title="Copy link"
                >
                  <Copy className="h-3.5 w-3.5" />
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                className={cn("h-7 px-2", copied === "title" && "text-green-600 bg-green-600/10")}
                onClick={() => handleCopy("title")}
                title="Copy title"
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className={cn("h-7 px-2", copied === "content" && "text-green-600 bg-green-600/10")}
                onClick={() => handleCopy("content")}
                title="Copy content"
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </CardHeader>

        {/* Preview content when collapsed */}
        {!open && previewMd && (
          <CardContent className="pt-0">
            <SafeMarkdown content={previewMd} className="prose prose-sm max-w-none dark:prose-invert" />
          </CardContent>
        )}

        {/* Full content with animation when expanded */}
        {md && (
          <CollapsibleContent className="overflow-hidden data-[state=open]:animate-collapsible-down data-[state=closed]:animate-collapsible-up data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-top-1 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:slide-out-to-top-1">
            <CardContent className="pt-0">
              <SafeMarkdown content={md} className="prose prose-sm max-w-none dark:prose-invert" />
            </CardContent>
          </CollapsibleContent>
        )}
      </Collapsible>
    </Card>
  );
};

export default PageCard;

