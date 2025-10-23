import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import MDEditor from "@uiw/react-md-editor";
import "@uiw/react-md-editor/markdown-editor.css";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Calendar, Hash, Users, Tag, CalendarClock, CalendarDays, Shuffle, Boxes, Plus, Wand2, Briefcase, X, ChevronDown, ChevronUp } from "lucide-react";
import SafeMarkdown from "@/components/SafeMarkdown";
import { cn } from "@/lib/utils";
import { createWorkItem, CreateWorkItemRequest, WorkItemState, WorkItemAssignee, WorkItemLabel, WorkItemProject, WorkItemBusiness, WorkItemModule, WorkItemCycle, WorkItemParent } from "@/api/workitems";
import { getProjectSettings, ProjectMember, ProjectState, ProjectLabel } from "@/api/projects";
import { generateWorkItemWithAI, generateWithAiSurprise } from "@/api/ai";

export type WorkItemCreateInlineProps = {
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

const FieldChip: React.FC<React.PropsWithChildren<{
  icon?: React.ReactNode;
  onClick?: () => void;
  onRemove?: () => void;
  removable?: boolean;
  selected?: boolean;
}>> = ({ icon, children, onClick, onRemove, removable = false, selected = false }) => (
  <div
    className={cn(
      "inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs bg-background cursor-pointer hover:bg-accent transition-colors",
      selected ? "text-foreground border-primary" : "text-muted-foreground",
      onClick && "hover:border-primary/50"
    )}
    onClick={onClick}
  >
    {icon}
    <span className="whitespace-nowrap">{children}</span>
    {removable && onRemove && (
      <button
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="ml-1 hover:bg-destructive/20 rounded-full p-0.5"
      >
        <X className="h-3 w-3" />
      </button>
    )}
  </div>
);

export const WorkItemCreateInline: React.FC<WorkItemCreateInlineProps> = ({
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

  // Work item specific state
  const [selectedState, setSelectedState] = React.useState<WorkItemState | null>(null);
  const [selectedAssignees, setSelectedAssignees] = React.useState<WorkItemAssignee[]>([]);
  const [selectedLabels, setSelectedLabels] = React.useState<WorkItemLabel[]>([]);
  const [selectedPriority, setSelectedPriority] = React.useState<string>('None');
  const [selectedStartDate, setSelectedStartDate] = React.useState<string>('');
  const [selectedDueDate, setSelectedDueDate] = React.useState<string>('');
  const [selectedCycle, setSelectedCycle] = React.useState<WorkItemCycle | null>(null);
  const [selectedModule, setSelectedModule] = React.useState<WorkItemModule | null>(null);
  const [selectedParent, setSelectedParent] = React.useState<WorkItemParent | null>(null);
  const [selectedEstimate, setSelectedEstimate] = React.useState<any>(null);
  const [estimateSystem, setEstimateSystem] = React.useState<string>('');

  // Data fetched from API
  const [states, setStates] = React.useState<ProjectState[]>([]);
  const [members, setMembers] = React.useState<ProjectMember[]>([]);
  const [labels, setLabels] = React.useState<ProjectLabel[]>([]);
  const [cycles, setCycles] = React.useState<any[]>([]);
  const [modules, setModules] = React.useState<any[]>([]);
  const [workItems, setWorkItems] = React.useState<any[]>([]);
  const [estimations, setEstimations] = React.useState<any[]>([]);

  // UI state
  const [showTemplates, setShowTemplates] = React.useState<boolean>(false);
  const [selectedTemplate, setSelectedTemplate] = React.useState<any>(null);
  const [userPrompt, setUserPrompt] = React.useState<string>('');

  // Template definitions
  const templates = [
    {
      id: 'bug-fix',
      name: 'Bug Fix',
      description: 'Report and track software bugs and issues',
      title: '🐛 Bug Fix: [Brief Description]',
      content: '## Bug Description\n\n## Steps to Reproduce\n\n## Expected Behavior\n\n## Actual Behavior\n\n## Additional Information\n',
      category: 'Development',
      priority: 'High',
      estimatedTime: 60,
      color: '#ef4444',
      icon: '🐛'
    },
    {
      id: 'feature-request',
      name: 'Feature Request',
      description: 'Request new features or functionality',
      title: '✨ Feature Request: [Feature Name]',
      content: '## Feature Description\n\n## Business Value\n\n## User Experience\n\n## Technical Requirements\n\n## Acceptance Criteria\n',
      category: 'General',
      priority: 'Medium',
      estimatedTime: 120,
      color: '#8b5cf6',
      icon: '✨'
    },
    {
      id: 'general-task',
      name: 'General Task',
      description: 'General work items and tasks',
      title: '📝 Task: [Task Description]',
      content: '## Task Description\n\n## Requirements\n\n## Deliverables\n\n## Notes\n',
      category: 'General',
      priority: 'Medium',
      estimatedTime: 60,
      color: '#3b82f6',
      icon: '📝'
    },
    {
      id: 'documentation',
      name: 'Documentation',
      description: 'Documentation and knowledge base updates',
      title: '📚 Documentation: [Document Title]',
      content: '## Document Title\n\n## Purpose\n\n## Content Outline\n\n## Target Audience\n\n## Review Requirements\n',
      category: 'Documentation',
      priority: 'Low',
      estimatedTime: 90,
      color: '#10b981',
      icon: '📚'
    },
    {
      id: 'research-task',
      name: 'Research Task',
      description: 'Research and investigation tasks',
      title: '🔍 Research: [Research Topic]',
      content: '## Research Topic\n\n## Research Questions\n\n## Methodology\n\n## Expected Findings\n\n## Resources Needed\n',
      category: 'Research',
      priority: 'Medium',
      estimatedTime: 180,
      color: '#f59e0b',
      icon: '🔍'
    },
    {
      id: 'code-review',
      name: 'Code Review',
      description: 'Code review and feedback',
      title: '👀 Code Review: [Component/Module]',
      content: '## Code Location\n\n## Review Focus Areas\n\n## Code Quality\n\n## Best Practices\n\n## Security Considerations\n',
      category: 'Review',
      priority: 'Medium',
      estimatedTime: 45,
      color: '#8b5cf6',
      icon: '👀'
    }
  ];

  React.useEffect(() => {
    if (projectId && businessId) {
      loadProjectData();
    }
  }, [projectId, businessId]);

  const loadProjectData = async () => {
    try {
      const settings = await getProjectSettings(projectId!, businessId!);
      setStates(settings.states || []);
      setLabels(settings.labels || []);
      setMembers(settings.members || []);
    } catch (error) {
      console.error('Failed to load project data:', error);
    }
  };

  const handleSave = async () => {
    if (!name.trim()) {
      alert('Please enter a work item title');
      return;
    }

    setIsLoading(true);

    try {
      const payload: CreateWorkItemRequest = {
        title: name.trim(),
        description: desc,
        startDate: selectedStartDate,
        endDate: selectedDueDate,
        label: selectedLabels,
        state: selectedState || undefined,
        priority: selectedPriority,
        estimate: selectedEstimate,
        estimateSystem: estimateSystem,
        status: 'ACCEPTED',
        assignee: selectedAssignees,
        modules: selectedModule || undefined,
        cycle: selectedCycle || undefined,
        parent: selectedParent || undefined,
        project: {
          id: projectId || '',
          name: projectName || ''
        },
        business: {
          id: businessId || '',
          name: businessName || ''
        },
        createdBy: {
          id: localStorage.getItem('staffId') || '',
          name: localStorage.getItem('staffName') || ''
        }
      };

      const response = await createWorkItem(payload);
      onSave?.({ title: name.trim(), description: desc });
    } catch (error) {
      console.error('Failed to create work item:', error);
      alert('Failed to create work item. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAssigneeSelect = (assignee: ProjectMember) => {
    if (!selectedAssignees.find(a => a.id === assignee.id)) {
      setSelectedAssignees([...selectedAssignees, { id: assignee.id, name: assignee.name }]);
    }
  };

  const handleAssigneeRemove = (assigneeId: string) => {
    setSelectedAssignees(selectedAssignees.filter(a => a.id !== assigneeId));
  };

  const handleLabelSelect = (label: ProjectLabel) => {
    if (!selectedLabels.find(l => l.id === label.id)) {
      setSelectedLabels([...selectedLabels, { id: label.id, name: label.name }]);
    }
  };

  const handleLabelRemove = (labelId: string) => {
    setSelectedLabels(selectedLabels.filter(l => l.id !== labelId));
  };

  const handleStateSelect = (state: ProjectState) => {
    const subState = state.subStates?.[0];
    if (subState) {
      setSelectedState({ id: subState.id, name: subState.name });
    }
  };

  const handlePrioritySelect = (priority: string) => {
    setSelectedPriority(priority);
  };

  const handleGenerateWithAI = async () => {
    if (!userPrompt.trim()) {
      alert('Please enter a prompt');
      return;
    }

    try {
      const template = {
        title: '✨ Generated Task',
        content: '## Generated Content\n\n## Requirements\n\n## Implementation\n'
      };

      const response = await generateWorkItemWithAI({
        prompt: userPrompt,
        template
      });

      setName(response.title || name);
      setDesc(response.description || response.content || desc);
      setUserPrompt('');
    } catch (error) {
      console.error('Failed to generate with AI:', error);
      alert('Failed to generate content with AI');
    }
  };

  const handleSurpriseMe = async () => {
    try {
      const response = await generateWithAiSurprise({
        title: name,
        description: desc
      });

      setName(response.title || name);
      setDesc(response.description || response.content || desc);
    } catch (error) {
      console.error('Failed to generate surprise content:', error);
      alert('Failed to generate surprise content');
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority.toUpperCase()) {
      case 'HIGH': return 'bg-red-100 text-red-800 border-red-200';
      case 'MEDIUM': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'LOW': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const handleTemplateSelect = (template: any) => {
    setSelectedTemplate(template);
    setName(template.title);
    setDesc(template.content);
    setSelectedPriority(template.priority);
    setShowTemplates(false);
  };

  const handleUseTemplate = () => {
    if (selectedTemplate && userPrompt.trim()) {
      handleGenerateWithAI();
    } else if (selectedTemplate) {
      handleTemplateSelect(selectedTemplate);
    }
  };

  return (
    <Card className={cn("border-muted/70", className)}>
      <CardContent className="p-0">
        <div className="px-5 pt-4">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Work item title"
            className="h-11 text-base"
          />
        </div>

        <div className="px-5 pt-4">
          <div className="relative" data-color-mode="light">
            <MDEditor
              value={desc}
              onChange={(v) => setDesc(v || "")}
              height={260}
              preview={isEditingDesc ? "edit" : "preview"}
              hideToolbar={true}
            />
            <div className="absolute bottom-3 right-3 flex gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="h-7 gap-1"
                onClick={handleSurpriseMe}
                title="Generate with AI"
              >
                <Wand2 className="h-4 w-4" />
                Surprise me
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="h-7 gap-1"
                onClick={() => setIsEditingDesc((s) => !s)}
                title={isEditingDesc ? "Preview" : "Edit"}
              >
                <Wand2 className="h-4 w-4" />
                {isEditingDesc ? "Preview" : "Edit"}
              </Button>
            </div>
          </div>
          {!isEditingDesc && (
            <div className="sr-only">
              <SafeMarkdown content={desc} />
            </div>
          )}
        </div>

        {/* Template Section */}
        {showTemplates && (
          <div className="px-5 py-4 border-b bg-muted/20">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Choose a template</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowTemplates(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {templates.map(template => (
                  <div
                    key={template.id}
                    className={cn(
                      "p-3 border rounded-lg cursor-pointer transition-colors hover:bg-accent",
                      selectedTemplate?.id === template.id && "border-primary bg-primary/5"
                    )}
                    onClick={() => setSelectedTemplate(template)}
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-lg">{template.icon}</span>
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium text-sm truncate">{template.name}</h4>
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {template.description}
                        </p>
                        <div className="flex items-center gap-2 mt-2">
                          <Badge variant="outline" className="text-xs">
                            {template.category}
                          </Badge>
                          <span className={cn("px-1.5 py-0.5 rounded text-xs", getPriorityColor(template.priority))}>
                            {template.priority}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {selectedTemplate && (
                <div className="space-y-3 p-3 border rounded-lg bg-background">
                  <div className="flex items-center gap-2">
                    <span>{selectedTemplate.icon}</span>
                    <span className="font-medium">{selectedTemplate.name}</span>
                  </div>

                  <div>
                    <label className="text-sm font-medium">Describe your requirements</label>
                    <Input
                      value={userPrompt}
                      onChange={(e) => setUserPrompt(e.target.value)}
                      placeholder="e.g., I need to fix the login issue where users can't reset their passwords"
                      className="mt-1"
                    />
                  </div>

                  <div className="flex gap-2">
                    <Button onClick={handleUseTemplate} size="sm">
                      Use template
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSelectedTemplate(null);
                        setUserPrompt('');
                      }}
                    >
                      Clear
                    </Button>
                  </div>
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
              icon={<Shuffle className="h-3.5 w-3.5" />}
              onClick={() => handleStateSelect(states[0])}
              selected={!!selectedState}
            >
              {selectedState?.name || 'State'}
            </FieldChip>

            <FieldChip
              icon={<Tag className="h-3.5 w-3.5" />}
              onClick={() => {/* Priority selection popup */}}
              selected={selectedPriority !== 'None'}
            >
              <span className={cn("px-1.5 py-0.5 rounded text-xs", getPriorityColor(selectedPriority))}>
                {selectedPriority}
              </span>
            </FieldChip>

            <FieldChip
              icon={<Users className="h-3.5 w-3.5" />}
              onClick={() => {/* Assignee selection popup */}}
              selected={selectedAssignees.length > 0}
            >
              {selectedAssignees.length > 0
                ? `${selectedAssignees.length} assignee${selectedAssignees.length > 1 ? 's' : ''}`
                : 'Assignees'
              }
            </FieldChip>

            <FieldChip
              icon={<Tag className="h-3.5 w-3.5" />}
              onClick={() => {/* Label selection popup */}}
              selected={selectedLabels.length > 0}
            >
              {selectedLabels.length > 0
                ? `${selectedLabels.length} label${selectedLabels.length > 1 ? 's' : ''}`
                : 'Labels'
              }
            </FieldChip>

            <FieldChip
              icon={<Calendar className="h-3.5 w-3.5" />}
              onClick={() => {/* Start date picker */}}
              selected={!!selectedStartDate}
            >
              {selectedStartDate ? new Date(selectedStartDate).toLocaleDateString() : 'Start date'}
            </FieldChip>

            <FieldChip
              icon={<CalendarDays className="h-3.5 w-3.5" />}
              onClick={() => {/* Due date picker */}}
              selected={!!selectedDueDate}
            >
              {selectedDueDate ? new Date(selectedDueDate).toLocaleDateString() : 'Due date'}
            </FieldChip>

            <FieldChip
              icon={<CalendarClock className="h-3.5 w-3.5" />}
              onClick={() => {/* Cycle selection popup */}}
              selected={!!selectedCycle}
            >
              {selectedCycle?.name || 'Cycle'}
            </FieldChip>

            <FieldChip
              icon={<Boxes className="h-3.5 w-3.5" />}
              onClick={() => {/* Module selection popup */}}
              selected={!!selectedModule}
            >
              {selectedModule?.name || 'Module'}
            </FieldChip>

            <FieldChip
              icon={<Plus className="h-3.5 w-3.5" />}
              onClick={() => {/* Parent selection popup */}}
              selected={!!selectedParent}
            >
              {selectedParent?.name || 'Add parent'}
            </FieldChip>
          </div>

          {/* Selected items display */}
          {selectedAssignees.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {selectedAssignees.map(assignee => (
                <Badge key={assignee.id} variant="secondary" className="text-xs">
                  {assignee.name}
                  <button
                    onClick={() => handleAssigneeRemove(assignee.id)}
                    className="ml-1 hover:bg-destructive/20 rounded-full p-0.5"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}

          {selectedLabels.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {selectedLabels.map(label => (
                <Badge key={label.id} variant="outline" className="text-xs">
                  {label.name}
                  <button
                    onClick={() => handleLabelRemove(label.id)}
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
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowTemplates(!showTemplates)}
            >
              {showTemplates ? (
                <>
                  <ChevronUp className="h-4 w-4 mr-1" />
                  Hide templates
                </>
              ) : (
                <>
                  <ChevronDown className="h-4 w-4 mr-1" />
                  Templates
                </>
              )}
            </Button>
            <Button variant="outline" size="sm">
              Create another
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={onDiscard}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={isLoading}>
              {isLoading ? 'Creating...' : 'Create work item'}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default WorkItemCreateInline;


