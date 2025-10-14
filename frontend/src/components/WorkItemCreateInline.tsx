import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import MDEditor from "@uiw/react-md-editor";
import "@uiw/react-md-editor/markdown-editor.css";
import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Calendar, Hash, Users, Tag, CalendarClock, CalendarDays, Shuffle, Boxes, Plus, Wand2 } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";
import { cn } from "@/lib/utils";

export type WorkItemCreateInlineProps = {
  title?: string;
  description?: string;
  onSave?: (values: { title: string; description: string }) => void;
  onDiscard?: () => void;
  className?: string;
};

const FieldChip: React.FC<React.PropsWithChildren<{ icon?: React.ReactNode }>> = ({ icon, children }) => (
  <div className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs text-muted-foreground bg-background">
    {icon}
    <span className="whitespace-nowrap">{children}</span>
  </div>
);

export const WorkItemCreateInline: React.FC<WorkItemCreateInlineProps> = ({ title = "", description = "", onSave, onDiscard, className }) => {
  const [name, setName] = React.useState<string>(title);
  const [desc, setDesc] = React.useState<string>(description);
  const [createMore, setCreateMore] = React.useState<boolean>(false);
  const [isEditingDesc, setIsEditingDesc] = React.useState<boolean>(true);

  const handleSave = () => {
    onSave?.({ title: name.trim(), description: desc });
  };

  return (
    <Card className={cn("border-muted/70", className)}>
      <CardContent className="p-0">
        <div className="px-5 pt-4">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Title"
            className="h-11 text-base"
          />
        </div>

        <div className="px-5 pt-4">
          <div className="relative" data-color-mode="light">
            <MDEditor value={desc} onChange={(v) => setDesc(v || "")} height={260} preview={isEditingDesc ? "edit" : "preview"} />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="absolute bottom-3 right-3 h-7 gap-1"
              onClick={() => setIsEditingDesc((s) => !s)}
              title={isEditingDesc ? "Preview" : "Edit"}
            >
              <Wand2 className="h-4 w-4" />
              {isEditingDesc ? "Preview" : "Edit"}
            </Button>
          </div>
          {!isEditingDesc && (
            <div className="sr-only">
              <SafeMarkdown content={desc} />
            </div>
          )}
        </div>

        <div className="px-5 pb-4 pt-3">
          <div className="flex flex-wrap gap-2">
            <FieldChip icon={<Shuffle className="h-3.5 w-3.5" />}>Backlog</FieldChip>
            <FieldChip icon={<Tag className="h-3.5 w-3.5" />}>None</FieldChip>
            <FieldChip icon={<Users className="h-3.5 w-3.5" />}>Assignees</FieldChip>
            <FieldChip icon={<Tag className="h-3.5 w-3.5" />}>Labels</FieldChip>
            <FieldChip icon={<Calendar className="h-3.5 w-3.5" />}>Start date</FieldChip>
            <FieldChip icon={<CalendarDays className="h-3.5 w-3.5" />}>Due date</FieldChip>
            <FieldChip icon={<CalendarClock className="h-3.5 w-3.5" />}>Cycle</FieldChip>
            <FieldChip icon={<Boxes className="h-3.5 w-3.5" />}>Modules</FieldChip>
            <FieldChip icon={<Plus className="h-3.5 w-3.5" />}>Add parent</FieldChip>
          </div>
        </div>

        <div className="px-5 py-4 border-t flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-foreground">
            <Switch checked={createMore} onCheckedChange={(v) => setCreateMore(Boolean(v))} />
            <span>Create more</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={onDiscard}>Discard</Button>
            <Button onClick={handleSave}>Save</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default WorkItemCreateInline;


