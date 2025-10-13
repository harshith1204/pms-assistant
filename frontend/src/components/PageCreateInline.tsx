import React, { useEffect, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
  title?: string;
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

export const PageCreateInline: React.FC<PageCreateInlineProps> = ({ title = "", initialEditorJs, onSave, onDiscard, className }) => {
  const [name, setName] = useState<string>(title);
  const editorRef = useRef<EditorJS | null>(null);
  const editorContainerRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<string>("edit");
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
  console.log('PageCreateInline props:', { title, initialEditorJs });
  console.log('Editor data state:', editorData);

  useEffect(() => {
    console.log('Initializing Editor.js with data:', initialEditorJs);

    if (editorContainerRef.current && !editorRef.current) {
      try {
        editorRef.current = new EditorJS({
          holder: editorContainerRef.current,
          data: editorData,
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
        onSave?.({ title: name.trim() || "Untitled Page", editorJs: outputData });
      } catch (error) {
        console.error('Saving failed: ', error);
      }
    }
  };

  const handlePreview = async () => {
    if (editorRef.current) {
      try {
        const outputData = await editorRef.current.save();
        console.log('Editor.js preview data:', outputData);
        setEditorData(outputData);
        setActiveTab("preview");
      } catch (error) {
        console.error('Preview failed: ', error);
      }
    }
  };

  // Convert Editor.js blocks to markdown for preview
  const convertToMarkdown = (data: { blocks: Block[] }): string => {
    const blocks = data?.blocks || [];
    return blocks.map(block => {
      const { type, data } = block;
      switch (type) {
        case 'header': {
          const level = Math.min(6, Math.max(1, (data.level as number) || 2));
          return `${'#'.repeat(level)} ${(data.text as string) || ''}`;
        }
        case 'paragraph': {
          return (data.text as string) || '';
        }
        case 'list': {
          const items = (data.items as string[]) || [];
          const style = (data.style as string) === 'ordered' ? 'ol' : 'ul';
          if (style === 'ol') {
            return items.map((item: string, idx: number) => `${idx + 1}. ${item}`).join('\n');
          } else {
            return items.map((item: string) => `- ${item}`).join('\n');
          }
        }
        case 'quote': {
          const text = (data.text as string) || '';
          const caption = (data.caption as string) || '';
          return `> ${text}${caption ? `\n> — ${caption}` : ''}`;
        }
        case 'code': {
          const code = (data.code as string) || '';
          return `\`\`\`\n${code}\n\`\`\``;
        }
        case 'inlineCode': {
          return `\`${(data.text as string) || ''}\``;
        }
        case 'linkTool': {
          const link = (data.link as string) || '';
          const meta = (data.meta as any) || {};
          return `[${meta.title || link}](${link})`;
        }
        case 'marker': {
          return `==${(data.text as string) || ''}==`;
        }
        case 'delimiter': {
          return '---';
        }
        case 'embed': {
          const embed = (data.embed as string) || '';
          const source = (data.source as string) || '';
          const caption = (data.caption as string) || '';
          return `> ${embed}\n> Source: ${source}${caption ? `\n> ${caption}` : ''}`;
        }
        case 'table': {
          const content = (data.content as string[][]) || [];
          if (content.length === 0) return '';
          const headers = content[0] || [];
          const rows = content.slice(1) || [];
          let markdown = `| ${headers.join(' | ')} |\n`;
          markdown += `| ${headers.map(() => '---').join(' | ')} |\n`;
          rows.forEach((row: string[]) => {
            markdown += `| ${row.join(' | ')} |\n`;
          });
          return markdown;
        }
        case 'image': {
          const file = (data.file as any) || {};
          const url = file.url || (data.url as string) || '';
          const caption = (data.caption as string) || '';
          return `![${caption || 'Image'}](${url})`;
        }
        default: {
          return (data.text as string) || '';
        }
      }
    }).join('\n\n');
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
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="edit">Edit</TabsTrigger>
              <TabsTrigger value="preview" onClick={handlePreview}>Preview</TabsTrigger>
            </TabsList>
            <TabsContent value="edit" className="mt-4">
          <div className="relative">
                {!editorReady ? (
                  <div className="border rounded-md bg-background min-h-[220px] max-h-[420px] overflow-auto flex items-center justify-center">
                    <div className="text-muted-foreground">Loading editor...</div>
                  </div>
                ) : (
                  <div
                    ref={editorContainerRef}
                    className="border rounded-md bg-background min-h-[220px] max-h-[420px] overflow-auto editor-container"
                    style={{
                      padding: '16px',
                      fontSize: '14px',
                      lineHeight: '1.6',
                      border: '1px solid hsl(var(--border))',
                      backgroundColor: 'hsl(var(--background))',
                      color: 'hsl(var(--foreground))',
                    }}
                  />
                )}
              </div>
            </TabsContent>
            <TabsContent value="preview" className="mt-4">
              <div className="border rounded-md bg-background min-h-[220px] max-h-[420px] overflow-auto p-4">
                <pre className="whitespace-pre-wrap text-sm">
                  <code>{convertToMarkdown(editorData)}</code>
                </pre>
          </div>
            </TabsContent>
          </Tabs>
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

