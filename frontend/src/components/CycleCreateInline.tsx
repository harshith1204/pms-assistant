import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

export type CycleCreateInlineProps = {
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

export const CycleCreateInline: React.FC<CycleCreateInlineProps> = ({ 
  title = "", 
  description = "", 
  onSave, 
  onDiscard, 
  className 
}) => {
  const [cycleTitle, setCycleTitle] = React.useState<string>(title);
  const [cycleDescription, setCycleDescription] = React.useState<string>(description);

  const handleSave = () => {
    onSave?.({ title: cycleTitle.trim(), description: cycleDescription.trim() });
  };

  const handleCancel = () => {
    onDiscard?.();
  };

  return (
    <Card className={cn("border-muted/70 shadow-sm", className)}>
      <CardContent className="p-6">
        <h2 className="text-2xl font-semibold mb-6">Create cycle</h2>
        
        <div className="space-y-4">
          <Input
            value={cycleTitle}
            onChange={(e) => setCycleTitle(e.target.value)}
            placeholder="Title"
            className="h-12 text-base border-2 focus-visible:ring-2"
          />

          <Textarea
            value={cycleDescription}
            onChange={(e) => setCycleDescription(e.target.value)}
            placeholder="Description"
            className="min-h-[120px] text-base border-2 focus-visible:ring-2 resize-none"
          />

          <div className="flex gap-2 pt-2">
            <FieldButton icon={<Calendar className="h-4 w-4" />}>
              Start date → End date
            </FieldButton>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 mt-8">
          <Button 
            variant="ghost" 
            onClick={handleCancel}
            className="px-6"
          >
            Cancel
          </Button>
          <Button 
            onClick={handleSave}
            className="px-6 bg-purple-600 hover:bg-purple-700"
          >
            Create cycle
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default CycleCreateInline;
