import { useEffect, useRef, useState } from "react";

type EditorJsData = {
  blocks: Array<Record<string, unknown>>;
};

interface EditorJsViewerProps {
  blocks: EditorJsData["blocks"];
  minHeight?: number;
}

// Lightweight read-only viewer for Editor.js data
export function EditorJsViewer({ blocks, minHeight = 200 }: EditorJsViewerProps) {
  const holderRef = useRef<HTMLDivElement | null>(null);
  const editorRef = useRef<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function init() {
      try {
        const EditorJS = (await import("@editorjs/editorjs")).default as any;
        if (!isMounted) return;
        editorRef.current = new EditorJS({
          holder: holderRef.current!,
          readOnly: true,
          data: { blocks: Array.isArray(blocks) ? blocks : [] },
          minHeight,
        });
      } catch (e: any) {
        setError(e?.message || "Failed to load Editor.js");
      }
    }
    init();
    return () => {
      isMounted = false;
      try {
        if (editorRef.current && editorRef.current.destroy) {
          editorRef.current.destroy();
        }
      } catch {
        // ignore
      }
    };
  }, [blocks, minHeight]);

  if (error) {
    return (
      <div className="text-sm text-destructive">
        Failed to load Editor.js viewer: {error}
      </div>
    );
  }

  return <div ref={holderRef} className="border rounded-md p-3 bg-card" />;
}
