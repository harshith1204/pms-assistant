import { Component, EventEmitter, Inject, OnInit, Output, ViewChild } from '@angular/core';
import { MatCheckboxChange } from '@angular/material/checkbox';
import { MAT_DIALOG_DATA, MatDialog, MatDialogRef } from '@angular/material/dialog';
import { PopupPmsComponent } from '../popup-pms/popup-pms.component';
import { MatRadioChange } from '@angular/material/radio';
import { WorkManagementService } from '../../work-management.service';
import { MatDatepicker } from '@angular/material/datepicker';


interface PriorityItem {
  name: string;
  icon: string;
  class: string;
  checked: boolean;
}

interface StateItem {
  name: string;
  icon: string;
  class: string;
  checked: boolean;
}

interface AssigneeItem {
  name: string;
  avatar: string;
  initial: string;
  checked: boolean;
}

interface CycleItem {
  name: string;
  status: string;
  checked: boolean;
}

interface ModuleItem {
  name: string;
  icon: string;
  checked: boolean;
}

interface MentionItem {
  name: string;
  initial: string;
  checked: boolean;
}

interface CreatedByItem {
  name: string;
  initial: string;
  checked: boolean;
}

interface LabelItem {
  name: string;
  color: string;
  checked: boolean;
}

interface GroupingOption {
  name: string;
  value: string;
  checked: boolean;
}

interface DateRangeOption {
  name: string;
  value: string;
  checked: boolean;
}
interface ObjectModel {
  name: string;
  id: string;
}

@Component({
  selector: 'app-filter-pms',
  templateUrl: './filter-pms.component.html',
  styleUrls: ['./filter-pms.component.scss']
})
export class FilterPmsComponent implements OnInit {
   @Output() dataChanged = new EventEmitter<any>();


  constructor(
        @Inject(MAT_DIALOG_DATA) public data: any,
            private matDialog: MatDialog,
              private projectService:WorkManagementService,
          private dialogRef: MatDialogRef<PopupPmsComponent>
  ){}
  ngOnInit(): void {
    this.screen = this.data.screen;
    
    if (this.data?.status === 'PROJECT_FILTER') {
      if (this.data.projectData?.members) {
        this.membersList = this.data.projectData.members;
      }
      
      this.selectedLeads = this.selectedLeads || [];
      this.selectedmembers = this.selectedmembers || [];
      this.selectedAccess = this.selectedAccess || [];
      
      this.initializeFilteredArrays();
      this.getUpdatedFilters();
    } else {
      // Load saved access type for PAGE_FILTER
      if (this.data?.status === 'PAGE_FILTER') {
        const savedAccess = localStorage.getItem('PAGE_FILTER_ACCESS');
        if (savedAccess) {
          this.selectedPageAccess = savedAccess;
          this.selectedAccess = [savedAccess];
          this.pageAccessTypes.forEach(type => {
            type.checked = type.name === savedAccess;
          });
        }
      }
      
      if(this.data.projectData!=null && this.data.projectData){
       this.getProjectCyclesAPI();
      this.getProjectModulesAPI();
      this.getPages();
      }
      this.getAllLabels();
      this.getProjectMembers();
      this.getAllSubStateList();
    }
    
    this.feature = this.data?.projectData?.features;
  }

  private dataLoadedCounter = 0;
  private expectedDataCount = 5; 

  private checkIfAllDataLoaded() {
    this.dataLoadedCounter++;
    if (this.dataLoadedCounter >= this.expectedDataCount) {
      this.getUpdatedFilters();
    }
  }

  feature:any;
  screen:any;
  isMyprojects:boolean = false;
  selectedmembers:any[]=[];
  selectedAssignees: any[] = [];
  selectedLeads: any[] = [];
  selectedBusinessMembers:any[]=[];
  selectedmentions:any[]=[];
  selectedCreatedBy:any[]=[];
  selectedPriorities:any[]=[];
  selectedStates:any[]=[];
  selectedAccess: string[] = [];
  selectedPageAccess:any
  // projectStates:any;
  projectLabels:any= [];
  selectedViewType: any;
  ascendingType: any;
  projectData: any;
  projectCycles:any;
  selectedCycles:any[]=[];
  projectModules:any;
  selectedModules:any[]=[];
  selectedLabels:any[]=[];
  selectedPages:any[]=[];
  customStartDate1:any;
  customEndDate:any;
  selectedStartDate:any;
  selectedEndDate:any;


  // filter variables
  searchTerm:any;
  filteredPriorities:any[]=[];
  filteredStates:any[]=[];
  filteredAssignees:any[]=[];
  filteredCycles:any[]=[];
  filteredModules:any[]=[];
  filteredCreatedBy:any[]=[];
  filteredLabels:any[]=[];
  filteredPages:any[]=[];
  showMoreLabels: boolean = false;
  showMoreStates: boolean = false;
  showMoreAssignees: boolean = false;
  showMoreCycles: boolean = false;
  showMoreModules: boolean = false;
  showMorePages: boolean = false;
  showMoreCreatedBy: boolean = false;
  panelExpanded:boolean = true;

  applySearch() {
this.panelExpanded = true;
  if (this.searchTerm != null && this.searchTerm.trim() !== '') {
    const term = this.searchTerm.toLowerCase();

    this.filteredPriorities = this.priorityItems?.length
      ? this.priorityItems.filter(item => item.name.toLowerCase().includes(term)).map(item => ({
          ...item,
          checked: this.selectedPriorities?.includes(item.name)
        }))
      : [];

    this.filteredStates = this.projectStates?.length
      ? this.projectStates.filter(item => item.name.toLowerCase().includes(term)).map(item => ({
          ...item,
          checked: this.selectedStates?.some(s => s.name === item.name)
        }))
      : [];

    this.filteredAssignees = this.membersList?.length
      ? this.membersList.filter(item => item.name.toLowerCase().includes(term)).map(item => ({
          ...item,
          checked: this.selectedAssignees?.some(a => a.memberId === item.memberId)
        }))
      : [];

    this.filteredCycles = this.projectCycles?.length
      ? this.projectCycles.filter(item => (item.title || item.name || '').toLowerCase().includes(term)).map(item => ({
          ...item,
          checked: this.selectedCycles?.some(c => c.id === item.id)
        }))
      : [];

    this.filteredModules = this.projectModules?.length
      ? this.projectModules.filter(item => (item.title || item.name || '').toLowerCase().includes(term)).map(item => ({
          ...item,
          checked: this.selectedModules?.some(m => m.id === item.id)
        }))
      : [];

    this.filteredPages = this.projectPages?.length
      ? this.projectPages.filter(item => (item.title || item.name || '').toLowerCase().includes(term)).map(item => ({
          ...item,
          checked: this.selectedPages?.some(p => p.id === item.id)
        }))
      : [];

    this.filteredCreatedBy = this.membersList?.length
      ? this.membersList.filter(item => item.name.toLowerCase().includes(term)).map(item => ({
          ...item,
          checked: this.selectedCreatedBy?.some(m => m.memberId === item.memberId)
        }))
      : [];

    this.filteredLabels = this.projectLabels?.length
      ? this.projectLabels.filter(item => (item.label || item.name || '').toLowerCase().includes(term)).map(item => ({
          ...item,
          checked: this.selectedLabels?.some(l => l.id === item.id)
        }))
      : [];

  } else {
    // Reset all if search is empty or null - ensure arrays exist before mapping
    this.filteredPriorities = this.priorityItems?.length
  ? this.priorityItems.map(item => ({
      ...item,
      checked: this.selectedPriorities?.includes(item.name) || false
    }))
  : [];

this.filteredStates = this.projectStates?.length
  ? this.projectStates.map(item => ({
      ...item,
      checked: this.selectedStates?.some(s => s.name === item.name) || false
    }))
  : [];

this.filteredAssignees = this.membersList?.length
  ? this.membersList.map(item => ({
      ...item,
      checked: this.selectedAssignees?.some(a => a.memberId === item.memberId) || false
    }))
  : [];

this.filteredCycles = this.projectCycles?.length
  ? this.projectCycles.map(item => ({
      ...item,
      checked: this.selectedCycles?.some(c => c.id === item.id) || false
    }))
  : [];

this.filteredModules = this.projectModules?.length
  ? this.projectModules.map(item => ({
      ...item,
      checked: this.selectedModules?.some(m => m.id === item.id) || false
    }))
  : [];
this.filteredPages = this.projectPages?.length
  ? this.projectPages.map(item => ({
      ...item,
      checked: this.selectedPages?.some(p => p.id === item.id) || false
    }))
  : [];

this.filteredCreatedBy = this.membersList?.length
  ? this.membersList.map(item => ({
      ...item,
      checked: this.selectedCreatedBy?.some(m => m.memberId === item.memberId) || false
    }))
  : [];

this.filteredLabels = this.projectLabels?.length
  ? this.projectLabels.map(item => ({
      ...item,
      checked: this.selectedLabels?.some(l => l.id === item.id) || false
    }))
  : [];

  }

// if (isWorkItemFilter) {
//     payload = {
//       startDate: this.customStartDate,
//       endDate: this.customDueDate,
//       stateId: this.selectedStates.map(s => s.id),
//       leadId: this.selectedLeads.map(s => s.memberId || s.id),
//       priority: this.selectedPriorities,
//       assigneeId: this.selectedAssignees.map(s => s.memberId),
//       labelId: this.selectedLabels.map(s => s.id),
//       cycleId: this.selectedCycles.map(s => s.id),
//       moduleId: this.selectedModules.map(s => s.id),
//       createdById: this.selectedCreatedBy.map(s => s.memberId)
//     };
//   }else

  }
 returnPayload() {
  const isWorkItemFilter = this.data?.status === 'WORK_ITEM_FILTER';
  const isProjectFilter = this.data?.status === 'PROJECT_FILTER';
  const isPageFilter = this.data?.status === 'PAGE_FILTER';
  
  let payload: any;
  
  if (isProjectFilter) {
    payload = {
      startDate: this.customStartDate,
      endDate: this.customEndDate, 
      lead: this.selectedLeads.map(s => ({ id: s.memberId || s.id, name: s.name })),
      members: this.selectedmembers.map(s => ({ id: s.memberId || s.id, name: s.name })),
      access: this.selectedAccess || []
    };
  } else if (isPageFilter){
    payload = {
      moduleId: this.selectedModules.map(s => ({ id: s.id, name: s?.title || s?.name })),
      cycleId: this.selectedCycles.map(s => ({ id: s.id, name: s?.title || s?.name })),
      pageId: this.selectedPages.map(s => ({ id: s.id, name: s?.title || s?.name })),
      createdBy:this.selectedCreatedBy.map(s => ({id: s.memberId, name: s.name})),
      memberIds:this.selectedAssignees.map(s => ({ id: s.memberId, name: s.name })),
      access: this.selectedPageAccess || this.selectedAccess[0] || 'PUBLIC'
    };
  } else {
    payload = {
      startDate: this.customStartDate,
      endDate: this.customDueDate,
      state: this.selectedStates.map(s => ({ id: s.id, name: s.name })),
      lead: this.selectedLeads.map(s => ({ id: s.memberId || s.id, name: s.name })),
      priority: this.selectedPriorities,
      assignee: this.selectedAssignees.map(s => ({ id: s.memberId, name: s.name })),
      label: this.selectedLabels.map(s => ({ id: s.id, name: s?.label || s?.name })),
      cycle: this.selectedCycles.map(s => ({ id: s.id, name: s?.title || s?.name })),
      modules: this.selectedModules.map(s => ({ id: s.id, name: s?.title || s?.name })),
      createdBy:this.selectedCreatedBy.map(s => ({id: s.memberId, name: s.name}))
    };
  }
  
  const cleanedPayload = Object.entries(payload).reduce((acc, [key, value]) => {
    if (
      value === null ||
      value === undefined ||
      (Array.isArray(value) && value.length === 0) ||
      (typeof value === 'object' && !Array.isArray(value) && Object.values(value).every(v => !v)) ||
      value === ""
    ) {
      
    } else {
      acc[key] = value;
    }
    return acc;
  }, {} as any);
   this.dataChanged.emit(cleanedPayload);
   
}

  customDateRange: { start: Date | null; end: Date | null } = { start: null, end: null };

onCustomDateRangeSelect(range: { start: Date | null; end: Date | null }) {
  if (range?.start && range?.end) {
    
    // You can apply filters, update model, etc.
  }
}

  onAssigneeChange(event: any, item: any) {
  if (event.checked) {
    if (!this.selectedAssignees.some(s => s.memberId === item.memberId)) {
      this.selectedAssignees.push(item);
    }
  } else {
    this.selectedAssignees = this.selectedAssignees.filter(s => s.memberId !== item.memberId);
  }
  
  const filteredItem = this.filteredAssignees.find(a => a.memberId === item.memberId);
  if (filteredItem) {
    filteredItem.checked = event.checked;
  }
  
  this.returnPayload();
}


onPriorityChange(event: MatCheckboxChange, item: any) {
  if (event.checked) {
    if (!this.selectedPriorities.includes(item.name)) {
      this.selectedPriorities.push(item.name);
    }
  } else {
    this.selectedPriorities = this.selectedPriorities.filter(name => name !== item.name);
  }
  
  const filteredItem = this.filteredPriorities.find(p => p.name === item.name);
  if (filteredItem) {
    filteredItem.checked = event.checked;
  }
  
  this.returnPayload();
}

onAccessChange(event: MatCheckboxChange, item: any) {
  if (event.checked) {
    if (this.data?.status === 'PAGE_FILTER') {
      this.selectedAccess = [item.name];
      this.selectedPageAccess = item.name;
      
      this.pageAccessTypes.forEach(type => {
        type.checked = type.name === item.name;
      });
      
      localStorage.setItem('PAGE_FILTER_ACCESS', item.name);
    } else {
      if (!this.selectedAccess.includes(item.name)) {
        this.selectedAccess.push(item.name);
      }
    }
  } else {
    this.selectedAccess = this.selectedAccess.filter(name => name !== item.name);
    
    if (this.data?.status === 'PAGE_FILTER') {
      this.selectedPageAccess = '';
      localStorage.removeItem('PAGE_FILTER_ACCESS');
    }
  }
  
  this.returnPayload();
}


 onCycleChange(event: MatCheckboxChange, item: any) {
   
     if (event.checked) {
    if (!this.selectedCycles.some(s => s.id === item.id)) {
      this.selectedCycles.push(item);
    }
  } else {
    this.selectedCycles = this.selectedCycles.filter(s => s.id !== item.id);
  }
  
  
  if (this.filteredCycles && this.filteredCycles.length > 0) {
    const filteredItem = this.filteredCycles.find(c => c.id === item.id);
    if (filteredItem) {
      filteredItem.checked = event.checked;
      console.log('Updated filtered item:', filteredItem);
    } else {
      console.log('Filtered item not found for id:', item.id);
    }
  } else {
    console.log('filteredCycles is empty or not initialized');
  }
  
  this.returnPayload();
  }

   onModuleChange(event: MatCheckboxChange, item: any) {
   
     if (event.checked) {
    if (!this.selectedModules.some(s => s.id === item.id)) {
      this.selectedModules.push(item);
    }
  } else {
    this.selectedModules = this.selectedModules.filter(s => s.id !== item.id);
  }
  
  const filteredItem = this.filteredModules.find(m => m.id === item.id);
  if (filteredItem) {
    filteredItem.checked = event.checked;
  }
  
  this.returnPayload();
  }
  onPageChange(event: MatCheckboxChange, item: any) {
    if (event.checked) {
      if (!this.selectedPages.some(s => s.id === item.id)) {
        this.selectedPages.push(item);
      }
    } else {
      this.selectedPages = this.selectedPages.filter(s => s.id !== item.id);
    }

    const filteredItem = this.filteredPages.find(p => p.id === item.id);
    if (filteredItem) {
      filteredItem.checked = event.checked;
    }

    this.returnPayload();
  }

isAssigneeSelected(item: any): boolean {
  return this.selectedAssignees.some(s => s.memberId === item.memberId);
}
isModuleSelected(item: any): boolean {
  return this.selectedModules.some(s => s.id === item.id);
}
isStateSelected(item: any): boolean {
  return this.selectedStates.some(s => s.stateId === item.stateId);
}

isLabelSelected(item: any): boolean {
  return this.selectedLabels.some(s => s.id === item.id);
}
isMentionselected(item: any): boolean {
  return this.selectedmentions.some(s => s.id === item.id);
}
isCreatedByselected(item: any): boolean {
  return this.selectedCreatedBy.some(s => s.memberId === item.memberId);
}

isCycleselected(item: any): boolean {
  return this.selectedCycles.some(s => s.id === item.id);
}


isMyprojectsView(item :any){

}
  isLeadSelected(item: any): boolean {
    const itemId = item.id || item.memberId;
    const isSelected = (this.selectedLeads ?? []).some(selected => 
      selected.id === itemId || selected.memberId === itemId
    );
    return isSelected;
  }

  ismemberSelected(item: any): boolean {
    const itemId = item.id || item.memberId;
    const isSelected = (this.selectedmembers ?? []).some(selected => 
      selected.id === itemId || selected.memberId === itemId
    );
    return isSelected;
  }

isAccessSelected(item: any): boolean {
  return this.selectedAccess?.includes(item.name) || false;
}
  
  priorityItems: PriorityItem[] = [
    { name: 'URGENT', icon: 'error_outline', class: 'urgent', checked: false },
    { name: 'HIGH', icon: 'signal_cellular_alt', class: 'high', checked: false },
    { name: 'MEDIUM', icon: 'signal_cellular_alt_2_bar', class: 'medium', checked: false },
    { name: 'LOW', icon: 'signal_cellular_alt_1_bar', class: 'low', checked: false },
    { name: 'NONE', icon: 'remove_circle_outline', class: 'none', checked: false }
  ];

   datesList= [
     'Today',
     'Yesterday',
     'Last 7 days',
     'Last 30 days',
    //  'Custom', 
  ];

  selectedDateRange: string = '';

  onDateRangeSelection(selectedOption: string) {
    this.selectedDateRange = selectedOption;
    
    if (selectedOption === 'Custom') {
      this.customStartDate = null;
      this.customEndDate = null;
    } else {
      const dateRange = this.calculateDateRange(selectedOption);
      this.customStartDate = dateRange.startDate;
      this.customEndDate = dateRange.endDate;
      this.returnPayload();
    }
  }

  
 getStateIcon(item: any): string {
  switch (item) {
    case 'Backlog': return 'radio_button_unchecked';
    case 'Unstarted': return 'circle';
    case 'Started': return 'play_circle';
    case 'Completed': return 'check_circle';
    case 'Cancelled': return 'cancel';
    default: return 'radio_button_unchecked';
  }
}
 getStateClass(item: any): string {
  if (item === "Backlog") {
    return 'backlog';
  } else if (item === "Unstarted") {
    return 'todo';
  } else if (item === "Started") {
    return 'in-progress';
  } else if (item === "Completed") {
    return 'done';
  } else if (item === "Cancelled") {
    return 'cancelled';
  }
  return 'backlog'; 
}




  accessTypes: any[] = [
    { name: 'PRIVATE', icon: 'error_outline', checked: false },
    { name: 'PUBLIC', icon: 'signal_cellular_alt', checked: false },
  ];
  pageAccessTypes: any[] = [
    { name: 'PRIVATE', icon: 'error_outline', checked: false },
    { name: 'PUBLIC', icon: 'signal_cellular_alt', checked: true },
    { name: 'ARCHIVED', icon: 'signal_cellular_alt', checked: false }
  ];

  stateItems: StateItem[] = [
    { name: 'Backlog', icon: 'radio_button_unchecked', class: 'backlog', checked: false },
    { name: 'Todo', icon: 'circle', class: 'todo', checked: false },
    { name: 'In Progress', icon: 'play_circle', class: 'in-progress', checked: false },
    { name: 'Done', icon: 'check_circle', class: 'done', checked: false },
    { name: 'Cancelled', icon: 'cancel', class: 'cancelled', checked: false }
  ];

  assigneeItems: AssigneeItem[] = [
    { name: 'You', avatar: '', initial: 'Y', checked: false },
    { name: 'abhinaya', avatar: '', initial: 'A', checked: false },
    { name: 'shiva.s', avatar: '', initial: 'S', checked: false },
    { name: 'tarungarg', avatar: '', initial: 'T', checked: false }
  ];
   members: AssigneeItem[] = [
    { name: 'You', avatar: '', initial: 'Y', checked: false },
    { name: 'abhinaya', avatar: '', initial: 'A', checked: false },
    { name: 'shiva.s', avatar: '', initial: 'S', checked: false },
    { name: 'tarungarg', avatar: '', initial: 'T', checked: false }
  ];

  cycleItems: CycleItem[] = [
    { name: 'CMIS', status: 'active', checked: false },
    { name: 'Enhancement', status: 'active', checked: false },
    { name: 'Optimisation', status: 'active', checked: false }
  ];

  moduleItems: ModuleItem[] = [
    { name: 'Invoice', icon: 'description', checked: false },
    { name: 'Analytics', icon: 'analytics', checked: false },
    { name: 'App Repo', icon: 'folder', checked: false }
  ];

  mentionItems: MentionItem[] = [
    { name: 'You', initial: 'Y', checked: false },
    { name: 'aditya', initial: 'A', checked: false },
    { name: 'akhil', initial: 'A', checked: false }
  ];

  createdByItems: CreatedByItem[] = [
    { name: 'You', initial: 'Y', checked: false },
    { name: 'gaurav.sharma531', initial: 'G', checked: false }
  ];

  labelItems: LabelItem[] = [
    { name: 'Bug', color: '#dc3545', checked: false },
    { name: 'Design', color: '#ff69b4', checked: false },
    { name: 'Desktop View', color: '#ff6b00', checked: false },
    { name: 'Functionality', color: '#2ecc71', checked: false },
    { name: 'Left over bugs', color: '#ffd700', checked: false }
  ];

  workItemGroupingOptions: GroupingOption[] = [
    { name: 'All Work items', value: 'all', checked: true },
    { name: 'Active Work items', value: 'active', checked: false },
    { name: 'Backlog Work items', value: 'backlog', checked: false }
  ];

  startDateOptions: DateRangeOption[] = [
    { name: '1 week from now', value: '1week', checked: false },
    { name: '2 weeks from now', value: '2weeks', checked: false },
    { name: '1 month from now', value: '1month', checked: false },
    { name: '2 months from now', value: '2months', checked: false },
    { name: 'Custom', value: 'custom', checked: false }
  ];

  dueDateOptions: DateRangeOption[] = [
    { name: '1 week from now', value: '1week', checked: false },
    { name: '2 weeks from now', value: '2weeks', checked: false },
    { name: '1 month from now', value: '1month', checked: false },
    { name: '2 months from now', value: '2months', checked: false },
    { name: 'Custom', value: 'custom', checked: false }
  ];

showCustomStartDatePicker = false;
showCustomDueDatePicker = false;
  customStartDate: any;
customSelectedStartDate: Date | null = null;
customSelectedDueDate: Date | null = null;
  customDueDate: any;
  selectedDateOption: any;

  @ViewChild('startDatePicker') startDatePicker!: MatDatepicker<any>;
  @ViewChild('dueDatePicker') dueDatePicker!: MatDatepicker<any>;

  get selectedPriorityCount(): number {
    return this.priorityItems.filter(item => item.checked).length;
  }

  get selectedStateCount(): number {
    return this.stateItems.filter(item => item.checked).length;
  }

  get selectedAssigneeCount(): number {
    return this.assigneeItems.filter(item => item.checked).length;
  }

  get selectedCycleCount(): number {
    return this.cycleItems.filter(item => item.checked).length;
  }

  get selectedModuleCount(): number {
    return this.moduleItems.filter(item => item.checked).length;
  }

  get selectedMentionCount(): number {
    return this.mentionItems.filter(item => item.checked).length;
  }

  get selectedCreatedByCount(): number {
    return this.createdByItems.filter(item => item.checked).length;
  }

  get selectedLabelCount(): number {
    return this.labelItems.filter(item => item.checked).length;
  }


  onDateOptionSelection(event: MatRadioChange) {
    const selectedItem = this.selectedDateOption;

    if(selectedItem === 'Custom'){
    } else {
      const dateRange = this.calculateDateRange(selectedItem);
      this.customStartDate = dateRange.startDate;
      this.customEndDate = dateRange.endDate;
      this.returnPayload();
    }
  }

  calculateDateRange(dateOption: string): { startDate: string, endDate: string } {
    const today = new Date();
    const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const endOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59, 59, 999);
    
    let startDate: Date;
    let endDate: Date;

    switch (dateOption) {
      case 'Today':
        startDate = startOfToday;
        endDate = endOfToday;
        break;
        
      case 'Yesterday':
        const yesterday = new Date(today);
        yesterday.setDate(today.getDate() - 1);
        startDate = new Date(yesterday.getFullYear(), yesterday.getMonth(), yesterday.getDate());
        endDate = new Date(yesterday.getFullYear(), yesterday.getMonth(), yesterday.getDate(), 23, 59, 59, 999);
        break;
        
      case 'Last 7 days':
        const sevenDaysAgo = new Date(today);
        sevenDaysAgo.setDate(today.getDate() - 6); 
        startDate = new Date(sevenDaysAgo.getFullYear(), sevenDaysAgo.getMonth(), sevenDaysAgo.getDate());
        endDate = endOfToday;
        break;
        
      case 'Last 30 days':
        const thirtyDaysAgo = new Date(today);
        thirtyDaysAgo.setDate(today.getDate() - 29); 
        startDate = new Date(thirtyDaysAgo.getFullYear(), thirtyDaysAgo.getMonth(), thirtyDaysAgo.getDate());
        endDate = endOfToday;
        break;
        
      default:
        startDate = startOfToday;
        endDate = endOfToday;
        break;
    }

    const formatDate = (date: Date): string => {
      const day = String(date.getDate()).padStart(2, '0');
      const month = String(date.getMonth() + 1).padStart(2, '0'); 
      const year = date.getFullYear();
      return `${day}-${month}-${year}`;
    };
    return { startDate: formatDate(startDate), endDate: formatDate(endDate) };
  }


    

  getProjectsList() {
    throw new Error('Method not implemented.');
  }

  onStateChange(event: MatCheckboxChange, item: any) {
     if (event.checked) {
    if (!this.selectedStates.some(s => s.id === item.id)) {
      this.selectedStates.push(item);
    }
  } else {
    this.selectedStates = this.selectedStates.filter(s => s.id !== item.id);
  }
  
  const filteredItem = this.filteredStates.find(s => s.id === item.id);
  if (filteredItem) {
    filteredItem.checked = event.checked;
  }
  
    this.returnPayload();
  }
  
  onLeadChange(event: MatCheckboxChange, item: any): void {
    const itemId = item.id || item.memberId;
    if (event.checked) {
      if (!this.selectedLeads.some(s => s.id === itemId || s.memberId === itemId)) {
        this.selectedLeads.push({
          id: itemId,
          memberId: itemId,
          name: item.name
        });
      }
    } else {
      this.selectedLeads = this.selectedLeads.filter(s => 
        s.id !== itemId && s.memberId !== itemId
      );
    }
    this.returnPayload();
  }

  onMembersChange(event: MatCheckboxChange, item: any): void {
    const itemId = item.id || item.memberId;
    if (event.checked) {
      if (!this.selectedmembers.some(s => s.id === itemId || s.memberId === itemId)) {
        this.selectedmembers.push({
          id: itemId,
          memberId: itemId,
          name: item.name
        });
      }
    } else {
      this.selectedmembers = this.selectedmembers.filter(s => 
        s.id !== itemId && s.memberId !== itemId
      );
    }
    this.returnPayload();
  }



  onMentionChange(event: MatCheckboxChange, item: any) {
    if (event.checked) {
     if (!this.selectedmentions.some(s => s.id === item.id)) {
      this.selectedmentions.push(item);
    }
  } else {
    this.selectedmentions = this.selectedmentions.filter(i => i.id !== item.id);
  }
  this.returnPayload();
  }

  onCreatedByChange(event: MatCheckboxChange, item: any) {
       if (event.checked) {
     if (!this.selectedCreatedBy.some(s => s.memberId === item.memberId)) {
      this.selectedCreatedBy.push(item);
    }
  } else {
    this.selectedCreatedBy = this.selectedCreatedBy.filter(i => i.memberId !== item.memberId);
  }
  
  const filteredItem = this.filteredCreatedBy.find(c => c.memberId === item.memberId);
  if (filteredItem) {
    filteredItem.checked = event.checked;
  }
  
  this.returnPayload();
  }

  onLabelChange(event: MatCheckboxChange, item: any) {
       console.log('onLabelChange called:', { event: event.checked, item: item, selectedLabels: this.selectedLabels });
       
       if (event.checked) {
     if (!this.selectedLabels.some(s => s.id === item.id)) {
      this.selectedLabels.push(item);
    }
  } else {
    this.selectedLabels = this.selectedLabels.filter(i => i.id !== item.id);
  }
  
  console.log('selectedLabels after change:', this.selectedLabels);
  if (this.filteredLabels && this.filteredLabels.length > 0) {
    const filteredItem = this.filteredLabels.find(l => l.id === item.id);
    if (filteredItem) {
      filteredItem.checked = event.checked;
      console.log('Updated filtered label item:', filteredItem);
    } else {
      console.log('Filtered label item not found for id:', item.id);
    }
  } else {
    console.log('filteredLabels is empty or not initialized');
  }
  
  this.returnPayload();
  }

  toggleShowMoreLabels() {
    this.showMoreLabels = !this.showMoreLabels;
  }

  getDisplayedLabels() {
    if (!this.filteredLabels || this.filteredLabels.length === 0) {
      return [];
    }
    
    if (this.showMoreLabels) {
      return this.filteredLabels;
    }
    
    return this.filteredLabels.slice(0, 5);
  }

  toggleShowMoreStates() {
    this.showMoreStates = !this.showMoreStates;
  }

  getDisplayedStates() {
    if (!this.filteredStates || this.filteredStates.length === 0) {
      return [];
    }
    
    if (this.showMoreStates) {
      return this.filteredStates;
    }
    
    return this.filteredStates.slice(0, 5);
  }

  toggleShowMoreAssignees() {
    this.showMoreAssignees = !this.showMoreAssignees;
  }

  getDisplayedAssignees() {
    if (!this.filteredAssignees || this.filteredAssignees.length === 0) {
      return [];
    }
    
    if (this.showMoreAssignees) {
      return this.filteredAssignees;
    }
    
    return this.filteredAssignees.slice(0, 5);
  }

  toggleShowMoreCycles() {
    this.showMoreCycles = !this.showMoreCycles;
  }

  getDisplayedCycles() {
    if (!this.filteredCycles || this.filteredCycles.length === 0) {
      return [];
    }
    
    if (this.showMoreCycles) {
      return this.filteredCycles;
    }
    
    return this.filteredCycles.slice(0, 5);
  }

  toggleShowMoreModules() {
    this.showMoreModules = !this.showMoreModules;
  }
  toggleShowMorePages(){
    this.showMorePages = !this.showMorePages;
  }

  getDisplayedModules() {
    if (!this.filteredModules || this.filteredModules.length === 0) {
      return [];
    }
    
    if (this.showMoreModules) {
      return this.filteredModules;
    }
    
    return this.filteredModules.slice(0, 5);
  }
  getDisplayedPages(){
      if (!this.filteredPages || this.filteredPages.length === 0) {
      return [];
    }
    if (this.showMorePages) {
      return this.filteredPages;
    }
    return this.filteredPages.slice(0, 5);
  }

  toggleShowMoreCreatedBy() {
    this.showMoreCreatedBy = !this.showMoreCreatedBy;
  }

  getDisplayedCreatedBy() {
    if (!this.filteredCreatedBy || this.filteredCreatedBy.length === 0) {
      return [];
    }
    
    if (this.showMoreCreatedBy) {
      return this.filteredCreatedBy;
    }
    
    return this.filteredCreatedBy.slice(0, 5);
  }

  onGroupingChange(option: GroupingOption) {
    this.workItemGroupingOptions.forEach(item => {
      item.checked = item === option;
    });
  }

  calculateFutureDate(value: string): string | null {
  const now = new Date();
  let future: Date;

  switch (value) {
    case '1week':
      future = new Date(now);
      future.setDate(now.getDate() + 7);
      break;
    case '2weeks':
      future = new Date(now);
      future.setDate(now.getDate() + 14);
      break;
    case '1month':
      future = new Date(now);
      future.setMonth(now.getMonth() + 1);
      break;
    case '2months':
      future = new Date(now);
      future.setMonth(now.getMonth() + 2);
      break;
    default:
      return null;
  }

  // Format dd-MM-yyyy
  const day = String(future.getDate()).padStart(2, '0');
  const month = String(future.getMonth() + 1).padStart(2, '0'); // month is 0-based
  const year = future.getFullYear();

  return `${day}-${month}-${year}`;
}

onCustomStartDateChange(event: any,) {
  if (event.value) {
    const date: Date = event.value;
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0'); // month is 0-based
    const year = date.getFullYear();
    const formattedDate = `${day}-${month}-${year}`;

 this.customSelectedStartDate = event.value;   // keep original Date
      this.customStartDate = formattedDate; 
  } else {

       this.customSelectedStartDate = null;
      this.customStartDate = null;
  }

  this.returnPayload();
}

onCustomDueDateChange(event: any){
  if(event.value){
 const date: Date = event.value;
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0'); // month is 0-based
    const year = date.getFullYear();
    const formattedDate = `${day}-${month}-${year}`;

      this.customSelectedDueDate = event.value;   // keep original Date
      this.customDueDate = formattedDate;  
  }else{
  this.customSelectedDueDate = null;
      this.customDueDate = null;
  }
  
   this.returnPayload();
}


onStartDateOptionChange(event: MatCheckboxChange, option: DateRangeOption) {
  this.startDateOptions.forEach(opt => opt.checked = false);
  option.checked = event.checked;

  if (option.value === 'custom') {
    this.showCustomStartDatePicker = event.checked;

    if (event.checked) {
      setTimeout(() => this.startDatePicker.open()); // open immediately
    
    } else {
      this.customStartDate = null;
    }
  } else if (event.checked) {
    this.showCustomStartDatePicker = false;
    this.customStartDate = this.calculateFutureDate(option.value);
  } else {
    this.customStartDate = null;
  }
if(option.value != 'custom'){
  this.returnPayload();
}

}


 onDueDateOptionChange(event: MatCheckboxChange, option: DateRangeOption) {
  // Clear all selections first to enforce single selection
  this.dueDateOptions.forEach(opt => opt.checked = false);
  option.checked = event.checked;

  if (option.value === 'custom') {
    this.showCustomDueDatePicker = event.checked;


     if (event.checked) {
      setTimeout(() => this.dueDatePicker.open());
  
    } else {
      this.customDueDate = null;
    }
  } else if (event.checked) {
    this.showCustomDueDatePicker = false;
    this.customDueDate = this.calculateFutureDate(option.value);
  } else {
    this.customDueDate = null;
  }
   if(option.value != 'custom'){
  this.returnPayload();
}
}

  formatDate(date: Date | null, type: 'start' | 'due'): string {
    if (!date) {
      return type === 'start' ? 'Start date' : 'Due date';
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  removeCustomStartDate(event: Event) {
    event.stopPropagation();
    this.customStartDate = null;
  }

  removeCustomDueDate(event: Event) {
    event.stopPropagation();
    this.customDueDate = null;
  }
getUpdatedFilters() {
  const selected = this.data?.selectedFilters || {};
  console.log('FilterPmsComponent getUpdatedFilters called with:', selected);

  this.initializeFilteredArrays();

  if (selected['State']) {
    this.selectedStates = [];
    selected['State'].forEach((name: string) => {
      const foundState = this.projectStates?.find(state => state.name === name);
      if (foundState) {
        this.selectedStates.push({
          id: foundState.id,
          name: foundState.name,
          stateId: foundState.stateId,
          stateName: foundState.stateName
        });
      }
    });
    
    if (this.projectStates?.length) {
      this.filteredStates = this.projectStates.map(item => ({
        ...item,
        checked: this.selectedStates.some(s => s.name === item.name)
      }));
    }
  }

  if (selected['Priority']) {
    this.selectedPriorities = [...selected['Priority']];
    this.filteredPriorities = this.priorityItems.map(item => ({
      ...item,
      checked: this.selectedPriorities.includes(item.name)
    }));
  }

  if (selected['Assignees']) {
    this.selectedAssignees = selected['Assignees'].map((a: any) => ({ memberId: a.memberId || '', name: a.name }));
    if (this.membersList?.length) {
      this.filteredAssignees = this.membersList.map(item => ({
        ...item,
        checked: this.selectedAssignees.some(a => a.name === item.name)
      }));
    }
  }

  if (selected['Labels']) {
    this.selectedLabels = [];
    selected['Labels'].forEach((name: string) => {
      const foundLabel = this.projectLabels?.find(label => label.label === name || label.name === name);
      if (foundLabel) {
        this.selectedLabels.push({
          id: foundLabel.id,
          name: foundLabel.label || foundLabel.name
        });
      }
    });
    
    if (this.projectLabels?.length) {
      this.filteredLabels = this.projectLabels.map(item => ({
        ...item,
        checked: this.selectedLabels.some(l => l.id === item.id)
      }));
    }
  }

  if (selected['Modules']) {
    this.selectedModules = selected['Modules'].map((mod: any) => ({ id: mod.id || '', name: mod.name }));
    if (this.projectModules?.length) {
      this.filteredModules = this.projectModules.map(item => ({
        ...item,
        checked: this.selectedModules.some(m => m.id === item.id)
      }));
    }
  }

  if (selected['Cycles']) {
    if(this.data?.screen === 'PAGE_FILTER'){
      this.selectedCycles = selected['Cycles'].map((mod: any) => ({ id: mod.id || '', name: mod.name }));
    if (this.projectCycles?.length) {
      this.filteredCycles = this.projectCycles.map(item => ({
        ...item,
        checked: this.selectedCycles.some(m => m.id === item.id)
      }));
    }
    }else{
      this.selectedCycles = [];
    selected['Cycles'].forEach((name: string) => {
      const foundCycle = this.projectCycles?.find(cycle => cycle.title === name || cycle.name === name);
      if (foundCycle) {
        this.selectedCycles.push({
          id: foundCycle.id,
          name: foundCycle.title || foundCycle.name,
          title: foundCycle.title
        });
      }
    });
    
    if (this.projectCycles?.length) {
      this.filteredCycles = this.projectCycles.map(item => ({
        ...item,
        checked: this.selectedCycles.some(c => c.id === item.id)
      }));
    }
    }  
  }

  if (selected['Lead']) {
    this.selectedLeads = selected['Lead'].map((lead: any) => ({ 
      id: lead.id || lead.memberId || '', 
      name: lead.name,
      memberId: lead.id || lead.memberId || ''
    }));
  }

  if (selected['Members']) {
    this.selectedmembers = selected['Members'].map((mem: any) => ({ 
      id: mem.id || mem.memberId || '', 
      name: mem.name,
      memberId: mem.id || mem.memberId || ''
    }));
  }

  if (selected['Access']) {
    if (this.data?.status === 'PAGE_FILTER') {
      // For PAGE_FILTER, handle access as string (single selection)
      const accessValue = typeof selected['Access'] === 'string' ? selected['Access'] : 
                         (Array.isArray(selected['Access']) && selected['Access'].length > 0 ? 
                          (typeof selected['Access'][0] === 'string' ? selected['Access'][0] : selected['Access'][0].name) : 
                          'PUBLIC');
      
      this.selectedPageAccess = accessValue;
      this.selectedAccess = [accessValue];
      
      this.pageAccessTypes.forEach(type => {
        type.checked = type.name === accessValue;
      });
      
      // Save to localStorage
      localStorage.setItem('PAGE_FILTER_ACCESS', accessValue);
    } else {
      // For other filters, preserve array behavior
      this.selectedAccess = selected['Access'].map((access: any) => 
        typeof access === 'string' ? access : access.name
      );
      
      this.accessTypes = this.accessTypes?.map(item => ({
        ...item,
        checked: this.selectedAccess.includes(item.name)
      })) || [
        { name: 'PRIVATE', icon: 'error_outline', checked: this.selectedAccess.includes('PRIVATE') },
        { name: 'PUBLIC', icon: 'signal_cellular_alt', checked: this.selectedAccess.includes('PUBLIC') }
      ];
    }
  }

  if (selected['StartDate']) {
    this.customStartDate = selected['StartDate'];
  }

  if (selected['EndDate']) {
    this.customEndDate = selected['EndDate'];
  }

  if (selected['Pages']) {
    this.selectedPages = selected['Pages'].map((page: any) => ({ 
      id: page.id || '', 
      name: page.name || page.title || ''
    }));
    
    if (this.projectPages?.length) {
      this.filteredPages = this.projectPages.map(item => ({
        ...item,
        checked: this.selectedPages.some(p => p.id === item.id)
      }));
    }
  }

  if (selected['CreatedBy']) {
    this.selectedCreatedBy = selected['CreatedBy'].map((creator: any) => ({ 
      memberId: creator.memberId || creator.id || '', 
      name: creator.name
    }));
    
    if (this.membersList?.length) {
      this.filteredCreatedBy = this.membersList.map(item => ({
        ...item,
        checked: this.selectedCreatedBy.some(c => c.memberId === item.memberId)
      }));
    }
  }
}

initializeFilteredArrays(){
  this.filteredPriorities = this.priorityItems?.map(item => ({
    ...item,
    checked: this.selectedPriorities?.includes(item.name) || false
  })) || [];

  this.filteredStates = this.projectStates?.map(item => ({
    ...item,
    checked: this.selectedStates?.some(s => s.name === item.name) || false
  })) || [];

  this.filteredAssignees = this.membersList?.map(item => ({
    ...item,
    checked: this.selectedAssignees?.some(a => a.memberId === item.memberId) || false
  })) || [];

  this.filteredCycles = this.projectCycles?.map(item => ({
    ...item,
    checked: this.selectedCycles?.some(c => c.id === item.id) || false
  })) || [];

  this.filteredModules = this.projectModules?.map(item => ({
    ...item,
    checked: this.selectedModules?.some(m => m.id === item.id) || false
  })) || [];

  this.filteredCreatedBy = this.membersList?.map(item => ({
    ...item,
    checked: this.selectedCreatedBy?.some(m => m.memberId === item.memberId) || false
  })) || [];

  this.filteredLabels = this.projectLabels?.map(item => ({
    ...item,
    checked: this.selectedLabels?.some(l => l.id === item.id) || false
  })) || [];

  this.filteredPages = this.projectPages?.map(item => ({
    ...item,
    checked: this.selectedPages?.some(p => p.id === item.id) || false
  })) || [];

  this.accessTypes = this.accessTypes?.map(item => ({
    ...item,
    checked: this.selectedAccess?.includes(item.name) || false
  })) || [
    { name: 'PRIVATE', icon: 'error_outline', checked: false },
    { name: 'PUBLIC', icon: 'signal_cellular_alt', checked: false }
  ];
}

 

   getProjectCyclesAPI(){
  
  const businessId = localStorage.getItem('businessId');
    const projectId = this.data.projectData.projectId;
    
    this.projectService.getProjectCycles(businessId,projectId).subscribe((response: any) => {
      console.log('cycles::', response);
       const data = response?.data || {};

      this.projectCycles = [
      ...(data.UPCOMING || []),
      ...(data.ACTIVE || []),
      ...(data.COMPLETED || [])
    ];
    this.applySearch();
    this.checkIfAllDataLoaded();
  
    }, (error: any) => {
      console.error('Error getting cycles', error);
      this.checkIfAllDataLoaded(); 
    });
  }

   getProjectModulesAPI(){
     const businessId = localStorage.getItem('businessId');
    const projectId = this.data.projectData.projectId;
        let payload = {
        businessId:businessId,
        projectId: projectId
      }
   
    this.projectService.getProjectModules(payload).subscribe((response: any) => {
      
      this.projectModules = response.data;
      this.applySearch();
      this.checkIfAllDataLoaded();
  
    }, (error: any) => {
      console.error('Error getting modules', error);
      this.checkIfAllDataLoaded(); 
    });
  }

  projectPages:any
  getPages(){
    const pId = this.data.projectData.projectId;
    let payload = {
      moduleId: null,
      cycleId: null,
      pageId: null,
      createdBy: null,
      memberIds: null
    };
    if (pId) {
      this.projectService.getAllPages(pId,payload).subscribe(
        (res: any) => {
          this.projectPages = res.data || [];
          console.log('Fetched pages:', this.projectPages);
          this.applySearch();
          this.checkIfAllDataLoaded();
        },
        (error: any) => {
          console.error('Error fetching pages:', error);
          this.checkIfAllDataLoaded();
        }
      );
    }
  }

  getAllLabels() {
  let projectId = this.data.projectData.projectId;
  this.projectService.getAllLabels(projectId).subscribe(
    (res: any) => {
      this.projectLabels = res.data || [];
      console.log('Fetched labels:', this.projectLabels);
      this.applySearch();
      this.checkIfAllDataLoaded();
    },
    (error: any) => {
      console.error('Error fetching labels:', error);
      this.checkIfAllDataLoaded(); 
    }
  );
}

projectStates:any[] = [];
  stateList:any;
  getAllSubStateList(){
    let projectId = this.data.projectData.projectId;
    this.projectService.getAllSubStatesList(projectId).subscribe({
      next: (response: any) => {
        this.stateList = response.data;
        this.projectStates = this.stateList.flatMap((state: any) => 
        state.subStates.map((subState: any) => ({
          ...subState,
          stateName: state.name,  
          stateId: state.id       
        }))
      );
        console.log('Sub-states fetched:', this.projectStates);
        this.applySearch();
        this.checkIfAllDataLoaded(); 
      },
      error: (error) => {
        console.error('Error fetching sub-states:', error);
        this.checkIfAllDataLoaded(); 
      }
    });
  }

membersList:any;
getProjectMembers() {
  let projectId = this.data.projectData.projectId;
  this.projectService.getAllMembers(projectId).subscribe(
    (res: any) => {
      this.membersList = res.data || [];
      console.log('Fetched members:', this.membersList);
      this.applySearch();
      this.checkIfAllDataLoaded();
    },
    (error: any) => {
      console.error('Error fetching members:', error);
      this.checkIfAllDataLoaded(); 
    }
  );
}
}
