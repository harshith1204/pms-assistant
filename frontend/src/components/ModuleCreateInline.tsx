import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Calendar, Users, UserCircle, Layers } from "lucide-react";
import { cn } from "@/lib/utils";

export type ModuleCreateInlineProps = {
  title?: string;
  description?: string;
  onSave?: (values: { title: string; description: string }) => void;
  onDiscard?: () => void;
  className?: string;
};

const FieldButton: React.FC<React.PropsWithChildren<{ icon?: React.ReactNode; onClick?: () => void }>> = ({ icon, children, onClick }) => (
  <button 
    onClick={onClick}
    className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm text-muted-foreground bg-background hover:bg-muted/50 transition-colors"
  >
    {icon}
    <span className="whitespace-nowrap">{children}</span>
  </button>
);

export const ModuleCreateInline: React.FC<ModuleCreateInlineProps> = ({ 
  title = "", 
  description = "", 
  onSave, 
  onDiscard, 
  className 
}) => {
  const [moduleTitle, setModuleTitle] = React.useState<string>(title);
  const [moduleDescription, setModuleDescription] = React.useState<string>(description);

  const handleSave = () => {
    onSave?.({ title: moduleTitle.trim(), description: moduleDescription.trim() });
  };

  const handleDiscard = () => {
    onDiscard?.();
  };

  return (
    <Card className={cn("border-muted/70 shadow-sm", className)}>
      <CardContent className="p-6">
        <h2 className="text-2xl font-semibold mb-6">Create module</h2>
        
        <div className="flex items-center gap-3 mb-6">
          <div className="flex items-center justify-center w-10 h-10 rounded bg-amber-100">
            <span className="text-xl">📦</span>
          </div>
          <span className="text-base font-medium text-muted-foreground">Simpo Tech</span>
        </div>

        <div className="space-y-4">
          <Input
            value={moduleTitle}
            onChange={(e) => setModuleTitle(e.target.value)}
            placeholder="Title"
            className="h-12 text-base border-2 focus-visible:ring-2"
          />

          <Textarea
            value={moduleDescription}
            onChange={(e) => setModuleDescription(e.target.value)}
            placeholder="Click to add description"
            className="min-h-[140px] text-base border-2 focus-visible:ring-2 resize-none"
          />

          <div className="flex flex-wrap gap-2 pt-2">
            <FieldButton icon={<Calendar className="h-4 w-4" />}>
              Start date → End date
            </FieldButton>
            <FieldButton icon={<Layers className="h-4 w-4" />}>
              Backlog
            </FieldButton>
            <FieldButton icon={<UserCircle className="h-4 w-4" />}>
              Lead
            </FieldButton>
            <FieldButton icon={<Users className="h-4 w-4" />}>
              Members
            </FieldButton>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 mt-8 pt-6 border-t">
          <Button 
            variant="ghost" 
            onClick={handleDiscard}
            className="px-6"
          >
            Discard
          </Button>
          <Button 
            onClick={handleSave}
            className="px-6 bg-purple-600 hover:bg-purple-700"
          >
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default ModuleCreateInline;
