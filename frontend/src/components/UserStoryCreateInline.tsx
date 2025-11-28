import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Calendar, Users, Tag, Boxes, Target, Lightbulb, Shuffle, Wand2, Briefcase } from "lucide-react";
import { cn } from "@/lib/utils";
import ProjectSelector from "@/components/ProjectSelector";
import MemberSelector from "@/components/MemberSelector";
import LabelSelector from "@/components/LabelSelector";
import { DateRangePicker, DateRange } from "@/components/ui/date-range-picker";
import { type Project } from "@/api/projects";
import { type ProjectMember } from "@/api/members";
import { type ProjectLabel } from "@/api/labels";
import { type SubState } from "@/api/substates";
import { type Module } from "@/api/modules";
import { type Epic } from "@/api/epics";
import { type Feature } from "@/api/features";
import SubStateSelector from "@/components/SubStateSelector";
import ModuleSelector from "@/components/ModuleSelector";
import EpicSelector from "@/components/EpicSelector";
import FeatureSelector from "@/components/FeatureSelector";
import { getAllProjectData, sendProjectDataToConversation } from "@/api/projectData";

export type UserStoryCreateInlineProps = {
  title?: string;
  description?: string;
  persona?: string;
  userGoal?: string;
  demographics?: string;
  acceptanceCriteria?: string;
  selectedProject?: Project | null;
  selectedAssignees?: ProjectMember[];
  selectedLabels?: ProjectLabel[];
  selectedDateRange?: DateRange;
  selectedSubState?: SubState | null;
  selectedModule?: Module | null;
  selectedEpic?: Epic | null;
  selectedFeature?: Feature | null;
  onProjectSelect?: (project: Project | null) => void;
  onAssigneesSelect?: (assignees: ProjectMember[]) => void;
  onLabelsSelect?: (labels: ProjectLabel[]) => void;
  onDateSelect?: (dateRange: DateRange | undefined) => void;
  onSubStateSelect?: (subState: SubState | null) => void;
  onModuleSelect?: (module: Module | null) => void;
  onEpicSelect?: (epic: Epic | null) => void;
  onFeatureSelect?: (feature: Feature | null) => void;
  onSave?: (values: {
    title: string;
    description: string;
    persona: string;
    userGoal: string;
    demographics: string;
    acceptanceCriteria: string;
    project?: Project | null;
    assignees?: ProjectMember[];
    labels?: ProjectLabel[];
    subState?: SubState | null;
    module?: Module | null;
    epic?: Epic | null;
    feature?: Feature | null;
    startDate?: string;
    endDate?: string;
  }) => void;
  onDiscard?: () => void;
  className?: string;
  conversationId?: string;
  onProjectDataLoaded?: (message: string) => void;
};

const FieldChip: React.FC<React.PropsWithChildren<{ icon?: React.ReactNode; onClick?: () => void; className?: string }>> = ({ icon, children, onClick, className }) => (
  <div
    className={cn(
      "inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs text-muted-foreground bg-background",
      onClick && "cursor-pointer hover:bg-muted/50 hover:border-primary/20 transition-colors",
      className
    )}
    onClick={onClick}
  >
    {icon}
    <span className="whitespace-nowrap">{children}</span>
  </div>
);

export const UserStoryCreateInline: React.FC<UserStoryCreateInlineProps> = ({
  title = "",
  description = "",
  persona = "",
  userGoal = "",
  demographics = "",
  acceptanceCriteria = "",
  selectedProject = null,
  selectedAssignees = [],
  selectedLabels = [],
  selectedDateRange,
  selectedSubState = null,
  selectedModule = null,
  selectedEpic = null,
  selectedFeature = null,
  onProjectSelect,
  onAssigneesSelect,
  onLabelsSelect,
  onDateSelect,
  onSubStateSelect,
  onModuleSelect,
  onEpicSelect,
  onFeatureSelect,
  onSave,
  onDiscard,
  className,
  conversationId,
  onProjectDataLoaded
}) => {
  const [name, setName] = React.useState<string>(title);
  const [desc, setDesc] = React.useState<string>(description);
  const [personaValue, setPersonaValue] = React.useState<string>(persona);
  const [userGoalValue, setUserGoalValue] = React.useState<string>(userGoal);
  const [demographicsValue, setDemographicsValue] = React.useState<string>(demographics);
  const [acceptanceCriteriaValue, setAcceptanceCriteriaValue] = React.useState<string>(acceptanceCriteria);
  const [labels, setLabels] = React.useState<ProjectLabel[]>(selectedLabels);

  const handleSave = () => {
    const startDate = selectedDateRange?.from?.toISOString().split('T')[0];
    const endDate = selectedDateRange?.to?.toISOString().split('T')[0];
    onSave?.({
      title: name.trim(),
      description: desc,
      persona: personaValue,
      userGoal: userGoalValue,
      demographics: demographicsValue,
      acceptanceCriteria: acceptanceCriteriaValue,
      project: selectedProject,
      assignees: selectedAssignees,
      labels: labels,
      subState: selectedSubState,
      module: selectedModule,
      epic: selectedEpic,
      feature: selectedFeature,
      startDate,
      endDate
    });
  };

  const handleProjectSelect = async (project: Project | null) => {
    onProjectSelect?.(project);

    if (project) {
      try {
        const projectData = await getAllProjectData(project.projectId);
        const message = await sendProjectDataToConversation(
          projectData,
          project.projectName,
          project.projectDisplayId,
          conversationId
        );
        onProjectDataLoaded?.(message);
      } catch (error) {
        // Failed to fetch project data
      }
    }
  };

  const handleLabelsSelect = (newLabels: ProjectLabel[]) => {
    setLabels(newLabels);
    onLabelsSelect?.(newLabels);
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

        <div className="px-5 pt-4 grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Description</label>
            <Textarea
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="Describe the user story..."
              className="min-h-[120px] resize-y"
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-2 block">Persona</label>
            <Textarea
              value={personaValue}
              onChange={(e) => setPersonaValue(e.target.value)}
              placeholder="Who is the target user/persona?"
              className="min-h-[120px] resize-y"
            />
          </div>
        </div>

        <div className="px-5 pt-4">
          <label className="text-sm font-medium mb-2 block">User Goal</label>
          <Textarea
            value={userGoalValue}
            onChange={(e) => setUserGoalValue(e.target.value)}
            placeholder="What goal is the user trying to achieve?"
            className="min-h-[100px] resize-y"
          />
        </div>

        <div className="px-5 pt-4">
          <label className="text-sm font-medium mb-2 block">Demographics</label>
          <Textarea
            value={demographicsValue}
            onChange={(e) => setDemographicsValue(e.target.value)}
            placeholder="Describe target user demographics..."
            className="min-h-[100px] resize-y"
          />
        </div>

        <div className="px-5 pt-4">
          <label className="text-sm font-medium mb-2 block">Acceptance Criteria</label>
          <Textarea
            value={acceptanceCriteriaValue}
            onChange={(e) => setAcceptanceCriteriaValue(e.target.value)}
            placeholder="Define acceptance criteria for this user story..."
            className="min-h-[100px] resize-y"
          />
        </div>

        <div className="px-5 pb-4 pt-4">
          <div className="flex flex-wrap gap-2">
            <ProjectSelector
              selectedProject={selectedProject}
              onProjectSelect={handleProjectSelect}
              trigger={(
                <FieldChip
                  icon={<Briefcase className="h-3.5 w-3.5" />}
                  className={selectedProject ? "text-foreground border-primary/20 bg-primary/5" : undefined}
                >
                  {selectedProject ? `${selectedProject.projectName}` : "Project"}
                </FieldChip>
              )}
            />
            {selectedProject ? (
              <SubStateSelector
                projectId={selectedProject.projectId}
                selectedSubState={selectedSubState}
                onSubStateSelect={onSubStateSelect || (() => {})}
                trigger={
                  <FieldChip
                    icon={<Shuffle className="h-3.5 w-3.5" />}
                    className={selectedSubState ? "text-foreground border-primary/20 bg-primary/5" : undefined}
                  >
                    {selectedSubState ? selectedSubState.name : "States"}
                  </FieldChip>
                }
              />
            ) : (
              <FieldChip icon={<Shuffle className="h-3.5 w-3.5" />}>States</FieldChip>
            )}
            {selectedProject && (
              <MemberSelector
                projectId={selectedProject.projectId}
                selectedMembers={selectedAssignees}
                onMembersSelect={onAssigneesSelect || (() => {})}
                mode="multiple"
                title="Select Assignees"
                placeholder="Assignees"
                trigger={
                  <FieldChip
                    icon={<Users className="h-3.5 w-3.5" />}
                    className={selectedAssignees.length > 0 ? "text-foreground border-primary/20 bg-primary/5" : undefined}
                  >
                    {selectedAssignees.length > 0
                      ? `${selectedAssignees.length} assignee${selectedAssignees.length > 1 ? 's' : ''}`
                      : "Assignees"
                    }
                  </FieldChip>
                }
              />
            )}
            {!selectedProject && (
              <FieldChip icon={<Users className="h-3.5 w-3.5" />}>Assignees</FieldChip>
            )}
            {selectedProject ? (
              <LabelSelector
                projectId={selectedProject.projectId}
                selectedLabels={labels}
                onLabelsSelect={handleLabelsSelect}
                mode="multiple"
                title="Select Labels"
                placeholder="Labels"
                trigger={
                  <FieldChip
                    icon={<Tag className="h-3.5 w-3.5" />}
                    className={labels?.length > 0 ? "text-foreground border-primary/20 bg-primary/5" : undefined}
                  >
                    {labels?.length === 0 ? "Labels" :
                     labels?.length === 1 ? labels[0].label :
                     `${labels?.length} labels`}
                  </FieldChip>
                }
              />
            ) : (
              <FieldChip icon={<Tag className="h-3.5 w-3.5" />}>Labels</FieldChip>
            )}
            <DateRangePicker
              date={selectedDateRange}
              onDateChange={onDateSelect}
              placeholder="Duration"
              icon={<Calendar className="h-3.5 w-3.5" />}
            />
            {selectedProject ? (
              <EpicSelector
                projectId={selectedProject.projectId}
                selectedEpic={selectedEpic}
                onEpicSelect={onEpicSelect || (() => {})}
                trigger={
                  <FieldChip
                    icon={<Target className="h-3.5 w-3.5" />}
                    className={selectedEpic ? "text-foreground border-primary/20 bg-primary/5" : undefined}
                  >
                    {selectedEpic ? selectedEpic.title : "Epic"}
                  </FieldChip>
                }
              />
            ) : (
              <FieldChip icon={<Target className="h-3.5 w-3.5" />}>Epic</FieldChip>
            )}
            {selectedProject ? (
              <ModuleSelector
                projectId={selectedProject.projectId}
                selectedModule={selectedModule}
                onModuleSelect={onModuleSelect || (() => {})}
                trigger={
                  <FieldChip
                    icon={<Boxes className="h-3.5 w-3.5" />}
                    className={selectedModule ? "text-foreground border-primary/20 bg-primary/5" : undefined}
                  >
                    {selectedModule ? selectedModule.title : "Modules"}
                  </FieldChip>
                }
              />
            ) : (
              <FieldChip icon={<Boxes className="h-3.5 w-3.5" />}>Modules</FieldChip>
            )}
            {selectedProject ? (
              <FeatureSelector
                projectId={selectedProject.projectId}
                selectedFeature={selectedFeature}
                onFeatureSelect={onFeatureSelect || (() => {})}
                trigger={
                  <FieldChip
                    icon={<Lightbulb className="h-3.5 w-3.5" />}
                    className={selectedFeature ? "text-foreground border-primary/20 bg-primary/5" : undefined}
                  >
                    {selectedFeature ? (selectedFeature.basicInfo?.title || selectedFeature.title) : "Feature"}
                  </FieldChip>
                }
              />
            ) : (
              <FieldChip icon={<Lightbulb className="h-3.5 w-3.5" />}>Feature</FieldChip>
            )}
          </div>
        </div>

        <div className="px-5 py-4 border-t flex items-center justify-end">
          <div className="flex items-center gap-2">
            {onDiscard && (
              <Button variant="ghost" onClick={onDiscard}>Discard</Button>
            )}
            <Button onClick={handleSave}>Save</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default UserStoryCreateInline;
