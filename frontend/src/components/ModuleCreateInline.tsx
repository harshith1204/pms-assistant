import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import MDEditor from "@uiw/react-md-editor";
import "@uiw/react-md-editor/markdown-editor.css";
import { Card, CardContent } from "@/components/ui/card";
import { Calendar, Users, UserCircle, Layers, Wand2, FolderKanban } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";
import { cn } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fetchProjects, Project } from "@/api/projects";

export type ModuleCreateInlineProps = {
  title?: string;
  description?: string;
  onSave?: (values: { title: string; description: string; projectId?: string }) => void;
  onDiscard?: () => void;
  className?: string;
};

const FieldChip: React.FC<React.PropsWithChildren<{ icon?: React.ReactNode }>> = ({ icon, children }) => (
  <div className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs text-muted-foreground bg-background">
    {icon}
    <span className="whitespace-nowrap">{children}</span>
  </div>
);

export const ModuleCreateInline: React.FC<ModuleCreateInlineProps> = ({ 
  title = "", 
  description = "", 
  onSave, 
  onDiscard, 
  className 
}) => {
  const [name, setName] = React.useState<string>(title);
  const [desc, setDesc] = React.useState<string>(description);
  const [isEditingDesc, setIsEditingDesc] = React.useState<boolean>(true);
  const [selectedProjectId, setSelectedProjectId] = React.useState<string>("");
  const [projects, setProjects] = React.useState<Project[]>([]);

  React.useEffect(() => {
    const loadProjects = async () => {
      const projectsList = await fetchProjects();
      setProjects(projectsList);
    };
    loadProjects();
  }, []);

  const handleSave = () => {
    onSave?.({ title: name.trim(), description: desc, projectId: selectedProjectId || undefined });
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
          <MDEditor value={desc} onChange={(v) => setDesc(v || "")} height={260} preview={isEditingDesc ? "edit" : "preview"} hideToolbar={true} />
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
            <div className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs bg-background min-w-[180px]">
              <FolderKanban className="h-3.5 w-3.5 text-muted-foreground" />
              <Select value={selectedProjectId} onValueChange={setSelectedProjectId}>
                <SelectTrigger className="h-6 border-0 p-0 text-xs focus:ring-0 focus:ring-offset-0">
                  <SelectValue placeholder="Select project" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((project) => (
                    <SelectItem key={project._id} value={project._id}>
                      {project.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <FieldChip icon={<Calendar className="h-3.5 w-3.5" />}>Start date</FieldChip>
            <FieldChip icon={<Calendar className="h-3.5 w-3.5" />}>End date</FieldChip>
            <FieldChip icon={<Layers className="h-3.5 w-3.5" />}>Backlog</FieldChip>
            <FieldChip icon={<UserCircle className="h-3.5 w-3.5" />}>Lead</FieldChip>
            <FieldChip icon={<Users className="h-3.5 w-3.5" />}>Members</FieldChip>
          </div>
        </div>

        <div className="px-5 py-4 border-t flex items-center justify-end">
          <div className="flex items-center gap-2">
            <Button onClick={handleSave}>Save</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default ModuleCreateInline;
