import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import MDEditor from "@uiw/react-md-editor";
import "@uiw/react-md-editor/markdown-editor.css";
import { Card, CardContent } from "@/components/ui/card";
import { Calendar, Wand2, Briefcase, X } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";
import { cn } from "@/lib/utils";
import { createCycle, CreateCycleRequest } from "@/api/cycles";

export type CycleCreateInlineProps = {
  title?: string;
  description?: string;
  projectId?: string;
  projectName?: string;
  businessId?: string;
  businessName?: string;
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

export const CycleCreateInline: React.FC<CycleCreateInlineProps> = ({
  title = "",
  description = "",
  projectId,
  projectName,
  businessId,
  businessName,
  onSave,
  onDiscard,
  className
}) => {
  const [name, setName] = React.useState<string>(title);
  const [desc, setDesc] = React.useState<string>(description);
  const [isEditingDesc, setIsEditingDesc] = React.useState<boolean>(true);
  const [isLoading, setIsLoading] = React.useState<boolean>(false);

  // Date state
  const [startDate, setStartDate] = React.useState<string>('');
  const [endDate, setEndDate] = React.useState<string>('');
  const [showDatePicker, setShowDatePicker] = React.useState<boolean>(false);

  const handleSave = async () => {
    if (!name.trim()) {
      alert('Please enter a cycle title');
      return;
    }

    setIsLoading(true);

    try {
      const payload: CreateCycleRequest = {
        title: name.trim(),
        description: desc,
        startDate: startDate,
        endDate: endDate,
        projectId: projectId || '',
        businessId: businessId || '',
        createdBy: {
          id: localStorage.getItem('staffId') || '',
          name: localStorage.getItem('staffName') || ''
        }
      };

      const response = await createCycle(payload);
      onSave?.({ title: name.trim(), description: desc });
    } catch (error) {
      console.error('Failed to create cycle:', error);
      alert('Failed to create cycle. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDateRangeClick = () => {
    setShowDatePicker(!showDatePicker);
  };

  const handleStartDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setStartDate(e.target.value);
  };

  const handleEndDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEndDate(e.target.value);
  };

  const formatDateRange = () => {
    if (!startDate && !endDate) return 'Start date → End date';

    const start = startDate ? new Date(startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'Start';
    const end = endDate ? new Date(endDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'End';

    return `${start} → ${end}`;
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

        {/* Date Picker Section */}
        {showDatePicker && (
          <div className="px-5 py-4 border-b bg-muted/20">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Set cycle duration</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowDatePicker(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium">Start Date</label>
                  <Input
                    type="date"
                    value={startDate}
                    onChange={handleStartDateChange}
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">End Date</label>
                  <Input
                    type="date"
                    value={endDate}
                    onChange={handleEndDateChange}
                    className="mt-1"
                  />
                </div>
              </div>

              {startDate && endDate && new Date(startDate) > new Date(endDate) && (
                <div className="text-sm text-destructive">
                  End date must be after start date
                </div>
              )}
            </div>
          </div>
        )}

        <div className="px-5 pb-4 pt-3">
          <div className="flex flex-wrap gap-2">
            <FieldChip icon={<Briefcase className="h-3.5 w-3.5" />}>
              {projectName || 'Project'}
            </FieldChip>
            <FieldChip
              icon={<Calendar className="h-3.5 w-3.5" />}
              onClick={handleDateRangeClick}
              selected={!!(startDate || endDate)}
            >
              {formatDateRange()}
            </FieldChip>
          </div>
        </div>

        <div className="px-5 py-4 border-t flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              Create another
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={onDiscard}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={isLoading}>
              {isLoading ? 'Creating...' : 'Create cycle'}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default CycleCreateInline;
