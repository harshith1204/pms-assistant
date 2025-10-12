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
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";
import { ListPlugin } from "@lexical/react/LexicalListPlugin";
import { LinkPlugin } from "@lexical/react/LexicalLinkPlugin";
import { MarkdownShortcutPlugin } from "@lexical/react/LexicalMarkdownShortcutPlugin";
import { $createParagraphNode, $createTextNode, $getRoot, $getSelection, $isRangeSelection, $setBlocksType, type EditorState, UNDO_COMMAND, REDO_COMMAND, FORMAT_TEXT_COMMAND } from "lexical";
import { HeadingNode, QuoteNode, $createHeadingNode, $isHeadingNode } from "@lexical/rich-text";
import { ListNode, ListItemNode, $createListNode, INSERT_ORDERED_LIST_COMMAND, INSERT_UNORDERED_LIST_COMMAND, REMOVE_LIST_COMMAND } from "@lexical/list";
import { LinkNode, AutoLinkNode, TOGGLE_LINK_COMMAND } from "@lexical/link";
import { CodeNode, $createCodeNode } from "@lexical/code";
import { Wand2 } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";

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
  const paras = String(text || "").split(/\n{2,}/g).map((s) => s.trim()).filter(Boolean);
  return {
    blocks: paras.map((p) => ({ id: Math.random().toString(36).slice(2), type: "paragraph", data: { text: p } })),
  };
}

const Placeholder: React.FC = () => (
  <div className="absolute pointer-events-none text-muted-foreground/70">Write page content…</div>
);

export const PageCreateInline: React.FC<PageCreateInlineProps> = ({ title = "", initialEditorJs, onSave, onDiscard, className }) => {
  const [name, setName] = React.useState<string>(title);
  const latestEditorStateRef = React.useRef<EditorState | null>(null);
  const editorRef = React.useRef<any>(null);
  const [isEditing, setIsEditing] = React.useState<boolean>(true);

  const EditorRefPlugin: React.FC<{ onReady: (editor: any) => void }> = ({ onReady }) => {
    const [editor] = useLexicalComposerContext();
    React.useEffect(() => {
      onReady(editor);
    }, [editor, onReady]);
    return null;
  };

  const initialConfig = React.useMemo(() => ({
    namespace: "page-editor",
    onError: (e: Error) => console.error(e),
    theme: {},
    editorState: (editor: any) => {
      const blocks = Array.isArray(initialEditorJs?.blocks) ? initialEditorJs!.blocks : [];
      editor.update(() => {
        const root = $getRoot();
        root.clear();
        if (!blocks || blocks.length === 0) {
          const p = $createParagraphNode();
          p.append($createTextNode(""));
          root.append(p);
          return;
        }
        for (const b of blocks) {
          const type = String(b?.type || "paragraph");
          const data = b?.data || {};
          if (type === "header") {
            const level = Math.min(6, Math.max(1, Number(data.level) || 2));
            const tag = ("h" + String(level)) as any;
            const h = $createHeadingNode(tag);
            h.append($createTextNode(String(data.text || "").replace(/<[^>]+>/g, "")));
            root.append(h);
            continue;
          }
          if (type === "list") {
            const style = data.style === "ordered" ? "number" : "bullet";
            const list = $createListNode(style as any);
            const items: string[] = Array.isArray(data.items) ? data.items : [];
            for (const it of items) {
              const li = new ListItemNode();
              li.append($createTextNode(String(it || "").replace(/<[^>]+>/g, "")));
              list.append(li);
            }
            root.append(list);
            continue;
          }
          if (type === "code") {
            const code = $createCodeNode();
            code.append($createTextNode(String(data.code || "")));
            root.append(code);
            continue;
          }
          // paragraph or fallback
          const p = $createParagraphNode();
          const text = String(data.text || "").replace(/<[^>]+>/g, "");
          p.append($createTextNode(text));
          root.append(p);
        }
      });
    },
    // Register nodes to enable rich-text features
    nodes: [HeadingNode, QuoteNode, ListNode, ListItemNode, LinkNode, AutoLinkNode, CodeNode],
  }), [initialEditorJs]);

  const handleChange = (state: EditorState) => {
    latestEditorStateRef.current = state;
  };

  const handleSave = () => {
    const computeBlocks = (): { blocks: any[] } => {
      const currentState = latestEditorStateRef.current || editorRef.current?.getEditorState();
      if (!currentState) return { blocks: [] };
      const blocks: any[] = [];
      try {
        currentState.read(() => {
          const root = $getRoot();
          const children = root.getChildren();
          for (const node of children) {
            // Headings
            if ($isHeadingNode(node)) {
              const tag = (node as any).getTag?.() || "h2";
              const level = Number(String(tag).replace("h", "")) || 2;
              const text = node.getTextContent().trim();
              if (text) {
                blocks.push({ id: Math.random().toString(36).slice(2), type: "header", data: { text, level } });
              }
              continue;
            }
            // Lists
            if (node instanceof ListNode) {
              const listType = node.getListType();
              const style = listType === "number" ? "ordered" : "unordered";
              const items: string[] = [];
              for (const li of node.getChildren()) {
                if (li instanceof ListItemNode) {
                  const t = li.getTextContent().trim();
                  if (t) items.push(t);
                }
              }
              if (items.length > 0) {
                blocks.push({ id: Math.random().toString(36).slice(2), type: "list", data: { style, items } });
              }
              continue;
            }
            // Code blocks
            if (node instanceof CodeNode) {
              const codeText = node.getTextContent();
              if (codeText.trim()) {
                blocks.push({ id: Math.random().toString(36).slice(2), type: "code", data: { code: codeText } });
              }
              continue;
            }
            // Quote → store as paragraph for compatibility
            if (node instanceof QuoteNode) {
              const text = node.getTextContent().trim();
              if (text) {
                blocks.push({ id: Math.random().toString(36).slice(2), type: "paragraph", data: { text: text } });
              }
              continue;
            }
            // Paragraph or fallback
            const type = (node as any).getType?.() || "paragraph";
            if (type === "paragraph") {
              const text = node.getTextContent().trim();
              if (text) {
                blocks.push({ id: Math.random().toString(36).slice(2), type: "paragraph", data: { text } });
              }
              continue;
            }
            // Fallback: treat unknown nodes as paragraph text
            const text = node.getTextContent().trim();
            if (text) {
              blocks.push({ id: Math.random().toString(36).slice(2), type: "paragraph", data: { text } });
            }
          }
        });
      } catch {}
      return { blocks };
    };
    const editorJs = computeBlocks();
    onSave?.({ title: name.trim() || "Untitled Page", editorJs });
  };

  const computeCurrentEditorJs = React.useCallback(() => {
    const currentState = latestEditorStateRef.current || editorRef.current?.getEditorState();
    if (!currentState) return { blocks: [] };
    const blocks: any[] = [];
    try {
      currentState.read(() => {
        const root = $getRoot();
        const children = root.getChildren();
        for (const node of children) {
          if ($isHeadingNode(node)) {
            const tag = (node as any).getTag?.() || "h2";
            const level = Number(String(tag).replace("h", "")) || 2;
            const text = node.getTextContent().trim();
            if (text) blocks.push({ id: Math.random().toString(36).slice(2), type: "header", data: { text, level } });
            continue;
          }
          if (node instanceof ListNode) {
            const listType = node.getListType();
            const style = listType === "number" ? "ordered" : "unordered";
            const items: string[] = [];
            for (const li of node.getChildren()) {
              if (li instanceof ListItemNode) {
                const t = li.getTextContent().trim();
                if (t) items.push(t);
              }
            }
            if (items.length > 0) blocks.push({ id: Math.random().toString(36).slice(2), type: "list", data: { style, items } });
            continue;
          }
          if (node instanceof CodeNode) {
            const codeText = node.getTextContent();
            if (codeText.trim()) blocks.push({ id: Math.random().toString(36).slice(2), type: "code", data: { code: codeText } });
            continue;
          }
          if (node instanceof QuoteNode) {
            const text = node.getTextContent().trim();
            if (text) blocks.push({ id: Math.random().toString(36).slice(2), type: "paragraph", data: { text } });
            continue;
          }
          const type = (node as any).getType?.() || "paragraph";
          if (type === "paragraph") {
            const text = node.getTextContent().trim();
            if (text) blocks.push({ id: Math.random().toString(36).slice(2), type: "paragraph", data: { text } });
            continue;
          }
          const text = node.getTextContent().trim();
          if (text) blocks.push({ id: Math.random().toString(36).slice(2), type: "paragraph", data: { text } });
        }
      });
    } catch {}
    return { blocks };
  }, []);

  function editorJsBlocksToMarkdown(blocks?: any[]): string {
    try {
      const b = Array.isArray(blocks) ? blocks : [];
      const lines: string[] = [];
      for (const blk of b) {
        const type = blk?.type;
        const data = blk?.data || {};
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
        const text = String(data.text || "").replace(/<[^>]+>/g, "");
        if (text) lines.push(text);
      }
      return lines.join("\n\n").trim();
    } catch {
      return "";
    }
  }

  const Toolbar: React.FC = () => {
    const [editor] = useLexicalComposerContext();
    const applyHeading = (level: 1 | 2 | 3) => {
      editor.update(() => {
        const selection = $getSelection();
        if ($isRangeSelection(selection)) {
          $setBlocksType(selection, () => $createHeadingNode(("h" + level) as any));
        }
      });
    };
    const applyQuote = () => {
      editor.update(() => {
        const selection = $getSelection();
        if ($isRangeSelection(selection)) {
          $setBlocksType(selection, () => new QuoteNode());
        }
      });
    };
    return (
      <div className="flex flex-wrap items-center gap-1 border-b px-2 py-1 bg-muted/20">
        <Button type="button" variant="ghost" size="sm" onClick={() => editor.dispatchCommand(UNDO_COMMAND, undefined)}>Undo</Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => editor.dispatchCommand(REDO_COMMAND, undefined)}>Redo</Button>
        <div className="w-px h-5 bg-border mx-1" />
        <Button type="button" variant="ghost" size="sm" onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, "bold")}>B</Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, "italic")}>I</Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, "underline")}>U</Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, "strikethrough")}>S</Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, "code")}>{"</>"}</Button>
        <div className="w-px h-5 bg-border mx-1" />
        <Button type="button" variant="ghost" size="sm" onClick={() => applyHeading(1)}>H1</Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => applyHeading(2)}>H2</Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => applyHeading(3)}>H3</Button>
        <Button type="button" variant="ghost" size="sm" onClick={applyQuote}>Quote</Button>
        <div className="w-px h-5 bg-border mx-1" />
        <Button type="button" variant="ghost" size="sm" onClick={() => editor.dispatchCommand(INSERT_UNORDERED_LIST_COMMAND, undefined)}>Bulleted</Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => editor.dispatchCommand(INSERT_ORDERED_LIST_COMMAND, undefined)}>Numbered</Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => editor.dispatchCommand(REMOVE_LIST_COMMAND, undefined)}>Clear List</Button>
        <div className="w-px h-5 bg-border mx-1" />
        <Button type="button" variant="ghost" size="sm" onClick={() => editor.dispatchCommand(TOGGLE_LINK_COMMAND, "https://")}>Link</Button>
      </div>
    );
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
              <div className="border rounded-md bg-background overflow-hidden relative">
                {isEditing && <Toolbar />}
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
                {isEditing ? (
                  <>
                    <RichTextPlugin contentEditable={<ContentEditable className="min-h-[220px] max-h-[420px] overflow-auto px-3 py-2 outline-none" />} placeholder={<Placeholder />} ErrorBoundary={LexicalErrorBoundary} />
                    <HistoryPlugin />
                    <ListPlugin />
                    <LinkPlugin />
                    <MarkdownShortcutPlugin />
                    <OnChangePlugin onChange={handleChange} />
                    <EditorRefPlugin onReady={(ed) => { editorRef.current = ed; }} />
                  </>
                ) : (
                  <div className="px-5 py-3">
                    <SafeMarkdown content={editorJsBlocksToMarkdown(computeCurrentEditorJs().blocks)} className="prose prose-sm max-w-none dark:prose-invert" />
                  </div>
                )}
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

