import React, { useEffect, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import EditorJS from '@editorjs/editorjs';
import Header from '@editorjs/header';
import List from '@editorjs/list';
import Paragraph from '@editorjs/paragraph';
import Table from '@editorjs/table';
import Quote from '@editorjs/quote';
import Code from '@editorjs/code';
import InlineCode from '@editorjs/inline-code';
import LinkTool from '@editorjs/link';
import Marker from '@editorjs/marker';
import Delimiter from '@editorjs/delimiter';
import Embed from '@editorjs/embed';
import ImageTool from '@editorjs/image';

export type PageCreateInlineProps = {
  initialEditorJs?: { blocks: Block[] };
  onSave?: (values: { title: string; editorJs: { blocks: Block[] } }) => void;
  onDiscard?: () => void;
  className?: string;
};

interface Block {
  id?: string;
  type: string;
  data: Record<string, unknown>;
}

// Editor.js data format is already compatible, no conversion needed

const Placeholder: React.FC = () => (
  <div className="absolute pointer-events-none text-muted-foreground/70">Write page content…</div>
);

export const PageCreateInline: React.FC<PageCreateInlineProps> = ({ initialEditorJs, onSave, onDiscard, className }) => {
  const editorRef = useRef<EditorJS | null>(null);
  const editorContainerRef = useRef<HTMLDivElement>(null);
  const [isPreview, setIsPreview] = useState<boolean>(false);
  const [editorData, setEditorData] = useState<{ blocks: Block[] }>(initialEditorJs || {
    blocks: [
      {
        id: 'test-block',
        type: 'paragraph',
        data: {
          text: 'This is a test paragraph to verify the editor is working. If you can see and edit this text, the editor is functioning correctly.'
        }
      }
    ]
  });
  const [editorReady, setEditorReady] = useState<boolean>(false);

  // Debug logging
  console.log('PageCreateInline props:', { initialEditorJs });
  console.log('Editor data state:', editorData);

  useEffect(() => {
    console.log('Initializing Editor.js with data:', initialEditorJs);

    if (editorContainerRef.current && !editorRef.current) {
      try {
        editorRef.current = new EditorJS({
          holder: editorContainerRef.current,
          data: editorData,
          readOnly: isPreview,
          tools: {
            header: {
              class: Header,
              inlineToolbar: true,
              config: {
                levels: [1, 2, 3, 4, 5, 6],
                defaultLevel: 2
              }
            },
            paragraph: {
              class: Paragraph,
              inlineToolbar: true,
            },
            list: {
              class: List,
              inlineToolbar: true,
            },
            quote: {
              class: Quote,
              inlineToolbar: true,
            },
            code: {
              class: Code,
              inlineToolbar: true,
            },
            inlineCode: {
              class: InlineCode,
              shortcut: 'CMD+SHIFT+M',
            },
            linkTool: {
              class: LinkTool,
              config: {
                endpoint: '/api/fetchUrl',
              }
            },
            marker: {
              class: Marker,
            },
            delimiter: {
              class: Delimiter,
            },
            embed: {
              class: Embed,
              config: {
                services: {
                  youtube: true,
                  coub: true,
                  codepen: true,
                  imgur: true,
                }
              }
            },
            table: Table,
            image: {
              class: ImageTool,
              config: {
                endpoints: {
                  byFile: '/api/uploadFile',
                  byUrl: '/api/fetchUrl',
                }
              }
            },
          },
          placeholder: "Write page content…",
          minHeight: 220,
          autofocus: true,
        });

        editorRef.current.isReady
          .then(() => {
            console.log('Editor.js is ready to work!');
            setEditorReady(true);
            // Update local state after editor is ready
            setEditorData(initialEditorJs || { blocks: [] });

            // Auto-focus the editor
            if (editorRef.current && editorRef.current.focus) {
              try {
                editorRef.current.focus();
              } catch (error) {
                console.log('Focus method not available');
              }
            }
          })
          .catch((reason) => {
            console.error(`Editor.js initialization failed:`, reason);
          });
      } catch (error) {
        console.error('Failed to create Editor.js instance:', error);
      }
    }

    return () => {
      if (editorRef.current && editorRef.current.destroy) {
        editorRef.current.destroy();
        editorRef.current = null;
      }
    };
  }, []); // Only run once on mount

  // Toggle read-only mode based on isPreview (EditorJS built-in preview)
  useEffect(() => {
    // Persist current content, then rebuild the editor with correct readOnly state.
    let cancelled = false;
    (async () => {
      const holder = editorContainerRef.current;
      if (!holder) return;

      // Save current data if possible
      let nextData = editorData;
      if (editorRef.current?.save) {
        try {
          const output = await editorRef.current.save();
          if (!cancelled) {
            nextData = output as any;
            setEditorData(output as any);
          }
        } catch (e) {
          // fall back to existing state
        }
      }

      // Destroy existing instance
      try {
        editorRef.current?.destroy?.();
      } catch {}
      editorRef.current = null;
      setEditorReady(false);

      // Recreate with updated readOnly
      try {
        const instance = new EditorJS({
          holder,
          data: nextData,
          readOnly: isPreview,
          tools: {
            header: {
              class: Header,
              inlineToolbar: true,
              config: { levels: [1, 2, 3, 4, 5, 6], defaultLevel: 2 },
            },
            paragraph: { class: Paragraph, inlineToolbar: true },
            list: { class: List, inlineToolbar: true },
            quote: { class: Quote, inlineToolbar: true },
            code: { class: Code, inlineToolbar: true },
            inlineCode: { class: InlineCode, shortcut: 'CMD+SHIFT+M' },
            linkTool: { class: LinkTool, config: { endpoint: '/api/fetchUrl' } },
            marker: { class: Marker },
            delimiter: { class: Delimiter },
            embed: { class: Embed, config: { services: { youtube: true, coub: true, codepen: true, imgur: true } } },
            table: Table,
            image: { class: ImageTool, config: { endpoints: { byFile: '/api/uploadFile', byUrl: '/api/fetchUrl' } } },
          },
          placeholder: 'Write page content…',
          minHeight: 400,
          autofocus: !isPreview,
        });
        editorRef.current = instance;
        instance.isReady
          .then(() => {
            if (cancelled) return;
            setEditorReady(true);
            if (!isPreview) {
              try { editorRef.current?.focus?.(); } catch {}
            }
          })
          .catch((err) => console.error('Editor.js (re)initialization failed:', err));
      } catch (err) {
        console.error('Failed to rebuild Editor.js instance:', err);
      }
    })();

    return () => { cancelled = true; };
  }, [isPreview]);

  // Effect to handle initialEditorJs changes - recreate editor if data changes significantly
  useEffect(() => {
    const hasData = initialEditorJs && initialEditorJs.blocks && initialEditorJs.blocks.length > 0;
    const currentHasData = editorData.blocks && editorData.blocks.length > 0;

    // If the data presence state changed significantly, recreate the editor
    if (hasData !== currentHasData && editorRef.current) {
      console.log('Data presence changed, recreating editor');
      if (editorRef.current.destroy) {
        editorRef.current.destroy();
      }
      editorRef.current = null;

      // Reinitialize with new data
      if (editorContainerRef.current) {
        setTimeout(() => {
          if (editorContainerRef.current && !editorRef.current) {
            try {
              editorRef.current = new EditorJS({
                holder: editorContainerRef.current!,
                data: editorData,
                readOnly: isPreview,
                tools: {
                  header: {
                    class: Header,
                    inlineToolbar: true,
                    config: {
                      levels: [1, 2, 3, 4, 5, 6],
                      defaultLevel: 2
                    }
                  },
                  paragraph: {
                    class: Paragraph,
                    inlineToolbar: true,
                  },
                  list: {
                    class: List,
                    inlineToolbar: true,
                  },
                  quote: {
                    class: Quote,
                    inlineToolbar: true,
                  },
                  code: {
                    class: Code,
                    inlineToolbar: true,
                  },
                  inlineCode: {
                    class: InlineCode,
                    shortcut: 'CMD+SHIFT+M',
                  },
                  linkTool: {
                    class: LinkTool,
                    config: {
                      endpoint: '/api/fetchUrl',
                    }
                  },
                  marker: {
                    class: Marker,
                  },
                  delimiter: {
                    class: Delimiter,
                  },
                  embed: {
                    class: Embed,
                    config: {
                      services: {
                        youtube: true,
                        coub: true,
                        codepen: true,
                        imgur: true,
                      }
                    }
                  },
                  table: Table,
                  image: {
                    class: ImageTool,
                    config: {
                      endpoints: {
                        byFile: '/api/uploadFile',
                        byUrl: '/api/fetchUrl',
                      }
                    }
                  },
                },
                placeholder: "Write page content…",
                minHeight: 400,
                autofocus: true,
              });

              editorRef.current.isReady
                .then(() => {
                  console.log('Editor.js recreated and ready');
                  setEditorReady(true);
                  setEditorData(initialEditorJs || { blocks: [] });

                  // Auto-focus the editor
                  if (editorRef.current && editorRef.current.focus) {
                    try {
                      editorRef.current.focus();
                    } catch (error) {
                      console.log('Focus method not available');
                    }
                  }
                })
                .catch((error) => {
                  console.error('Failed to recreate Editor.js:', error);
                });
            } catch (error) {
              console.error('Failed to create new Editor.js instance:', error);
            }
          }
        }, 100);
      }
    } else if (initialEditorJs) {
      // Just update the state if only content changed
      setEditorData(initialEditorJs);
    }
  }, [initialEditorJs]);

  const handleSave = async () => {
    if (editorRef.current) {
      try {
        const outputData = await editorRef.current.save();
        console.log('Editor.js save data:', outputData);
        setEditorData(outputData);
        onSave?.({ title: "Untitled Page", editorJs: outputData });
      } catch (error) {
        console.error('Saving failed: ', error);
      }
    }
  };

  // No separate preview renderer needed; we use EditorJS read-only mode

  // Markdown conversion removed; EditorJS read-only view is used for preview

  return (
    <Card className={cn("border-muted/70 shadow-lg", className)}>
      <CardContent className="p-0">

        <div className="px-8 pt-8 pb-4">
          <div className="flex items-center justify-end gap-3">
            <span className={cn("text-sm font-medium", !isPreview && "text-foreground", isPreview && "text-muted-foreground")}>Edit</span>
            <Switch checked={isPreview} onCheckedChange={(v) => setIsPreview(Boolean(v))} />
            <span className={cn("text-sm font-medium", isPreview && "text-foreground", !isPreview && "text-muted-foreground")}>Preview</span>
          </div>
          <div className="mt-6 relative">
            <div
              ref={editorContainerRef}
              className="border-2 rounded-lg bg-background min-h-[400px] max-h-[600px] overflow-auto editor-container"
              style={{
                padding: '55px',
                fontSize: '15px',
                lineHeight: '1.7',
                border: '2px solid hsl(var(--border))',
                backgroundColor: 'hsl(var(--background))',
                color: 'hsl(var(--foreground))',
              }}
              aria-busy={!editorReady}
            />
            {!editorReady && (
              <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-background/60 backdrop-blur-[1px]">
              </div>
            )}
          </div>
        </div>

        <div className="px-8 py-6 border-t-2 flex items-center justify-end gap-3 bg-muted/20">
          <Button onClick={handleSave} size="lg" className="px-8">Save Page</Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default PageCreateInline;

