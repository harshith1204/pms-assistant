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
import { $createParagraphNode, $createTextNode, $getRoot, type EditorState } from "lexical";

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
        const paragraph = $createParagraphNode();
        paragraph.append($createTextNode(initialText));
        root.append(paragraph);
      });
    },
    nodes: [],
  }), [initialEditorJs]);

  const handleChange = (state: EditorState) => {
    try {
      state.read(() => {
        const text = $getRoot().getTextContent();
        latestTextRef.current = text;
      });
    } catch {}
  };

  const handleSave = () => {
    const editorJs = plainTextToEditorJs(latestTextRef.current || "");
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

