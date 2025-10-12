import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

import { LexicalComposer } from "@lexical/react/LexicalComposer";
import { RichTextPlugin } from "@lexical/react/LexicalRichTextPlugin";
import LexicalErrorBoundary from "@lexical/react/LexicalErrorBoundary";
import { HistoryPlugin } from "@lexical/react/LexicalHistoryPlugin";
import { OnChangePlugin } from "@lexical/react/LexicalOnChangePlugin";
import { ContentEditable } from "@lexical/react/LexicalContentEditable";
import { $getRoot, type EditorState } from "lexical";

import { ListPlugin } from "@lexical/react/LexicalListPlugin";
import { LinkPlugin } from "@lexical/react/LexicalLinkPlugin";
import { MarkdownShortcutPlugin } from "@lexical/react/LexicalMarkdownShortcutPlugin";
import { $convertFromMarkdownString, $convertToMarkdownString } from "@lexical/markdown";

import { ListItemNode, ListNode } from "@lexical/list";
import { CodeNode } from "@lexical/code";
import { LinkNode } from "@lexical/link";
import { HeadingNode, QuoteNode } from "@lexical/rich-text";

import { MARKDOWN_TRANSFORMERS } from "@/lexical/markdown";

export type PageCreateInlineProps = {
  title?: string;
  initialEditorJs?: { blocks: any[] };
  onSave?: (values: { title: string; editorJs: { blocks: any[] } }) => void;
  onDiscard?: () => void;
  className?: string;
};

function editorJsToPlainText(editorJs?: { blocks: any[] }): string {
  try {
    const blocks = editorJs?.blocks || [];
    const lines = blocks.map((b: any) => {
      const type = b?.type;
      const data = b?.data || {};
      if (type === "header") {
        return `${"#".repeat(Math.min(6, Number(data.level) || 2))} ${String(data.text || "").replace(/<[^>]+>/g, "")}`;
      }
      if (type === "list") {
        const style = data.style === "ordered" ? "ol" : "ul";
        const items: string[] = Array.isArray(data.items) ? data.items : [];
        return items.map((it, idx) => (style === "ol" ? `${idx + 1}. ` : "- ") + String(it || "").replace(/<[^>]+>/g, "")).join("\n");
      }
      if (type === "table") {
        const content: string[][] = Array.isArray(data.content) ? data.content : [];
        return content.map((row) => `| ${row.map((c) => String(c || "").replace(/<[^>]+>/g, "")).join(" | ")} |`).join("\n");
      }
      // paragraph or unknown
      return String(data.text || "").replace(/<[^>]+>/g, "");
    });
    return lines.join("\n\n").trim();
  } catch {
    return "";
  }
}

function plainTextToEditorJs(text: string): { blocks: any[] } {
  // Backwards-compatible fallback: treat double-newline as paragraph break
  const paras = String(text || "").split(/\n{2,}/g).map((s) => s.trim()).filter(Boolean);
  return {
    blocks: paras.map((p) => ({ id: Math.random().toString(36).slice(2), type: "paragraph", data: { text: p } })),
  };
}

function markdownToEditorJs(text: string): { blocks: any[] } {
  const blocks: any[] = [];
  const lines = String(text || "").replace(/\r\n?/g, "\n").split("\n");

  let i = 0;
  const genId = () => Math.random().toString(36).slice(2);

  const isTableRow = (s: string) => /^\s*\|.*\|\s*$/.test(s);
  const isTableSep = (s: string) => /^\s*\|?\s*:?[-]+:?(\s*\|\s*:?[-]+:?)+\s*\|?\s*$/.test(s);
  const olRegex = /^\s*(\d+)\.\s+(.+)$/;
  const ulRegex = /^\s*[-*+]\s+(.+)$/;

  while (i < lines.length) {
    let line = lines[i];
    if (!line || !line.trim()) { i++; continue; }

    // fenced code block ```
    if (/^\s*```/.test(line)) {
      i++; // skip opening fence
      const code: string[] = [];
      while (i < lines.length && !/^\s*```/.test(lines[i])) {
        code.push(lines[i]);
        i++;
      }
      if (i < lines.length) i++; // skip closing fence
      blocks.push({ id: genId(), type: "paragraph", data: { text: code.join("\n") } });
      continue;
    }

    // heading
    const hm = line.match(/^(#{1,6})\s+(.+)$/);
    if (hm) {
      const level = Math.min(6, hm[1].length);
      blocks.push({ id: genId(), type: "header", data: { level, text: hm[2].trim() } });
      i++;
      continue;
    }

    // table
    if (isTableRow(line)) {
      const rows: string[][] = [];
      // header row
      rows.push(line.split("|").slice(1, -1).map((c) => c.trim()));
      i++;
      // optional separator row
      if (i < lines.length && isTableSep(lines[i])) i++;
      // body rows
      while (i < lines.length && isTableRow(lines[i])) {
        rows.push(lines[i].split("|").slice(1, -1).map((c) => c.trim()));
        i++;
      }
      blocks.push({ id: genId(), type: "table", data: { content: rows } });
      continue;
    }

    // ordered list
    if (olRegex.test(line)) {
      const items: string[] = [];
      while (i < lines.length && olRegex.test(lines[i])) {
        const m = lines[i].match(olRegex)!;
        items.push(String(m[2]).trim());
        i++;
      }
      blocks.push({ id: genId(), type: "list", data: { style: "ordered", items } });
      continue;
    }

    // unordered list
    if (ulRegex.test(line)) {
      const items: string[] = [];
      while (i < lines.length && ulRegex.test(lines[i])) {
        const m = lines[i].match(ulRegex)!;
        items.push(String(m[1]).trim());
        i++;
      }
      blocks.push({ id: genId(), type: "list", data: { style: "unordered", items } });
      continue;
    }

    // blockquote -> paragraph content
    if (/^\s*>\s?/.test(line)) {
      const parts: string[] = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        parts.push(lines[i].replace(/^\s*>\s?/, "").trim());
        i++;
      }
      const textContent = parts.join(" ").trim();
      if (textContent) blocks.push({ id: genId(), type: "paragraph", data: { text: textContent } });
      continue;
    }

    // paragraph (collect until blank or a new block starter)
    const para: string[] = [line.trim()];
    i++;
    while (
      i < lines.length &&
      lines[i] && lines[i].trim() &&
      !/^(#{1,6})\s+/.test(lines[i]) &&
      !/^\s*```/.test(lines[i]) &&
      !isTableRow(lines[i]) &&
      !olRegex.test(lines[i]) &&
      !ulRegex.test(lines[i]) &&
      !/^\s*>\s?/.test(lines[i])
    ) {
      para.push(lines[i].trim());
      i++;
    }
    const textContent = para.join(" ").trim();
    if (textContent) blocks.push({ id: genId(), type: "paragraph", data: { text: textContent } });
  }

  return { blocks };
}

const Placeholder: React.FC = () => (
  <div className="absolute pointer-events-none text-muted-foreground/70">Write page content…</div>
);

export const PageCreateInline: React.FC<PageCreateInlineProps> = ({ title = "", initialEditorJs, onSave, onDiscard, className }) => {
  const [name, setName] = React.useState<string>(title);
  const latestTextRef = React.useRef<string>(editorJsToPlainText(initialEditorJs));

  const initialConfig = React.useMemo(() => ({
    namespace: "page-editor",
    onError: (e: Error) => console.error(e),
    theme: {},
    editorState: (editor: any) => {
      const initialText = editorJsToPlainText(initialEditorJs);
      editor.update(() => {
        const root = $getRoot();
        root.clear();
        $convertFromMarkdownString(initialText, MARKDOWN_TRANSFORMERS);
      });
    },
    nodes: [HeadingNode, QuoteNode, ListNode, ListItemNode, CodeNode, LinkNode],
  }), [initialEditorJs]);

  const handleChange = (state: EditorState) => {
    try {
      state.read(() => {
        const md = $convertToMarkdownString(MARKDOWN_TRANSFORMERS);
        latestTextRef.current = md;
      });
    } catch {}
  };

  const handleSave = () => {
    const md = latestTextRef.current || "";
    const editorJs = markdownToEditorJs(md);
    onSave?.({ title: name.trim() || "Untitled Page", editorJs });
  };

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
          <div className="relative">
            <LexicalComposer initialConfig={initialConfig}>
              <div className="border rounded-md bg-background">
                <RichTextPlugin contentEditable={<ContentEditable className="min-h-[220px] max-h-[420px] overflow-auto px-3 py-2 outline-none" />} placeholder={<Placeholder />} ErrorBoundary={LexicalErrorBoundary} />
                <HistoryPlugin />
                <OnChangePlugin onChange={handleChange} />
                <ListPlugin />
                <LinkPlugin />
                <MarkdownShortcutPlugin transformers={MARKDOWN_TRANSFORMERS} />
              </div>
            </LexicalComposer>
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

