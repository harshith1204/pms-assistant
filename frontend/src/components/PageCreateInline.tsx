import React, { useEffect, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
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
import { Briefcase, Wand2, Eye, EyeOff, Save, X, Calendar, Users } from 'lucide-react';
import { createPage, CreatePageRequest } from "@/api/pages";
import { getProjectSettings, ProjectMember } from "@/api/projects";

export type PageCreateInlineProps = {
  initialEditorJs?: { blocks: Block[] };
  projectId?: string;
  projectName?: string;
  businessId?: string;
  businessName?: string;
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

const FieldChip: React.FC<React.PropsWithChildren<{ icon?: React.ReactNode }>> = ({ icon, children }) => (
  <div className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs text-muted-foreground bg-background">
    {icon}
    <span className="whitespace-nowrap">{children}</span>
  </div>
);

const Placeholder: React.FC = () => (
  <div className="absolute pointer-events-none text-muted-foreground/70">Write page content…</div>
);

export const PageCreateInline: React.FC<PageCreateInlineProps> = ({
  initialEditorJs,
  projectId,
  projectName,
  businessId,
  businessName,
  onSave,
  onDiscard,
  className
}) => {
  const editorRef = useRef<EditorJS | null>(null);
  const editorContainerRef = useRef<HTMLDivElement>(null);
  const [isPreview, setIsPreview] = useState<boolean>(false);
  const [editorData, setEditorData] = useState<{ blocks: Block[] }>(initialEditorJs || {
    blocks: [
      {
        id: 'test-block',
        type: 'paragraph',
        data: {
          text: 'Start writing your page content here...'
        }
      }
    ]
  });
  const [editorReady, setEditorReady] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Page specific state
  const [pageTitle, setPageTitle] = useState<string>('');
  const [visibility, setVisibility] = useState<'PUBLIC' | 'PRIVATE' | 'ARCHIVED'>('PUBLIC');
  const [isLocked, setIsLocked] = useState<boolean>(false);
  const [selectedMembers, setSelectedMembers] = useState<any[]>([]);
  const [selectedCycles, setSelectedCycles] = useState<any[]>([]);
  const [selectedModules, setSelectedModules] = useState<any[]>([]);

  // Data fetched from API
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [cycles, setCycles] = useState<any[]>([]);
  const [modules, setModules] = useState<any[]>([]);

  // UI state
  const [showMemberPicker, setShowMemberPicker] = useState<boolean>(false);
  const [showCyclePicker, setShowCyclePicker] = useState<boolean>(false);
  const [showModulePicker, setShowModulePicker] = useState<boolean>(false);
  const [wordCount, setWordCount] = useState<number>(0);
  const [readTime, setReadTime] = useState<string>('0 minutes');

  React.useEffect(() => {
    if (projectId && businessId) {
      loadProjectData();
    }
  }, [projectId, businessId]);

  const loadProjectData = async () => {
    try {
      const settings = await getProjectSettings(projectId!, businessId!);
      setMembers(settings.members || []);
    } catch (error) {
      console.error('Failed to load project data:', error);
    }
  };

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
          minHeight: 400,
          autofocus: !isPreview,
          onChange: async () => {
            if (editorRef.current) {
              try {
                const output = await editorRef.current.save();
                calculateReadTime(output.blocks);
              } catch (error) {
                console.error('Failed to calculate read time:', error);
              }
            }
          }
        });

        editorRef.current.isReady
          .then(() => {
            console.log('Editor.js is ready to work!');
            setEditorReady(true);
            calculateReadTime(editorData.blocks);

            // Auto-focus the editor
            if (editorRef.current && editorRef.current.focus && !isPreview) {
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
    if (!pageTitle.trim()) {
      alert('Please enter a page title');
      return;
    }

    if (editorRef.current) {
      setIsLoading(true);

      try {
        const outputData = await editorRef.current.save();
        console.log('Editor.js save data:', outputData);
        setEditorData(outputData);

        const contentString = JSON.stringify(outputData);

        const payload: CreatePageRequest = {
          title: pageTitle.trim(),
          content: contentString,
          business: {
            id: businessId || '',
            name: businessName || ''
          },
          project: {
            id: projectId || '',
            name: projectName || ''
          },
          createdBy: {
            id: localStorage.getItem('staffId') || '',
            name: localStorage.getItem('staffName') || ''
          },
          visibility: visibility,
          locked: isLocked,
          favourite: false,
          readTime: readTime,
          wordCount: wordCount,
          linkedCycle: selectedCycles,
          linkedModule: selectedModules,
          linkedMembers: selectedMembers,
          linkedPages: []
        };

        const response = await createPage(payload);
        onSave?.({ title: pageTitle.trim(), editorJs: outputData });
      } catch (error) {
        console.error('Saving failed: ', error);
        alert('Failed to save page. Please try again.');
      } finally {
        setIsLoading(false);
      }
    }
  };

  const calculateReadTime = (blocks: Block[]) => {
    const text = blocks
      .filter(block => block.data?.text)
      .map(block => block.data.text)
      .join(' ')
      .replace(/<[^>]*>/g, '');

    const words = text.split(/\s+/).length;
    setWordCount(words);

    const wordsPerMinute = 225;
    const minutes = Math.ceil(words / wordsPerMinute);
    setReadTime(`${minutes} minute${minutes !== 1 ? 's' : ''}`);
  };

  // No separate preview renderer needed; we use EditorJS read-only mode

  // Markdown conversion removed; EditorJS read-only view is used for preview

  return (
    <Card className={cn("border-muted/70 shadow-lg", className)}>
      <CardContent className="p-0">

        {/* Header with title and actions */}
        <div className="px-8 pt-8 pb-4 border-b">
          <div className="flex items-center justify-between mb-4">
            <Input
              value={pageTitle}
              onChange={(e) => setPageTitle(e.target.value)}
              placeholder="Page title"
              className="text-2xl font-semibold border-none px-0 shadow-none focus-visible:ring-0"
            />
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">{wordCount} words • {readTime}</span>
              <span className={cn("text-sm font-medium", !isPreview && "text-foreground", isPreview && "text-muted-foreground")}>Edit</span>
              <Switch checked={isPreview} onCheckedChange={(v) => setIsPreview(Boolean(v))} />
              <span className={cn("text-sm font-medium", isPreview && "text-foreground", !isPreview && "text-muted-foreground")}>Preview</span>
            </div>
          </div>

          {/* Visibility and member controls */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Visibility:</span>
                <Button
                  variant={visibility === 'PUBLIC' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setVisibility('PUBLIC')}
                >
                  <Eye className="h-4 w-4 mr-1" />
                  Public
                </Button>
                <Button
                  variant={visibility === 'PRIVATE' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setVisibility('PRIVATE')}
                >
                  <EyeOff className="h-4 w-4 mr-1" />
                  Private
                </Button>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Linked:</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowCyclePicker(true)}
                >
                  <Calendar className="h-4 w-4 mr-1" />
                  {selectedCycles.length > 0 ? `${selectedCycles.length} cycle${selectedCycles.length > 1 ? 's' : ''}` : 'Cycles'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowModulePicker(true)}
                >
                  {selectedModules.length > 0 ? `${selectedModules.length} module${selectedModules.length > 1 ? 's' : ''}` : 'Modules'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowMemberPicker(true)}
                >
                  <Users className="h-4 w-4 mr-1" />
                  {selectedMembers.length > 0 ? `${selectedMembers.length} member${selectedMembers.length > 1 ? 's' : ''}` : 'Members'}
                </Button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm">
                <Wand2 className="h-4 w-4 mr-1" />
                Templates
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsLocked(!isLocked)}
              >
                {isLocked ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </div>

        {/* Editor */}
        <div className="relative">
          <div
            ref={editorContainerRef}
            className="min-h-[400px] max-h-[600px] overflow-auto editor-container"
            style={{
              padding: '32px',
              fontSize: '15px',
              lineHeight: '1.7',
              backgroundColor: 'hsl(var(--background))',
              color: 'hsl(var(--foreground))',
            }}
            aria-busy={!editorReady}
          />
          {!editorReady && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/60 backdrop-blur-[1px]">
              <div className="text-muted-foreground">Loading editor...</div>
            </div>
          )}
        </div>

        {/* Footer with save actions */}
        <div className="px-8 py-6 border-t-2 flex items-center justify-between bg-muted/20">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Last saved: Never</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={onDiscard}>
              <X className="h-4 w-4 mr-1" />
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={isLoading} size="lg" className="px-8">
              <Save className="h-4 w-4 mr-1" />
              {isLoading ? 'Saving...' : 'Save Page'}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default PageCreateInline;

