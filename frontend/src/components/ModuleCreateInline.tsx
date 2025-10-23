import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import MDEditor from "@uiw/react-md-editor";
import "@uiw/react-md-editor/markdown-editor.css";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Calendar, Users, UserCircle, Layers, Wand2, Briefcase, X, ChevronDown, ChevronUp } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";
import { cn } from "@/lib/utils";
import { createModule, CreateModuleRequest } from "@/api/modules";
import { getProjectSettings, ProjectMember, ProjectState } from "@/api/projects";

export type ModuleCreateInlineProps = {
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

export const ModuleCreateInline: React.FC<ModuleCreateInlineProps> = ({
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

  // Module specific state
  const [selectedLead, setSelectedLead] = React.useState<any>(null);
  const [selectedMembers, setSelectedMembers] = React.useState<any[]>([]);
  const [selectedState, setSelectedState] = React.useState<any>(null);
  const [startDate, setStartDate] = React.useState<string>('');
  const [endDate, setEndDate] = React.useState<string>('');
  const [isBacklogEnabled, setIsBacklogEnabled] = React.useState<boolean>(false);

  // Data fetched from API
  const [states, setStates] = React.useState<ProjectState[]>([]);
  const [members, setMembers] = React.useState<ProjectMember[]>([]);

  // UI state
  const [showDatePicker, setShowDatePicker] = React.useState<boolean>(false);
  const [showMemberPicker, setShowMemberPicker] = React.useState<boolean>(false);
  const [showLeadPicker, setShowLeadPicker] = React.useState<boolean>(false);
  const [showStatePicker, setShowStatePicker] = React.useState<boolean>(false);

  React.useEffect(() => {
    if (projectId && businessId) {
      loadProjectData();
    }
  }, [projectId, businessId]);

  const loadProjectData = async () => {
    try {
      const settings = await getProjectSettings(projectId!, businessId!);
      setStates(settings.states || []);
      setMembers(settings.members || []);
    } catch (error) {
      console.error('Failed to load project data:', error);
    }
  };

  const handleSave = async () => {
    if (!name.trim()) {
      alert('Please enter a module title');
      return;
    }

    setIsLoading(true);

    try {
      const payload: CreateModuleRequest = {
        title: name.trim(),
        description: desc,
        state: isBacklogEnabled ? selectedState : undefined,
        lead: selectedLead,
        assignee: selectedMembers,
        startDate: startDate,
        endDate: endDate,
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
        }
      };

      const response = await createModule(payload);
      onSave?.({ title: name.trim(), description: desc });
    } catch (error) {
      console.error('Failed to create module:', error);
      alert('Failed to create module. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleMemberSelect = (member: ProjectMember) => {
    if (!selectedMembers.find(m => m.id === member.id)) {
      setSelectedMembers([...selectedMembers, { id: member.id, name: member.name }]);
    }
  };

  const handleMemberRemove = (memberId: string) => {
    setSelectedMembers(selectedMembers.filter(m => m.id !== memberId));
  };

  const handleLeadSelect = (member: ProjectMember) => {
    setSelectedLead({ id: member.id, name: member.name });
    setShowLeadPicker(false);
  };

  const handleStateSelect = (state: ProjectState) => {
    const subState = state.subStates?.[0];
    if (subState) {
      setSelectedState({ id: subState.id, name: subState.name });
    }
    setShowStatePicker(false);
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
                <h3 className="font-medium">Set module duration</h3>
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
            </div>
          </div>
        )}

        {/* Member Picker Section */}
        {showMemberPicker && (
          <div className="px-5 py-4 border-b bg-muted/20">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Select members</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowMemberPicker(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="grid grid-cols-1 gap-2 max-h-40 overflow-y-auto">
                {members.map(member => (
                  <div
                    key={member.id}
                    className={cn(
                      "p-2 border rounded cursor-pointer hover:bg-accent transition-colors",
                      selectedMembers.find(m => m.id === member.id) && "border-primary bg-primary/5"
                    )}
                    onClick={() => handleMemberSelect(member)}
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs font-medium">
                        {member.name.charAt(0).toUpperCase()}
                      </div>
                      <span className="text-sm">{member.name}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Lead Picker Section */}
        {showLeadPicker && (
          <div className="px-5 py-4 border-b bg-muted/20">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Select lead</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowLeadPicker(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="grid grid-cols-1 gap-2 max-h-40 overflow-y-auto">
                {members.map(member => (
                  <div
                    key={member.id}
                    className={cn(
                      "p-2 border rounded cursor-pointer hover:bg-accent transition-colors",
                      selectedLead?.id === member.id && "border-primary bg-primary/5"
                    )}
                    onClick={() => handleLeadSelect(member)}
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs font-medium">
                        {member.name.charAt(0).toUpperCase()}
                      </div>
                      <span className="text-sm">{member.name}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* State Picker Section */}
        {showStatePicker && (
          <div className="px-5 py-4 border-b bg-muted/20">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Select backlog state</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowStatePicker(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="grid grid-cols-1 gap-2 max-h-40 overflow-y-auto">
                {states.map(state => (
                  <div key={state.id} className="space-y-2">
                    <div className="font-medium text-sm">{state.name}</div>
                    {state.subStates?.map(subState => (
                      <div
                        key={subState.id}
                        className={cn(
                          "p-2 border rounded cursor-pointer hover:bg-accent transition-colors ml-4",
                          selectedState?.id === subState.id && "border-primary bg-primary/5"
                        )}
                        onClick={() => handleStateSelect(state)}
                      >
                        <span className="text-sm">{subState.name}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
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
            <FieldChip
              icon={<Layers className="h-3.5 w-3.5" />}
              onClick={() => {
                setIsBacklogEnabled(!isBacklogEnabled);
                if (!isBacklogEnabled) {
                  setShowStatePicker(true);
                }
              }}
              selected={isBacklogEnabled}
            >
              {selectedState?.name || 'Backlog'}
            </FieldChip>
            <FieldChip
              icon={<UserCircle className="h-3.5 w-3.5" />}
              onClick={() => setShowLeadPicker(true)}
              selected={!!selectedLead}
            >
              {selectedLead?.name || 'Lead'}
            </FieldChip>
            <FieldChip
              icon={<Users className="h-3.5 w-3.5" />}
              onClick={() => setShowMemberPicker(true)}
              selected={selectedMembers.length > 0}
            >
              {selectedMembers.length > 0
                ? `${selectedMembers.length} member${selectedMembers.length > 1 ? 's' : ''}`
                : 'Members'
              }
            </FieldChip>
          </div>

          {/* Selected members display */}
          {selectedMembers.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {selectedMembers.map(member => (
                <Badge key={member.id} variant="secondary" className="text-xs">
                  {member.name}
                  <button
                    onClick={() => handleMemberRemove(member.id)}
                    className="ml-1 hover:bg-destructive/20 rounded-full p-0.5"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}
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
              {isLoading ? 'Creating...' : 'Create module'}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default ModuleCreateInline;
