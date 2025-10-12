import React from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Copy } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";
import { cn } from "@/lib/utils";

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
  const [copied, setCopied] = React.useState(false);
  const md = React.useMemo(() => editorJsToMarkdownString(content), [content]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(md || title || "");
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="mt-0.5 text-base font-semibold leading-snug break-words">{title}</div>
          </div>
          <div className="flex items-center gap-1 text-xs">
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
            <Button
              variant="ghost"
              size="sm"
              className={cn("h-7 px-2", copied && "text-green-600 bg-green-600/10")}
              onClick={handleCopy}
              title="Copy content"
            >
              <Copy className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardHeader>
      {md && (
        <CardContent className="pt-0">
          <SafeMarkdown content={md} className="prose prose-sm max-w-none dark:prose-invert" />
        </CardContent>
      )}
    </Card>
  );
};

export default PageCard;
