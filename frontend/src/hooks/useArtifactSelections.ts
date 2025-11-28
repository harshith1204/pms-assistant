import { useState } from "react";
import { SavedArtifactData } from "@/api/conversations";
import { Project } from "@/api/projects";
import { ProjectMember } from "@/api/members";
import { ProjectLabel } from "@/api/labels";
import { Cycle } from "@/api/cycles";
import { SubState } from "@/api/substates";
import { Module } from "@/api/modules";
import { Epic } from "@/api/epics";
import { Feature } from "@/api/features";
import { DateRange } from "@/components/ui/date-range-picker";

// Types for the selected values
export interface ArtifactSelections {
  selectedProject: Project | null;
  selectedAssignees: ProjectMember[];
  selectedLead: ProjectMember | null;
  selectedMembers: ProjectMember[];
  selectedDateRange: DateRange | undefined;
  selectedCycle: Cycle | null;
  selectedSubState: SubState | null;
  selectedModule: Module | null;
  selectedModuleSubState: SubState | null;
  selectedEpicPriority: string | null;
  selectedEpicState: string | null;
  selectedEpicAssignee: ProjectMember | null;
  selectedEpicLabels: ProjectLabel[];
  selectedEpicDateRange: DateRange | undefined;
  selectedUserStoryEpic: Epic | null;
  selectedUserStoryFeature: Feature | null;
  selectedUserStoryDateRange: DateRange | undefined;
  selectedUserStoryAssignees: ProjectMember[];
  selectedUserStoryLabels: ProjectLabel[];
  selectedUserStorySubState: SubState | null;
  selectedUserStoryModule: Module | null;
  selectedUserStoryProject: Project | null;
  selectedFeatureEpic: Epic | null;
  selectedFeatureDateRange: DateRange | undefined;
  selectedFeatureAssignees: ProjectMember[];
  selectedFeatureLabels: ProjectLabel[];
  selectedFeatureSubState: SubState | null;
  selectedFeatureModule: Module | null;
  selectedFeatureProject: Project | null;
}

// Props interface for the hook
export interface UseArtifactSelectionsProps {
  workItem?: {
    savedData?: SavedArtifactData;
  };
  page?: {
    savedData?: SavedArtifactData;
  };
  cycle?: {
    title?: string;
    description?: string;
    startDate?: string;
    endDate?: string;
    savedData?: SavedArtifactData;
  };
  module?: {
    savedData?: SavedArtifactData;
  };
  epic?: {
    priority?: string;
    state?: string;
    startDate?: string;
    dueDate?: string;
    savedData?: SavedArtifactData;
  };
  userStory?: {
    startDate?: string;
    endDate?: string;
    savedData?: SavedArtifactData;
  };
  feature?: {
    startDate?: string;
    endDate?: string;
    savedData?: SavedArtifactData;
  };
  project?: {
    savedData?: SavedArtifactData;
  };
}

// Helper function to extract selected values from savedData
const extractSelectedValues = (savedData: SavedArtifactData | null): ArtifactSelections => {
  const selectedValues = savedData?.selectedValues as any;
  return {
    selectedProject: selectedValues?.selectedProject || null,
    selectedAssignees: selectedValues?.selectedAssignees || [],
    selectedLead: selectedValues?.selectedLead || null,
    selectedMembers: selectedValues?.selectedMembers || [],
    selectedDateRange: selectedValues?.selectedDateRange || undefined,
    selectedCycle: selectedValues?.selectedCycle || null,
    selectedSubState: selectedValues?.selectedSubState || null,
    selectedModule: selectedValues?.selectedModule || null,
    selectedModuleSubState: selectedValues?.selectedModuleSubState || null,
    selectedEpicPriority: selectedValues?.selectedEpicPriority || null,
    selectedEpicState: selectedValues?.selectedEpicState || null,
    selectedEpicAssignee: selectedValues?.selectedEpicAssignee || null,
    selectedEpicLabels: selectedValues?.selectedEpicLabels || [],
    selectedEpicDateRange: selectedValues?.selectedEpicDateRange || undefined,
    selectedUserStoryEpic: selectedValues?.selectedUserStoryEpic || null,
    selectedUserStoryFeature: selectedValues?.selectedUserStoryFeature || null,
    selectedUserStoryDateRange: selectedValues?.selectedUserStoryDateRange || undefined,
    selectedUserStoryAssignees: selectedValues?.selectedUserStoryAssignees || [],
    selectedUserStoryLabels: selectedValues?.selectedUserStoryLabels || [],
    selectedUserStorySubState: selectedValues?.selectedUserStorySubState || null,
    selectedUserStoryModule: selectedValues?.selectedUserStoryModule || null,
    selectedUserStoryProject: selectedValues?.selectedUserStoryProject || null,
    selectedFeatureEpic: selectedValues?.selectedFeatureEpic || null,
    selectedFeatureDateRange: selectedValues?.selectedFeatureDateRange || undefined,
    selectedFeatureAssignees: selectedValues?.selectedFeatureAssignees || [],
    selectedFeatureLabels: selectedValues?.selectedFeatureLabels || [],
    selectedFeatureSubState: selectedValues?.selectedFeatureSubState || null,
    selectedFeatureModule: selectedValues?.selectedFeatureModule || null,
    selectedFeatureProject: selectedValues?.selectedFeatureProject || null,
  };
};

// Hook for managing artifact selections
export const useArtifactSelections = (props: UseArtifactSelectionsProps) => {
  const { workItem, page, cycle, module, epic, userStory, feature, project } = props;

  // Get saved selected values from the appropriate artifact's savedData
  const getSavedSelectedValues = (): ArtifactSelections => {
    if (workItem?.savedData) return extractSelectedValues(workItem.savedData);
    if (page?.savedData) return extractSelectedValues(page.savedData);
    if (cycle?.savedData) return extractSelectedValues(cycle.savedData);
    if (module?.savedData) return extractSelectedValues(module.savedData);
    if (epic?.savedData) return extractSelectedValues(epic.savedData);
    if (userStory?.savedData) return extractSelectedValues(userStory.savedData);
    if (feature?.savedData) return extractSelectedValues(feature.savedData);
    if (project?.savedData) return extractSelectedValues(project.savedData);
    return extractSelectedValues(null);
  };

  const savedSelectedValues = getSavedSelectedValues();

  // Module sub-state selection state
  const [selectedModuleSubState, setSelectedModuleSubState] = useState<SubState | null>(savedSelectedValues.selectedModuleSubState);

  // Cycle selection state
  const [selectedCycle, setSelectedCycle] = useState<Cycle | null>(savedSelectedValues.selectedCycle);

  // Project selection state
  const [selectedProject, setSelectedProject] = useState<Project | null>(savedSelectedValues.selectedProject);

  // Member selection state
  const [selectedAssignees, setSelectedAssignees] = useState<ProjectMember[]>(savedSelectedValues.selectedAssignees);
  const [selectedLead, setSelectedLead] = useState<ProjectMember | null>(savedSelectedValues.selectedLead);
  const [selectedMembers, setSelectedMembers] = useState<ProjectMember[]>(savedSelectedValues.selectedMembers);

  // Date range selection state
  const [selectedDateRange, setSelectedDateRange] = useState<DateRange | undefined>(savedSelectedValues.selectedDateRange);

  // Epic-specific selection state
  const [selectedEpicPriority, setSelectedEpicPriority] = useState<string | null>(epic?.priority ?? savedSelectedValues.selectedEpicPriority);
  const [selectedEpicState, setSelectedEpicState] = useState<string | null>(epic?.state ?? savedSelectedValues.selectedEpicState);
  const [selectedEpicAssignee, setSelectedEpicAssignee] = useState<ProjectMember | null>(savedSelectedValues.selectedEpicAssignee);
  const [selectedEpicLabels, setSelectedEpicLabels] = useState<ProjectLabel[]>(savedSelectedValues.selectedEpicLabels);
  const [selectedEpicDateRange, setSelectedEpicDateRange] = useState<DateRange | undefined>(
    epic?.startDate || epic?.dueDate
      ? {
          from: epic?.startDate ? new Date(epic.startDate) : undefined,
          to: epic?.dueDate ? new Date(epic.dueDate) : undefined,
        }
      : savedSelectedValues.selectedEpicDateRange
  );

  // Sub-state selection state
  const [selectedSubState, setSelectedSubState] = useState<SubState | null>(savedSelectedValues.selectedSubState);

  // Module selection state
  const [selectedModule, setSelectedModule] = useState<Module | null>(savedSelectedValues.selectedModule);

  // User Story selection state
  const [selectedUserStoryEpic, setSelectedUserStoryEpic] = useState<Epic | null>(savedSelectedValues.selectedUserStoryEpic);
  const [selectedUserStoryFeature, setSelectedUserStoryFeature] = useState<Feature | null>(savedSelectedValues.selectedUserStoryFeature);
  const [selectedUserStoryDateRange, setSelectedUserStoryDateRange] = useState<DateRange | undefined>(
    userStory?.startDate || userStory?.endDate
      ? {
          from: userStory?.startDate ? new Date(userStory.startDate) : undefined,
          to: userStory?.endDate ? new Date(userStory.endDate) : undefined,
        }
      : savedSelectedValues.selectedUserStoryDateRange
  );
  const [selectedUserStoryAssignees, setSelectedUserStoryAssignees] = useState<ProjectMember[]>(savedSelectedValues.selectedUserStoryAssignees);
  const [selectedUserStoryLabels, setSelectedUserStoryLabels] = useState<ProjectLabel[]>(savedSelectedValues.selectedUserStoryLabels);
  const [selectedUserStorySubState, setSelectedUserStorySubState] = useState<SubState | null>(savedSelectedValues.selectedUserStorySubState);
  const [selectedUserStoryModule, setSelectedUserStoryModule] = useState<Module | null>(savedSelectedValues.selectedUserStoryModule);
  const [selectedUserStoryProject, setSelectedUserStoryProject] = useState<Project | null>(savedSelectedValues.selectedUserStoryProject);

  // Feature selection state
  const [selectedFeatureEpic, setSelectedFeatureEpic] = useState<Epic | null>(savedSelectedValues.selectedFeatureEpic);
  const [selectedFeatureDateRange, setSelectedFeatureDateRange] = useState<DateRange | undefined>(
    feature?.startDate || feature?.endDate
      ? {
          from: feature?.startDate ? new Date(feature.startDate) : undefined,
          to: feature?.endDate ? new Date(feature.endDate) : undefined,
        }
      : savedSelectedValues.selectedFeatureDateRange
  );
  const [selectedFeatureAssignees, setSelectedFeatureAssignees] = useState<ProjectMember[]>(savedSelectedValues.selectedFeatureAssignees);
  const [selectedFeatureLabels, setSelectedFeatureLabels] = useState<ProjectLabel[]>(savedSelectedValues.selectedFeatureLabels);
  const [selectedFeatureSubState, setSelectedFeatureSubState] = useState<SubState | null>(savedSelectedValues.selectedFeatureSubState);
  const [selectedFeatureModule, setSelectedFeatureModule] = useState<Module | null>(savedSelectedValues.selectedFeatureModule);
  const [selectedFeatureProject, setSelectedFeatureProject] = useState<Project | null>(savedSelectedValues.selectedFeatureProject);

  return {
    // Module sub-state
    selectedModuleSubState,
    setSelectedModuleSubState,

    // Cycle
    selectedCycle,
    setSelectedCycle,

    // Project
    selectedProject,
    setSelectedProject,

    // Members
    selectedAssignees,
    setSelectedAssignees,
    selectedLead,
    setSelectedLead,
    selectedMembers,
    setSelectedMembers,

    // Date range
    selectedDateRange,
    setSelectedDateRange,

    // Epic-specific
    selectedEpicPriority,
    setSelectedEpicPriority,
    selectedEpicState,
    setSelectedEpicState,
    selectedEpicAssignee,
    setSelectedEpicAssignee,
    selectedEpicLabels,
    setSelectedEpicLabels,
    selectedEpicDateRange,
    setSelectedEpicDateRange,

    // Sub-state
    selectedSubState,
    setSelectedSubState,

    // Module
    selectedModule,
    setSelectedModule,

    // User Story
    selectedUserStoryEpic,
    setSelectedUserStoryEpic,
    selectedUserStoryFeature,
    setSelectedUserStoryFeature,
    selectedUserStoryDateRange,
    setSelectedUserStoryDateRange,
    selectedUserStoryAssignees,
    setSelectedUserStoryAssignees,
    selectedUserStoryLabels,
    setSelectedUserStoryLabels,
    selectedUserStorySubState,
    setSelectedUserStorySubState,
    selectedUserStoryModule,
    setSelectedUserStoryModule,
    selectedUserStoryProject,
    setSelectedUserStoryProject,

    // Feature
    selectedFeatureEpic,
    setSelectedFeatureEpic,
    selectedFeatureDateRange,
    setSelectedFeatureDateRange,
    selectedFeatureAssignees,
    setSelectedFeatureAssignees,
    selectedFeatureLabels,
    setSelectedFeatureLabels,
    selectedFeatureSubState,
    setSelectedFeatureSubState,
    selectedFeatureModule,
    setSelectedFeatureModule,
    selectedFeatureProject,
    setSelectedFeatureProject,
  };
};
