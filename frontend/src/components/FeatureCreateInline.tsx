import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Calendar, Users, Tag, Boxes, Target, Plus, Trash2, Shuffle, Briefcase, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
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
import SubStateSelector from "@/components/SubStateSelector";
import ModuleSelector from "@/components/ModuleSelector";
import EpicSelector from "@/components/EpicSelector";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getAllProjectData, sendProjectDataToConversation } from "@/api/projectData";

type FunctionalRequirement = {
  requirementId: string;
  priorityLevel: string;
  description: string;
};

type NonFunctionalRequirement = {
  requirementId: string;
  priorityLevel: string;
  description: string;
};

type Risk = {
  riskId: string;
  problemLevel: string;
  impactLevel: string;
  description: string;
  strategy: string;
  riskOwner?: { id: string; name: string };
};

export type FeatureCreateInlineProps = {
  title?: string;
  description?: string;
  problemStatement?: string;
  objective?: string;
  successCriteria?: string[];
  goals?: string[];
  painPoints?: string[];
  inScope?: string[];
  outOfScope?: string[];
  functionalRequirements?: FunctionalRequirement[];
  nonFunctionalRequirements?: NonFunctionalRequirement[];
  dependencies?: string[];
  risks?: Risk[];
  selectedProject?: Project | null;
  selectedAssignees?: ProjectMember[];
  selectedLabels?: ProjectLabel[];
  selectedDateRange?: DateRange;
  selectedSubState?: SubState | null;
  selectedModule?: Module | null;
  selectedEpic?: Epic | null;
  onProjectSelect?: (project: Project | null) => void;
  onAssigneesSelect?: (assignees: ProjectMember[]) => void;
  onLabelsSelect?: (labels: ProjectLabel[]) => void;
  onDateSelect?: (dateRange: DateRange | undefined) => void;
  onSubStateSelect?: (subState: SubState | null) => void;
  onModuleSelect?: (module: Module | null) => void;
  onEpicSelect?: (epic: Epic | null) => void;
  onSave?: (values: {
    title: string;
    description: string;
    problemStatement: string;
    objective: string;
    successCriteria: string[];
    goals: string[];
    painPoints: string[];
    inScope: string[];
    outOfScope: string[];
    functionalRequirements: FunctionalRequirement[];
    nonFunctionalRequirements: NonFunctionalRequirement[];
    dependencies: string[];
    risks: Risk[];
    project?: Project | null;
    assignees?: ProjectMember[];
    labels?: ProjectLabel[];
    subState?: SubState | null;
    module?: Module | null;
    epic?: Epic | null;
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

export const FeatureCreateInline: React.FC<FeatureCreateInlineProps> = ({
  title = "",
  description = "",
  problemStatement = "",
  objective = "",
  successCriteria = [],
  goals = [],
  painPoints = [],
  inScope = [],
  outOfScope = [],
  functionalRequirements = [],
  nonFunctionalRequirements = [],
  dependencies = [],
  risks = [],
  selectedProject = null,
  selectedAssignees = [],
  selectedLabels = [],
  selectedDateRange,
  selectedSubState = null,
  selectedModule = null,
  selectedEpic = null,
  onProjectSelect,
  onAssigneesSelect,
  onLabelsSelect,
  onDateSelect,
  onSubStateSelect,
  onModuleSelect,
  onEpicSelect,
  onSave,
  onDiscard,
  className,
  conversationId,
  onProjectDataLoaded
}) => {
  const [name, setName] = React.useState<string>(title);
  const [desc, setDesc] = React.useState<string>(description);
  const [problem, setProblem] = React.useState<string>(problemStatement);
  const [obj, setObj] = React.useState<string>(objective);
  const [criteria, setCriteria] = React.useState<string[]>(successCriteria.length > 0 ? successCriteria : [""]);
  const [goalsList, setGoalsList] = React.useState<string[]>(goals.length > 0 ? goals : [""]);
  const [painPointsList, setPainPointsList] = React.useState<string[]>(painPoints.length > 0 ? painPoints : [""]);
  const [inScopeList, setInScopeList] = React.useState<string[]>(inScope.length > 0 ? inScope : [""]);
  const [outOfScopeList, setOutOfScopeList] = React.useState<string[]>(outOfScope.length > 0 ? outOfScope : [""]);
  const [frList, setFrList] = React.useState<FunctionalRequirement[]>(functionalRequirements.length > 0 ? functionalRequirements : [{ requirementId: "FR-001", priorityLevel: "", description: "" }]);
  const [nfrList, setNfrList] = React.useState<NonFunctionalRequirement[]>(nonFunctionalRequirements.length > 0 ? nonFunctionalRequirements : [{ requirementId: "NFR-001", priorityLevel: "", description: "" }]);
  const [depsList, setDepsList] = React.useState<string[]>(dependencies.length > 0 ? dependencies : [""]);
  const [risksList, setRisksList] = React.useState<Risk[]>(risks.length > 0 ? risks : [{ riskId: "R-001", problemLevel: "", impactLevel: "", description: "", strategy: "" }]);
  const [labels, setLabels] = React.useState<ProjectLabel[]>(selectedLabels);

  const handleSave = () => {
    const startDate = selectedDateRange?.from?.toISOString().split('T')[0];
    const endDate = selectedDateRange?.to?.toISOString().split('T')[0];
    onSave?.({
      title: name.trim(),
      description: desc,
      problemStatement: problem,
      objective: obj,
      successCriteria: criteria.filter(c => c.trim()),
      goals: goalsList.filter(g => g.trim()),
      painPoints: painPointsList.filter(p => p.trim()),
      inScope: inScopeList.filter(s => s.trim()),
      outOfScope: outOfScopeList.filter(s => s.trim()),
      functionalRequirements: frList.filter(f => f.description.trim()),
      nonFunctionalRequirements: nfrList.filter(n => n.description.trim()),
      dependencies: depsList.filter(d => d.trim()),
      risks: risksList.filter(r => r.description.trim()),
      project: selectedProject,
      assignees: selectedAssignees,
      labels: labels,
      subState: selectedSubState,
      module: selectedModule,
      epic: selectedEpic,
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

  // Helper functions for dynamic lists
  const addListItem = (setter: React.Dispatch<React.SetStateAction<string[]>>) => {
    setter(prev => [...prev, ""]);
  };

  const updateListItem = (setter: React.Dispatch<React.SetStateAction<string[]>>, index: number, value: string) => {
    setter(prev => {
      const updated = [...prev];
      updated[index] = value;
      return updated;
    });
  };

  const removeListItem = (setter: React.Dispatch<React.SetStateAction<string[]>>, index: number) => {
    setter(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <Card className={cn("border-muted/70", className)}>
      <CardContent className="p-0">
        <div className="px-5 pt-4 grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Feature Name <span className="text-red-500">*</span></label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Interactive Data Visualizations"
              className="h-10"
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-2 block">Description</label>
            <Input
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="Brief description of the feature"
              className="h-10"
            />
          </div>
        </div>

        <div className="px-5 pt-4 grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Problem Statement <span className="text-red-500">*</span></label>
            <Textarea
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              placeholder="Describe the problem..."
              className="min-h-[80px] resize-y"
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-2 block">Objective <span className="text-red-500">*</span></label>
            <Textarea
              value={obj}
              onChange={(e) => setObj(e.target.value)}
              placeholder="What is the goal or purpose of this feature?"
              className="min-h-[80px] resize-y"
            />
          </div>
        </div>

        <div className="px-5 pt-4">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium">Success Criteria <span className="text-red-500">*</span></label>
            <Button variant="outline" size="sm" onClick={() => setCriteria(prev => [...prev, ""])} className="h-7 text-xs">
              <Plus className="h-3 w-3 mr-1" /> Add Criterion
            </Button>
          </div>
          {criteria.map((c, i) => (
            <div key={i} className="flex items-center gap-2 mb-2">
              <Input
                value={c}
                onChange={(e) => {
                  const updated = [...criteria];
                  updated[i] = e.target.value;
                  setCriteria(updated);
                }}
                placeholder="e.g., 90% task completion rate within 3 days"
                className="flex-1"
              />
              {criteria.length > 1 && (
                <Button variant="ghost" size="sm" onClick={() => setCriteria(prev => prev.filter((_, idx) => idx !== i))} className="h-8 w-8 p-0">
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
              )}
            </div>
          ))}
        </div>

        <div className="px-5 pt-4">
          <Card className="border-muted">
            <CardContent className="p-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium">Goals</label>
                    <Button variant="outline" size="sm" onClick={() => addListItem(setGoalsList)} className="h-7 text-xs">
                      <Plus className="h-3 w-3 mr-1" /> Add Goal
                    </Button>
                  </div>
                  {goalsList.map((g, i) => (
                    <div key={i} className="flex items-center gap-2 mb-2">
                      <Input
                        value={g}
                        onChange={(e) => updateListItem(setGoalsList, i, e.target.value)}
                        placeholder="What does this user want to achieve?"
                        className="flex-1"
                      />
                      {goalsList.length > 1 && (
                        <Button variant="ghost" size="sm" onClick={() => removeListItem(setGoalsList, i)} className="h-8 w-8 p-0">
                          <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium">Pain Points</label>
                    <Button variant="outline" size="sm" onClick={() => addListItem(setPainPointsList)} className="h-7 text-xs">
                      <Plus className="h-3 w-3 mr-1" /> Add Pain Point
                    </Button>
                  </div>
                  {painPointsList.map((p, i) => (
                    <div key={i} className="flex items-center gap-2 mb-2">
                      <Input
                        value={p}
                        onChange={(e) => updateListItem(setPainPointsList, i, e.target.value)}
                        placeholder="What frustrates this user?"
                        className="flex-1"
                      />
                      {painPointsList.length > 1 && (
                        <Button variant="ghost" size="sm" onClick={() => removeListItem(setPainPointsList, i)} className="h-8 w-8 p-0">
                          <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="px-5 pt-4">
          <Card className="border-muted">
            <CardContent className="p-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <label className="text-sm font-medium">In Scope</label>
                    <Button variant="outline" size="sm" onClick={() => addListItem(setInScopeList)} className="h-7 text-xs ml-auto">
                      <Plus className="h-3 w-3 mr-1" /> Add In Scope
                    </Button>
                  </div>
                  {inScopeList.map((s, i) => (
                    <div key={i} className="flex items-center gap-2 mb-2">
                      <Input
                        value={s}
                        onChange={(e) => updateListItem(setInScopeList, i, e.target.value)}
                        placeholder="What's included?"
                        className="flex-1"
                      />
                      {inScopeList.length > 1 && (
                        <Button variant="ghost" size="sm" onClick={() => removeListItem(setInScopeList, i)} className="h-8 w-8 p-0">
                          <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <XCircle className="h-4 w-4 text-red-600" />
                    <label className="text-sm font-medium">Out of Scope</label>
                    <Button variant="outline" size="sm" onClick={() => addListItem(setOutOfScopeList)} className="h-7 text-xs ml-auto">
                      <Plus className="h-3 w-3 mr-1" /> Add Out of Scope
                    </Button>
                  </div>
                  {outOfScopeList.map((s, i) => (
                    <div key={i} className="flex items-center gap-2 mb-2">
                      <Input
                        value={s}
                        onChange={(e) => updateListItem(setOutOfScopeList, i, e.target.value)}
                        placeholder="What's NOT included?"
                        className="flex-1"
                      />
                      {outOfScopeList.length > 1 && (
                        <Button variant="ghost" size="sm" onClick={() => removeListItem(setOutOfScopeList, i)} className="h-8 w-8 p-0">
                          <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="px-5 pt-4">
          <Card className="border-muted">
            <CardContent className="p-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium">Functional Requirements</label>
                    <Button variant="outline" size="sm" onClick={() => setFrList(prev => [...prev, { requirementId: `FR-${String(prev.length + 1).padStart(3, '0')}`, priorityLevel: "", description: "" }])} className="h-7 text-xs">
                      <Plus className="h-3 w-3 mr-1" /> Add Requirement
                    </Button>
                  </div>
                  {frList.map((fr, i) => (
                    <div key={i} className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-mono bg-muted px-2 py-1 rounded">{fr.requirementId}</span>
                      <Select
                        value={fr.priorityLevel}
                        onValueChange={(value) => {
                          const updated = [...frList];
                          updated[i].priorityLevel = value;
                          setFrList(updated);
                        }}
                      >
                        <SelectTrigger className="w-32 h-8 text-xs">
                          <SelectValue placeholder="Select Type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="MUST_HAVE">Must Have</SelectItem>
                          <SelectItem value="SHOULD_HAVE">Should Have</SelectItem>
                          <SelectItem value="COULD_HAVE">Could Have</SelectItem>
                          <SelectItem value="WONT_HAVE">Won't Have</SelectItem>
                        </SelectContent>
                      </Select>
                      <Input
                        value={fr.description}
                        onChange={(e) => {
                          const updated = [...frList];
                          updated[i].description = e.target.value;
                          setFrList(updated);
                        }}
                        placeholder="Describe the functional requirement..."
                        className="flex-1 h-8"
                      />
                    </div>
                  ))}
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium">Non-Functional Requirements</label>
                    <Button variant="outline" size="sm" onClick={() => setNfrList(prev => [...prev, { requirementId: `NFR-${String(prev.length + 1).padStart(3, '0')}`, priorityLevel: "", description: "" }])} className="h-7 text-xs">
                      <Plus className="h-3 w-3 mr-1" /> Add Requirement
                    </Button>
                  </div>
                  {nfrList.map((nfr, i) => (
                    <div key={i} className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-mono bg-muted px-2 py-1 rounded">{nfr.requirementId}</span>
                      <Select
                        value={nfr.priorityLevel}
                        onValueChange={(value) => {
                          const updated = [...nfrList];
                          updated[i].priorityLevel = value;
                          setNfrList(updated);
                        }}
                      >
                        <SelectTrigger className="w-32 h-8 text-xs">
                          <SelectValue placeholder="Select Type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="MUST_HAVE">Must Have</SelectItem>
                          <SelectItem value="SHOULD_HAVE">Should Have</SelectItem>
                          <SelectItem value="COULD_HAVE">Could Have</SelectItem>
                          <SelectItem value="WONT_HAVE">Won't Have</SelectItem>
                        </SelectContent>
                      </Select>
                      <Input
                        value={nfr.description}
                        onChange={(e) => {
                          const updated = [...nfrList];
                          updated[i].description = e.target.value;
                          setNfrList(updated);
                        }}
                        placeholder="Describe the non functional requirement..."
                        className="flex-1 h-8"
                      />
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="px-5 pt-4">
          <Card className="border-muted">
            <CardContent className="p-4">
              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium">Dependencies</label>
                  <Button variant="outline" size="sm" onClick={() => addListItem(setDepsList)} className="h-7 text-xs">
                    <Plus className="h-3 w-3 mr-1" /> Add Dependency
                  </Button>
                </div>
                {depsList.map((d, i) => (
                  <div key={i} className="flex items-center gap-2 mb-2">
                    <Input
                      value={d}
                      onChange={(e) => updateListItem(setDepsList, i, e.target.value)}
                      placeholder="e.g., Data Pipeline module"
                      className="flex-1"
                    />
                    {depsList.length > 1 && (
                      <Button variant="ghost" size="sm" onClick={() => removeListItem(setDepsList, i)} className="h-8 w-8 p-0">
                        <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                    Risks & Mitigation
                  </label>
                  <Button variant="outline" size="sm" onClick={() => setRisksList(prev => [...prev, { riskId: `R-${String(prev.length + 1).padStart(3, '0')}`, problemLevel: "", impactLevel: "", description: "", strategy: "" }])} className="h-7 text-xs">
                    <Plus className="h-3 w-3 mr-1" /> Add Risk
                  </Button>
                </div>
                {risksList.map((risk, i) => (
                  <div key={i} className="border rounded-lg p-3 mb-2">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-mono bg-muted px-2 py-1 rounded">{risk.riskId}</span>
                      <Select
                        value={risk.problemLevel}
                        onValueChange={(value) => {
                          const updated = [...risksList];
                          updated[i].problemLevel = value;
                          setRisksList(updated);
                        }}
                      >
                        <SelectTrigger className="w-40 h-8 text-xs">
                          <SelectValue placeholder="Select risk probability" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="HIGH">High</SelectItem>
                          <SelectItem value="MEDIUM">Medium</SelectItem>
                          <SelectItem value="LOW">Low</SelectItem>
                        </SelectContent>
                      </Select>
                      <Select
                        value={risk.impactLevel}
                        onValueChange={(value) => {
                          const updated = [...risksList];
                          updated[i].impactLevel = value;
                          setRisksList(updated);
                        }}
                      >
                        <SelectTrigger className="w-40 h-8 text-xs">
                          <SelectValue placeholder="Select risk impact" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="HIGH">High</SelectItem>
                          <SelectItem value="MEDIUM">Medium</SelectItem>
                          <SelectItem value="LOW">Low</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="mb-2">
                      <label className="text-xs text-muted-foreground mb-1 block">Risk Description</label>
                      <Input
                        value={risk.description}
                        onChange={(e) => {
                          const updated = [...risksList];
                          updated[i].description = e.target.value;
                          setRisksList(updated);
                        }}
                        placeholder="Describe the risk..."
                        className="h-8"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground mb-1 block">Mitigation Strategy</label>
                      <Input
                        value={risk.strategy}
                        onChange={(e) => {
                          const updated = [...risksList];
                          updated[i].strategy = e.target.value;
                          setRisksList(updated);
                        }}
                        placeholder="Describe the mitigation strategy..."
                        className="h-8"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
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

export default FeatureCreateInline;
