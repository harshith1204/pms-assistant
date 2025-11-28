import { useEffect, useState } from "react";
import { Bot, User, Copy, ThumbsUp, ThumbsDown } from "lucide-react";
import { cn } from "@/lib/utils";
import SafeMarkdown from "@/components/SafeMarkdown";
import { Button } from "@/components/ui/button";
import { AgentActivity } from "@/components/AgentActivity";
import { usePersonalization } from "@/context/PersonalizationContext";
import { type Project } from "@/api/projects";
import { DateRange } from "@/components/ui/date-range-picker";
import { SavedArtifactData } from "@/api/conversations";

interface ChatMessageProps {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  liked?: boolean;
  onLike?: (messageId: string) => void;
  onDislike?: (messageId: string) => void;
  onArtifactSaved?: (messageId: string, artifactType: string, savedData?: SavedArtifactData) => void;
  internalActivity?: {
    summary: string;
    bullets?: string[];
    doneLabel?: string;
    body?: string;
  };
  workItem?: {
    title: string;
    description?: string;
    projectIdentifier?: string;
    sequenceId?: string | number;
    link?: string;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  page?: {
    title: string;
    blocks: { blocks: unknown[] };
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  cycle?: {
    title: string;
    description?: string;
    startDate?: string;
    endDate?: string;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  module?: {
    title: string;
    description?: string;
    projectName?: string;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  epic?: {
    title: string;
    description?: string;
    priority?: string;
    state?: string;
    assignee?: string;
    labels?: string[];
    startDate?: string;
    dueDate?: string;
    link?: string;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  userStory?: {
    title: string;
    description?: string;
    persona?: string;
    userGoal?: string;
    demographics?: string;
    acceptanceCriteria?: string;
    priority?: string;
    state?: string;
    assignees?: string[];
    epicName?: string;
    featureName?: string;
    moduleName?: string;
    labels?: string[];
    startDate?: string;
    endDate?: string;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  feature?: {
    title: string;
    description?: string;
    problemStatement?: string;
    objective?: string;
    successCriteria?: string[];
    goals?: string[];
    painPoints?: string[];
    inScope?: string[];
    outOfScope?: string[];
    functionalRequirements?: { requirementId: string; priorityLevel: string; description: string }[];
    nonFunctionalRequirements?: { requirementId: string; priorityLevel: string; description: string }[];
    dependencies?: string[];
    risks?: { riskId: string; problemLevel: string; impactLevel: string; description: string; strategy: string }[];
    priority?: string;
    state?: string;
    epicName?: string;
    moduleName?: string;
    labels?: string[];
    startDate?: string;
    endDate?: string;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  project?: {
    name: string;
    projectId?: string;
    description?: string;
    imageUrl?: string;
    icon?: string;
    access?: "PUBLIC" | "PRIVATE";
    leadName?: string;
    isSaved?: boolean;
    savedData?: SavedArtifactData;
  };
  conversationId?: string;
}

import WorkItemCreateInline from "@/components/WorkItemCreateInline";
import WorkItemCard from "@/components/WorkItemCard";
import PageCreateInline from "@/components/PageCreateInline";
import PageCard from "@/components/PageCard";
import CycleCreateInline from "@/components/CycleCreateInline";
import CycleCard from "@/components/CycleCard";
import ModuleCreateInline from "@/components/ModuleCreateInline";
import ModuleCard from "@/components/ModuleCard";
import EpicCreateInline from "@/components/EpicCreateInline";
import EpicCard from "@/components/EpicCard";
import UserStoryCreateInline from "@/components/UserStoryCreateInline";
import UserStoryCard from "@/components/UserStoryCard";
import FeatureCreateInline from "@/components/FeatureCreateInline";
import FeatureCard from "@/components/FeatureCard";
import ProjectCreateInline from "@/components/ProjectCreateInline";
import ProjectCard from "@/components/ProjectCard";
import { createWorkItem, createWorkItemWithMembers } from "@/api/workitems";
import { createPage } from "@/api/pages";
import { createCycle } from "@/api/cycles";
import { createModule, createModuleWithMembers } from "@/api/modules";
import { createEpic, type Epic } from "@/api/epics";
import { createUserStory } from "@/api/userStories";
import { createFeature, type Feature } from "@/api/features";
import { createProject } from "@/api/projectCreate";
import { type ProjectMember } from "@/api/members";
import { type Cycle } from "@/api/cycles";
import { type SubState } from "@/api/substates";
import { type Module } from "@/api/modules";
import { type ProjectLabel } from "@/api/labels";
import { toast } from "@/components/ui/use-toast";
import { getBusinessId, getMemberId, getStaffName } from "@/config";
import { invalidateProjectCache } from "@/api/projectData";

export const ChatMessage = ({ id, role, content, isStreaming = false, liked, onLike, onDislike, onArtifactSaved, internalActivity, workItem, page, cycle, module, epic, userStory, feature, project, conversationId }: ChatMessageProps) => {
  const { settings } = usePersonalization();
  const [displayedContent, setDisplayedContent] = useState("");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [copied, setCopied] = useState(false);
  const canShowActions = role === "assistant" && !isStreaming && (displayedContent?.trim()?.length ?? 0) > 0;
  
  // Track whether each artifact has been saved (initially from props, then from local save actions)
  const [isWorkItemSaved, setIsWorkItemSaved] = useState(workItem?.isSaved ?? false);
  const [isPageSaved, setIsPageSaved] = useState(page?.isSaved ?? false);
  const [isCycleSaved, setIsCycleSaved] = useState(cycle?.isSaved ?? false);
  const [isModuleSaved, setIsModuleSaved] = useState(module?.isSaved ?? false);
  const [isEpicSaved, setIsEpicSaved] = useState(epic?.isSaved ?? false);
  const [isUserStorySaved, setIsUserStorySaved] = useState(userStory?.isSaved ?? false);
  const [isFeatureSaved, setIsFeatureSaved] = useState(feature?.isSaved ?? false);
  const [isProjectSaved, setIsProjectSaved] = useState(project?.isSaved ?? false);
  
  // Store saved data for display (link, etc.)
  const [savedWorkItemData, setSavedWorkItemData] = useState<SavedArtifactData | null>(workItem?.savedData ?? null);
  const [savedPageData, setSavedPageData] = useState<SavedArtifactData | null>(page?.savedData ?? null);
  const [savedCycleData, setSavedCycleData] = useState<SavedArtifactData | null>(cycle?.savedData ?? null);
  const [savedModuleData, setSavedModuleData] = useState<SavedArtifactData | null>(module?.savedData ?? null);
  const [savedEpicData, setSavedEpicData] = useState<SavedArtifactData | null>(epic?.savedData ?? null);
  const [savedUserStoryData, setSavedUserStoryData] = useState<SavedArtifactData | null>(userStory?.savedData ?? null);
  const [savedFeatureData, setSavedFeatureData] = useState<SavedArtifactData | null>(feature?.savedData ?? null);
  const [savedProjectData, setSavedProjectData] = useState<SavedArtifactData | null>(project?.savedData ?? null);
  
  const [saving, setSaving] = useState(false);

  // Module sub-state selection state
  const [selectedModuleSubState, setSelectedModuleSubState] = useState<SubState | null>(null);

  // Cycle selection state
  const [selectedCycle, setSelectedCycle] = useState<Cycle | null>(null);

  // Project selection state
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);

  // Member selection state
  const [selectedAssignees, setSelectedAssignees] = useState<ProjectMember[]>([]);
  const [selectedLead, setSelectedLead] = useState<ProjectMember | null>(null);
  const [selectedMembers, setSelectedMembers] = useState<ProjectMember[]>([]);

  // Date range selection state
  const [selectedDateRange, setSelectedDateRange] = useState<DateRange | undefined>();

  // Epic-specific selection state
  const [selectedEpicPriority, setSelectedEpicPriority] = useState<string | null>(epic?.priority ?? null);
  const [selectedEpicState, setSelectedEpicState] = useState<string | null>(epic?.state ?? null);
  const [selectedEpicAssignee, setSelectedEpicAssignee] = useState<ProjectMember | null>(null);
  const [selectedEpicLabels, setSelectedEpicLabels] = useState<ProjectLabel[]>([]);
  const [selectedEpicDateRange, setSelectedEpicDateRange] = useState<DateRange | undefined>(
    epic?.startDate || epic?.dueDate
      ? {
          from: epic?.startDate ? new Date(epic.startDate) : undefined,
          to: epic?.dueDate ? new Date(epic.dueDate) : undefined,
        }
      : undefined
  );

  useEffect(() => {
    if (epic && !savedEpic) {
      setSelectedEpicPriority(epic.priority ?? null);
      setSelectedEpicState(epic.state ?? null);
      setSelectedEpicAssignee(null);
      setSelectedEpicLabels([]);
      setSelectedEpicDateRange(
        epic.startDate || epic.dueDate
          ? {
              from: epic.startDate ? new Date(epic.startDate) : undefined,
              to: epic.dueDate ? new Date(epic.dueDate) : undefined,
            }
          : undefined
      );
    }
  }, [epic, savedEpic]);

  // Sub-state selection state
  const [selectedSubState, setSelectedSubState] = useState<SubState | null>(null);

  // Module selection state
  const [selectedModule, setSelectedModule] = useState<Module | null>(null);

  // User Story selection state
  const [selectedUserStoryEpic, setSelectedUserStoryEpic] = useState<Epic | null>(null);
  const [selectedUserStoryFeature, setSelectedUserStoryFeature] = useState<Feature | null>(null);
  const [selectedUserStoryDateRange, setSelectedUserStoryDateRange] = useState<DateRange | undefined>(
    userStory?.startDate || userStory?.endDate
      ? {
          from: userStory?.startDate ? new Date(userStory.startDate) : undefined,
          to: userStory?.endDate ? new Date(userStory.endDate) : undefined,
        }
      : undefined
  );
  const [selectedUserStoryAssignees, setSelectedUserStoryAssignees] = useState<ProjectMember[]>([]);
  const [selectedUserStoryLabels, setSelectedUserStoryLabels] = useState<ProjectLabel[]>([]);
  const [selectedUserStorySubState, setSelectedUserStorySubState] = useState<SubState | null>(null);
  const [selectedUserStoryModule, setSelectedUserStoryModule] = useState<Module | null>(null);
  const [selectedUserStoryProject, setSelectedUserStoryProject] = useState<Project | null>(null);

  // Feature selection state
  const [selectedFeatureEpic, setSelectedFeatureEpic] = useState<Epic | null>(null);
  const [selectedFeatureDateRange, setSelectedFeatureDateRange] = useState<DateRange | undefined>(
    feature?.startDate || feature?.endDate
      ? {
          from: feature?.startDate ? new Date(feature.startDate) : undefined,
          to: feature?.endDate ? new Date(feature.endDate) : undefined,
        }
      : undefined
  );
  const [selectedFeatureAssignees, setSelectedFeatureAssignees] = useState<ProjectMember[]>([]);
  const [selectedFeatureLabels, setSelectedFeatureLabels] = useState<ProjectLabel[]>([]);
  const [selectedFeatureSubState, setSelectedFeatureSubState] = useState<SubState | null>(null);
  const [selectedFeatureModule, setSelectedFeatureModule] = useState<Module | null>(null);
  const [selectedFeatureProject, setSelectedFeatureProject] = useState<Project | null>(null);

  useEffect(() => {
    if (role === "assistant" && isStreaming) {
      if (currentIndex < content.length) {
        const timeout = setTimeout(() => {
          setDisplayedContent(content.slice(0, currentIndex + 1));
          setCurrentIndex(currentIndex + 1);
        }, 20);
        return () => clearTimeout(timeout);
      }
    } else {
      setDisplayedContent(content);
    }
  }, [content, currentIndex, role, isStreaming]);

  const isUser = role === "user";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      // Failed to copy text
    }
  };

  const handleThumbsUp = () => {
    if (isStreaming) return;
    onLike?.(id);
  };

  const handleThumbsDown = () => {
    if (isStreaming) return;
    onDislike?.(id);
  };

  const isLiked = liked === true;
  const isDisliked = liked === false;

  return (
    <div className="p-3 animate-fade-in">
      {isUser ? (
        <div className="flex gap-4 flex-row-reverse">
          <div className="flex-1 text-right">
            <div className="flex justify-end">
              <div className="inline-block max-w-[80%] md:px-5 px-2 py-2 rounded-lg text-sm text-foreground leading-relaxed whitespace-pre-wrap bg-primary/10  text-right">
                {displayedContent}
                {isStreaming && currentIndex < content.length && (
                  <span className="inline-block w-1 h-4 ml-1 bg-primary animate-pulse" />
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {settings.showAgentInternals && internalActivity && (
            <AgentActivity
              summary={internalActivity.summary}
              bullets={internalActivity.bullets}
              doneLabel={internalActivity.doneLabel}
              body={internalActivity.body}
              defaultOpen={isStreaming}
              isStreaming={isStreaming}
            />
          )}

          {workItem ? (
              <WorkItemCreateInline
                title={workItem.title}
                description={workItem.description}
                selectedProject={selectedProject}
                selectedAssignees={selectedAssignees}
                selectedDateRange={selectedDateRange}
                selectedCycle={selectedCycle}
                selectedSubState={selectedSubState}
                selectedModule={selectedModule}
                onProjectSelect={setSelectedProject}
                onAssigneesSelect={setSelectedAssignees}
                onDateSelect={setSelectedDateRange}
                onCycleSelect={setSelectedCycle}
                onSubStateSelect={setSelectedSubState}
                onModuleSelect={setSelectedModule}
                isSaved={isWorkItemSaved}
                savedData={savedWorkItemData}
                onSave={async ({ title, description, project, assignees, cycle, subState, module, startDate, endDate, labels }) => {
                  if (isWorkItemSaved) return; // Already saved
                  try {
                    setSaving(true);
                    const businessId = getBusinessId();
                    const memberId = getMemberId();
                    const created = await createWorkItemWithMembers({
                      title,
                      description,
                      projectId: project?.projectId,
                      projectIdentifier: workItem.projectIdentifier,
                      cycleId: cycle?.id,
                      cycleTitle: cycle?.title,
                      subStateId: subState?.id,
                      subStateTitle: subState?.name,
                      moduleId: module?.id,
                      moduleTitle: module?.title,
                      assignees: assignees?.map(a => ({ id: a.id, name: a.displayName || a.name })),
                      labels: labels?.map(l => ({
                        id: l.id,
                        name: l.label,
                        color: l.color
                      })) || [],
                      startDate,
                      endDate,
                      createdBy: { id: memberId, name: "" }
                    });
                    
                    // Mark as saved locally
                    setIsWorkItemSaved(true);
                    setSavedWorkItemData(created);
                    
                    // Notify parent to persist saved state in conversation
                    onArtifactSaved?.(id, 'work_item', created);

                    // Invalidate cache for the project since new data was created
                    if (project?.projectId) {
                      invalidateProjectCache(project.projectId);
                    }

                    toast({ title: "Work item saved", description: "Your work item has been created.", duration: 3000  });
                  } catch (e: any) {
                    toast({ title: "Failed to save work item", description: String(e?.message || e), variant: "destructive" as any });
                  } finally {
                    setSaving(false);
                  }
                }}
                onDiscard={() => { /* no-op for now */ }}
                className="mt-1"
                conversationId={conversationId}
                onProjectDataLoaded={(message) => {
                  // Send the project data loaded message via WebSocket
                  if (conversationId && (window as any).chatSocket) {
                    (window as any).chatSocket.send({
                      message: message,
                      conversation_id: conversationId,
                    });
                  }
                }}
              />
          ) : page ? (
              <PageCreateInline
                initialEditorJs={page.blocks}
                selectedProject={selectedProject}
                onProjectSelect={setSelectedProject}
                isSaved={isPageSaved}
                savedData={savedPageData}
                onSave={async ({ title, editorJs, project }) => {
                  if (isPageSaved) return; // Already saved
                  try {
                    setSaving(true);
                    const businessId = getBusinessId();
                    const memberId = getMemberId();
                    const created = await createPage({
                      title: title || "Untitled Page",
                      content: editorJs,
                      projectId: project?.projectId,
                      createdBy: { id: memberId, name: "" }
                    });
                    
                    // Mark as saved locally
                    setIsPageSaved(true);
                    setSavedPageData(created);
                    
                    // Notify parent to persist saved state in conversation
                    onArtifactSaved?.(id, 'page', created);

                    // Invalidate cache for the project since new data was created
                    if (project?.projectId) {
                      invalidateProjectCache(project.projectId);
                    }

                    toast({ title: "Page saved", description: "Your page has been created." });
                  } catch (e: any) {
                    toast({ title: "Failed to save page", description: String(e?.message || e), variant: "destructive" as any });
                  } finally {
                    setSaving(false);
                  }
                }}
                onDiscard={() => { /* no-op for now */ }}
                className="mt-1"
              />
          ) : cycle ? (
              <CycleCreateInline
                title={cycle.title}
                description={cycle.description}
                selectedProject={selectedProject}
                selectedDateRange={selectedDateRange}
                onProjectSelect={setSelectedProject}
                onDateSelect={setSelectedDateRange}
                isSaved={isCycleSaved}
                savedData={savedCycleData}
                onSave={async ({ title, description, project, startDate, endDate }) => {
                  if (isCycleSaved) return; // Already saved
                  try {
                    setSaving(true);
                    const created = await createCycle({
                      title,
                      description,
                      projectId: project?.projectId,
                      startDate: startDate || cycle.startDate,
                      endDate: endDate || cycle.endDate
                    });
                    
                    // Mark as saved locally
                    setIsCycleSaved(true);
                    setSavedCycleData(created);
                    
                    // Notify parent to persist saved state in conversation
                    onArtifactSaved?.(id, 'cycle', created);

                    // Invalidate cache for the project since new data was created
                    if (project?.projectId) {
                      invalidateProjectCache(project.projectId);
                    }

                    toast({ title: "Cycle saved", description: "Your cycle has been created.", duration: 3000  });
                  } catch (e: any) {
                    toast({ title: "Failed to save cycle", description: String(e?.message || e), variant: "destructive" as any });
                  } finally {
                    setSaving(false);
                  }
                }}
                onDiscard={() => { /* no-op for now */ }}
                className="mt-1"
                conversationId={conversationId}
                onProjectDataLoaded={(message) => {
                  // Send the project data loaded message via WebSocket
                  if (conversationId && (window as any).chatSocket) {
                    (window as any).chatSocket.send({
                      message: message,
                      conversation_id: conversationId,
                    });
                  }
                }}
              />
          ) : module ? (
              <ModuleCreateInline
                title={module.title}
                description={module.description}
                selectedProject={selectedProject}
                selectedLead={selectedLead}
                selectedMembers={selectedMembers}
                selectedDateRange={selectedDateRange}
                selectedSubState={selectedModuleSubState}
                onProjectSelect={setSelectedProject}
                onLeadSelect={setSelectedLead}
                onMembersSelect={setSelectedMembers}
                onDateSelect={setSelectedDateRange}
                onSubStateSelect={setSelectedModuleSubState}
                isSaved={isModuleSaved}
                savedData={savedModuleData}
                onSave={async ({ title, description, project, lead, members, subState, startDate, endDate }) => {
                  if (isModuleSaved) return; // Already saved
                  try {
                    setSaving(true);
                    const created = await createModuleWithMembers({
                      title,
                      description,
                      projectId: project?.projectId,
                      subStateId: subState?.id,
                      subStateTitle: subState?.name,
                      lead: { id: lead.id, name: lead.displayName || lead.name },
                      members: members?.map(m => ({ id: m.id, name: m.displayName || m.name })),
                      startDate,
                      endDate
                    });
                    
                    // Mark as saved locally
                    setIsModuleSaved(true);
                    setSavedModuleData(created);
                    
                    // Notify parent to persist saved state in conversation
                    onArtifactSaved?.(id, 'module', created);

                    // Invalidate cache for the project since new data was created
                    if (project?.projectId) {
                      invalidateProjectCache(project.projectId);
                    }

                    toast({ title: "Module saved", description: "Your module has been created.", duration: 3000  });
                  } catch (e: any) {
                    toast({ title: "Failed to save module", description: String(e?.message || e), variant: "destructive" as any });
                  } finally {
                    setSaving(false);
                  }
                }}
                onDiscard={() => { /* no-op for now */ }}
                className="mt-1"
                conversationId={conversationId}
                onProjectDataLoaded={(message) => {
                  // Send the project data loaded message via WebSocket
                  if (conversationId && (window as any).chatSocket) {
                    (window as any).chatSocket.send({
                      message: message,
                      conversation_id: conversationId,
                    });
                  }
                }}
              />
          ) : epic ? (
              <EpicCreateInline
                title={epic.title}
                description={epic.description}
                selectedProject={selectedProject}
                selectedPriority={selectedEpicPriority}
                selectedState={selectedEpicState}
                selectedAssignee={selectedEpicAssignee}
                selectedLabels={selectedEpicLabels}
                selectedDateRange={selectedEpicDateRange}
                onProjectSelect={setSelectedProject}
                onPrioritySelect={setSelectedEpicPriority}
                onStateSelect={setSelectedEpicState}
                onAssigneeSelect={setSelectedEpicAssignee}
                onLabelsSelect={setSelectedEpicLabels}
                onDateSelect={setSelectedEpicDateRange}
                isSaved={isEpicSaved}
                savedData={savedEpicData}
                onSave={async ({ title, description, project, priority, state, assignee, labels, startDate, dueDate }) => {
                  if (isEpicSaved) return; // Already saved
                  try {
                    setSaving(true);
                    const labelNames = labels?.map((label) => label.label).filter(Boolean) ?? [];
                    const created = await createEpic({
                      title,
                      description,
                      projectId: project?.projectId,
                      priority: priority ?? undefined,
                      stateName: state ?? undefined,
                      assigneeName: assignee ? (assignee.displayName || assignee.name) : undefined,
                      labels: labelNames.length ? labelNames : undefined,
                      startDate,
                      dueDate,
                      createdBy: getMemberId(),
                    });

                    const savedData = {
                      id: created.id,
                      title: created.title,
                      description: created.description,
                      priority: priority ?? created.priority ?? null,
                      state: state ?? created.state ?? null,
                      assignee: assignee ? assignee.displayName || assignee.name : null,
                      labels: labelNames,
                      link: created.link ?? null,
                    };
                    
                    // Mark as saved locally
                    setIsEpicSaved(true);
                    setSavedEpicData(savedData);
                    
                    // Notify parent to persist saved state in conversation
                    onArtifactSaved?.(id, 'epic', savedData);

                    if (project?.projectId) {
                      invalidateProjectCache(project.projectId);
                    }

                    toast({ title: "Epic saved", description: "Your epic has been created." });
                  } catch (e: any) {
                    toast({ title: "Failed to save epic", description: String(e?.message || e), variant: "destructive" as any });
                  } finally {
                    setSaving(false);
                  }
                }}
                onDiscard={() => { /* no-op for now */ }}
                className="mt-1"
                conversationId={conversationId}
                onProjectDataLoaded={(message) => {
                  if (conversationId && (window as any).chatSocket) {
                    (window as any).chatSocket.send({
                      message: message,
                      conversation_id: conversationId,
                    });
                  }
                }}
              />
          ) : userStory ? (
              <UserStoryCreateInline
                title={userStory.title}
                description={userStory.description}
                persona={userStory.persona}
                userGoal={userStory.userGoal}
                demographics={userStory.demographics}
                acceptanceCriteria={userStory.acceptanceCriteria}
                selectedProject={selectedUserStoryProject}
                selectedAssignees={selectedUserStoryAssignees}
                selectedLabels={selectedUserStoryLabels}
                selectedDateRange={selectedUserStoryDateRange}
                selectedSubState={selectedUserStorySubState}
                selectedModule={selectedUserStoryModule}
                selectedEpic={selectedUserStoryEpic}
                selectedFeature={selectedUserStoryFeature}
                onProjectSelect={setSelectedUserStoryProject}
                onAssigneesSelect={setSelectedUserStoryAssignees}
                onLabelsSelect={setSelectedUserStoryLabels}
                onDateSelect={setSelectedUserStoryDateRange}
                onSubStateSelect={setSelectedUserStorySubState}
                onModuleSelect={setSelectedUserStoryModule}
                onEpicSelect={setSelectedUserStoryEpic}
                onFeatureSelect={setSelectedUserStoryFeature}
                isSaved={isUserStorySaved}
                savedData={savedUserStoryData}
                onSave={async ({ title, description, persona, userGoal, demographics, acceptanceCriteria, project, assignees, labels, subState, module: mod, epic: ep, feature: feat, startDate, endDate }) => {
                  if (isUserStorySaved) return; // Already saved
                  try {
                    setSaving(true);
                    const created = await createUserStory({
                      title,
                      description,
                      projectId: project?.projectId,
                      projectName: project?.projectName,
                      userGoal,
                      persona,
                      demographics,
                      acceptanceCriteria,
                      stateId: subState?.id,
                      stateName: subState?.name,
                      assignees: assignees?.map(a => ({ id: a.id, name: a.displayName || a.name })),
                      labels: labels?.map(l => ({ id: l.id, name: l.label, color: l.color })),
                      epicId: ep?.id,
                      epicName: ep?.title,
                      featureId: feat?.id,
                      featureName: feat?.basicInfo?.title || feat?.title,
                      moduleId: mod?.id,
                      moduleName: mod?.title,
                      startDate,
                      endDate,
                      createdBy: { id: getMemberId(), name: getStaffName() }
                    });

                    const savedData = {
                      id: created.id,
                      title: created.title,
                      description: created.description,
                      displayBugNo: created.displayBugNo,
                      link: created.link
                    };
                    
                    // Mark as saved locally
                    setIsUserStorySaved(true);
                    setSavedUserStoryData(savedData);
                    
                    // Notify parent to persist saved state in conversation
                    onArtifactSaved?.(id, 'user_story', savedData);

                    if (project?.projectId) {
                      invalidateProjectCache(project.projectId);
                    }

                    toast({ title: "User Story saved", description: "Your user story has been created." });
                  } catch (e: any) {
                    toast({ title: "Failed to save user story", description: String(e?.message || e), variant: "destructive" as any });
                  } finally {
                    setSaving(false);
                  }
                }}
                onDiscard={() => { /* no-op for now */ }}
                className="mt-1"
                conversationId={conversationId}
                onProjectDataLoaded={(message) => {
                  if (conversationId && (window as any).chatSocket) {
                    (window as any).chatSocket.send({
                      message: message,
                      conversation_id: conversationId,
                    });
                  }
                }}
              />
          ) : feature ? (
              <FeatureCreateInline
                title={feature.title}
                description={feature.description}
                problemStatement={feature.problemStatement}
                objective={feature.objective}
                successCriteria={feature.successCriteria}
                goals={feature.goals}
                painPoints={feature.painPoints}
                inScope={feature.inScope}
                outOfScope={feature.outOfScope}
                functionalRequirements={feature.functionalRequirements}
                nonFunctionalRequirements={feature.nonFunctionalRequirements}
                dependencies={feature.dependencies}
                risks={feature.risks}
                selectedProject={selectedFeatureProject}
                selectedAssignees={selectedFeatureAssignees}
                selectedLabels={selectedFeatureLabels}
                selectedDateRange={selectedFeatureDateRange}
                selectedSubState={selectedFeatureSubState}
                selectedModule={selectedFeatureModule}
                selectedEpic={selectedFeatureEpic}
                onProjectSelect={setSelectedFeatureProject}
                onAssigneesSelect={setSelectedFeatureAssignees}
                onLabelsSelect={setSelectedFeatureLabels}
                onDateSelect={setSelectedFeatureDateRange}
                onSubStateSelect={setSelectedFeatureSubState}
                onModuleSelect={setSelectedFeatureModule}
                onEpicSelect={setSelectedFeatureEpic}
                isSaved={isFeatureSaved}
                savedData={savedFeatureData}
                onSave={async ({ title, description, problemStatement, objective, successCriteria, goals, painPoints, inScope, outOfScope, functionalRequirements, nonFunctionalRequirements, dependencies, risks, project, assignees, labels, subState, module: mod, epic: ep, startDate, endDate }) => {
                  if (isFeatureSaved) return; // Already saved
                  try {
                    setSaving(true);
                    const created = await createFeature({
                      title,
                      description,
                      projectId: project?.projectId,
                      projectName: project?.projectName,
                      problemStatement,
                      objective,
                      successCriteria,
                      goals,
                      painPoints,
                      inScope,
                      outOfScope,
                      functionalRequirements,
                      nonFunctionalRequirements,
                      dependencies,
                      risks,
                      stateId: subState?.id,
                      stateName: subState?.name,
                      assignees: assignees?.map(a => ({ id: a.id, name: a.displayName || a.name })),
                      labels: labels?.map(l => ({ id: l.id, name: l.label, color: l.color })),
                      epicId: ep?.id,
                      epicName: ep?.title,
                      moduleId: mod?.id,
                      moduleName: mod?.title,
                      startDate,
                      endDate,
                      createdBy: { id: getMemberId(), name: getStaffName() }
                    });

                    const savedData = {
                      id: created.id,
                      title: created.title,
                      description: created.description,
                      displayBugNo: created.displayBugNo,
                      link: created.link
                    };
                    
                    // Mark as saved locally
                    setIsFeatureSaved(true);
                    setSavedFeatureData(savedData);
                    
                    // Notify parent to persist saved state in conversation
                    onArtifactSaved?.(id, 'feature', savedData);

                    if (project?.projectId) {
                      invalidateProjectCache(project.projectId);
                    }

                    toast({ title: "Feature saved", description: "Your feature has been created." });
                  } catch (e: any) {
                    toast({ title: "Failed to save feature", description: String(e?.message || e), variant: "destructive" as any });
                  } finally {
                    setSaving(false);
                  }
                }}
                onDiscard={() => { /* no-op for now */ }}
                className="mt-1"
                conversationId={conversationId}
                onProjectDataLoaded={(message) => {
                  if (conversationId && (window as any).chatSocket) {
                    (window as any).chatSocket.send({
                      message: message,
                      conversation_id: conversationId,
                    });
                  }
                }}
              />
          ) : project ? (
              <ProjectCreateInline
                name={project.name}
                projectId={project.projectId}
                description={project.description}
                imageUrl={project.imageUrl}
                icon={project.icon}
                access={project.access}
                leadName={project.leadName}
                isSaved={isProjectSaved}
                savedData={savedProjectData}
                onSave={async ({ name, projectId, description, imageUrl, icon, access, leadId, leadName }) => {
                  if (isProjectSaved) return; // Already saved
                  try {
                    setSaving(true);
                    const created = await createProject({
                      name,
                      projectId,
                      description,
                      imageUrl,
                      icon,
                      access,
                      leadId,
                      leadName,
                      createdBy: { id: getMemberId(), name: getStaffName() }
                    });

                    const savedData = {
                      id: created.id,
                      projectDisplayId: created.projectDisplayId,
                      name: created.name,
                      description: created.description,
                      imageUrl: created.imageUrl,
                      icon: created.icon,
                      access: created.access,
                      link: created.link
                    };
                    
                    // Mark as saved locally
                    setIsProjectSaved(true);
                    setSavedProjectData(savedData);
                    
                    // Notify parent to persist saved state in conversation
                    onArtifactSaved?.(id, 'project', savedData);

                    toast({ title: "Project saved", description: "Your project has been created." });
                  } catch (e: any) {
                    toast({ title: "Failed to save project", description: String(e?.message || e), variant: "destructive" as any });
                  } finally {
                    setSaving(false);
                  }
                }}
                onDiscard={() => { /* no-op for now */ }}
                className="mt-1"
              />
          ) : (
            <SafeMarkdown
              content={displayedContent}
              className="prose prose-sm max-w-none dark:prose-invert prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground prose-li:text-foreground"
            />
          )}
          {isStreaming && currentIndex < content.length && (
            <span className="inline-block w-1 h-4 ml-1 bg-primary animate-pulse" />
          )}

          {/* Action buttons for assistant messages */}
          {canShowActions && (
            <div className="flex items-center gap-1 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCopy}
                className={cn(
                  "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-primary/10 transition-all duration-200 rounded-md",
                  copied && "text-green-600 bg-green-600/10"
                )}
              >
                <Copy className="h-4 w-4" />
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleThumbsUp}
                className={cn(
                  "h-8 px-2 transition-all duration-200 rounded-md",
                  isLiked
                    ? "text-green-600 hover:text-green-700 bg-green-600/10"
                    : "text-muted-foreground hover:text-foreground hover:bg-primary/10"
                )}
              >
                <ThumbsUp className={cn("h-4 w-4", isLiked && "fill-current")} />
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleThumbsDown}
                className={cn(
                  "h-8 px-2 transition-all duration-200 rounded-md",
                  isDisliked
                    ? "text-red-600 hover:text-red-700 bg-red-600/10"
                    : "text-muted-foreground hover:text-foreground hover:bg-primary/10"
                )}
              >
                <ThumbsDown className={cn("h-4 w-4", isDisliked && "fill-current")} />
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
