import { useEffect, useRef } from "react";

// Lazy import EditorJS and tools to avoid SSR issues
export interface EditorJsViewerProps {
  blocks: unknown[];
}

export function EditorJsViewer({ blocks }: EditorJsViewerProps) {
  const holderRef = useRef<HTMLDivElement | null>(null);
  const editorRef = useRef<any>(null);

  useEffect(() => {
    let isMounted = true;
    async function init() {
      if (!holderRef.current) return;
      const EditorJS = (await import("@editorjs/editorjs")).default;
      const Header = (await import("@editorjs/header")).default;
      const List = (await import("@editorjs/list")).default;
      const Table = (await import("@editorjs/table")).default;
      const Paragraph = (await import("@editorjs/paragraph")).default;

      if (!isMounted) return;
      if (editorRef.current) {
        try { await editorRef.current.destroy?.(); } catch {}
        editorRef.current = null;
      }

      editorRef.current = new EditorJS({
        holder: holderRef.current!,
        readOnly: true,
        tools: {
          header: Header,
          list: List,
          table: Table,
          paragraph: Paragraph,
        },
        data: {
          blocks: Array.isArray(blocks) ? (blocks as any) : [],
        },
      });
    }
    init();
    return () => {
      isMounted = false;
      const ed = editorRef.current;
      if (ed && ed.destroy) {
        try { ed.destroy(); } catch {}
      }
      editorRef.current = null;
    };
  }, [blocks]);

  return (
    <div className="prose max-w-none">
      <div ref={holderRef} />
    </div>
  );
}
