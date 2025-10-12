import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

import { BlockNoteView, useBlockNote } from "@blocknote/react";
import "@blocknote/core/style.css";
import SafeMarkdown from "@/components/SafeMarkdown";
import { Wand2 } from "lucide-react";

export type PageCreateInlineProps = {
  title?: string;
  initialEditorJs?: { blocks: any[] };
  onSave?: (values: { title: string; editorJs: { blocks: any[] } }) => void;
  onDiscard?: () => void;
  className?: string;
};

function editorJsBlocksToMarkdown(json?: { blocks: any[] } | null): string {
  try {
    const blocks: any[] = Array.isArray(json?.blocks) ? json!.blocks : [];
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
      if (type === "code") {
        const code: string = String(data.code || "");
        lines.push("```\n" + code + "\n```");
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

function editorJsToBlockNote(editorJs?: { blocks: any[] } | null): any[] {
  try {
    const blocks = Array.isArray(editorJs?.blocks) ? editorJs!.blocks : [];
    const out: any[] = [];
    for (const b of blocks) {
      const type = String(b?.type || "paragraph");
      const data = b?.data || {};
      if (type === "header") {
        const level = Math.min(6, Math.max(1, Number(data.level) || 2));
        out.push({ type: "heading", level, content: String(data.text || "").replace(/<[^>]+>/g, "") });
        continue;
      }
      if (type === "list") {
        const items: string[] = Array.isArray(data.items) ? data.items : [];
        const isOrdered = data.style === "ordered";
        for (const it of items) {
          out.push({ type: isOrdered ? "numberedListItem" : "bulletListItem", content: String(it || "").replace(/<[^>]+>/g, "") });
        }
        continue;
      }
      if (type === "code") {
        out.push({ type: "codeBlock", content: String(data.code || "") });
        continue;
      }
      if (type === "table") {
        // Basic fallback: render table rows as paragraphs for editing
        const content: string[][] = Array.isArray(data.content) ? data.content : [];
        for (const row of content) {
          out.push({ type: "paragraph", content: row.join(" | ") });
        }
        continue;
      }
      out.push({ type: "paragraph", content: String(data.text || "").replace(/<[^>]+>/g, "") });
    }
    return out.length > 0 ? out : [{ type: "paragraph", content: "" }];
  } catch {
    return [{ type: "paragraph", content: "" }];
  }
}

function extractTextFromBNContent(content: any): string {
  if (!content) return "";
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    // Rich text fragments: concatenate .text fields
    return content.map((n: any) => (typeof n?.text === "string" ? n.text : "")).join("");
  }
  if (typeof content === "object" && typeof (content as any).text === "string") return (content as any).text;
  return String(content || "");
}

function blockNoteDocToEditorJs(doc: any[]): { blocks: any[] } {
  const blocks: any[] = [];
  let listAccum: { style: "ordered" | "unordered"; items: string[] } | null = null;

  const flushList = () => {
    if (listAccum && listAccum.items.length > 0) {
      blocks.push({ id: Math.random().toString(36).slice(2), type: "list", data: { style: listAccum.style === "ordered" ? "ordered" : "unordered", items: [...listAccum.items] } });
    }
    listAccum = null;
  };

  for (const node of doc || []) {
    const type = String(node?.type || "paragraph");
    if (type === "heading") {
      flushList();
      const level = Math.min(6, Math.max(1, Number(node?.level) || 2));
      const text = extractTextFromBNContent(node?.content).trim();
      if (text) blocks.push({ id: Math.random().toString(36).slice(2), type: "header", data: { text, level } });
      continue;
    }
    if (type === "bulletListItem" || type === "numberedListItem") {
      const style = type === "numberedListItem" ? "ordered" : "unordered";
      const text = extractTextFromBNContent(node?.content).trim();
      if (!listAccum || listAccum.style !== style) {
        flushList();
        listAccum = { style, items: [] };
      }
      if (text) listAccum.items.push(text);
      continue;
    }
    if (type === "codeBlock") {
      flushList();
      const codeText = extractTextFromBNContent(node?.content);
      if (codeText.trim()) blocks.push({ id: Math.random().toString(36).slice(2), type: "code", data: { code: codeText } });
      continue;
    }
    if (type === "blockquote") {
      flushList();
      const text = extractTextFromBNContent(node?.content).trim();
      if (text) blocks.push({ id: Math.random().toString(36).slice(2), type: "paragraph", data: { text } });
      continue;
    }
    // paragraph / fallback
    flushList();
    const text = extractTextFromBNContent(node?.content).trim();
    if (text) blocks.push({ id: Math.random().toString(36).slice(2), type: "paragraph", data: { text } });
  }
  flushList();
  return { blocks };
}

const Placeholder: React.FC = () => (
  <div className="absolute pointer-events-none text-muted-foreground/70">Write page content…</div>
);

export const PageCreateInline: React.FC<PageCreateInlineProps> = ({ title = "", initialEditorJs, onSave, onDiscard, className }) => {
  const [name, setName] = React.useState<string>(title);
  const [isEditing, setIsEditing] = React.useState<boolean>(true);

  const editor = useBlockNote({
    initialContent: editorJsToBlockNote(initialEditorJs),
  });

  const computeCurrentEditorJs = React.useCallback(() => {
    try {
      const doc = editor.document || [];
      return blockNoteDocToEditorJs(doc);
    } catch {
      return { blocks: [] };
    }
  }, [editor]);

  const handleSave = () => {
    const editorJs = computeCurrentEditorJs();
    onSave?.({ title: name.trim() || "Untitled Page", editorJs });
  };

  const previewMarkdown = React.useMemo(() => editorJsBlocksToMarkdown(computeCurrentEditorJs()), [computeCurrentEditorJs]);

  return (
    <Card className={cn("border-muted/70", className)}>
      <CardContent className="p-0">
        <div className="p-5 border-b">
          <div className="text-xl font-medium text-foreground">Create new page</div>
        </div>

        <div className="px-5 pt-4">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Title"
            className="h-11 text-base"
          />
        </div>

        <div className="px-5 pt-4">
          <div className="relative border rounded-md bg-background overflow-hidden">
            {isEditing ? (
              <>
                <BlockNoteView editor={editor} className="min-h-[220px] max-h-[420px] overflow-auto" />
                <div className="absolute pointer-events-none inset-x-3 top-2">
                  <Placeholder />
                </div>
              </>
            ) : (
              <div className="px-5 py-3">
                <SafeMarkdown content={previewMarkdown} className="prose prose-sm max-w-none dark:prose-invert" />
              </div>
            )}
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="absolute bottom-3 right-3 h-7 gap-1 z-10"
              onClick={() => setIsEditing((v) => !v)}
              title={isEditing ? "Preview" : "Edit"}
            >
              <Wand2 className="h-4 w-4" />
              {isEditing ? "Preview" : "Edit"}
            </Button>
          </div>
        </div>

        <div className="px-5 py-4 border-t flex items-center justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onDiscard}>Discard</Button>
          <Button onClick={handleSave}>Save</Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default PageCreateInline;
