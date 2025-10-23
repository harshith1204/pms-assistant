import { Component, Inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { WorkManagementService } from '../../work-management.service';

@Component({
  selector: 'app-popup-pms',
  templateUrl: './popup-pms.component.html',
  styleUrls: ['./popup-pms.component.scss']
})
export class PopupPmsComponent {

  constructor(
    private projectService: WorkManagementService,
    @Inject(MAT_DIALOG_DATA) public data: any,
    private dialogRef: MatDialogRef<PopupPmsComponent>
  ) {
    dialogRef.backdropClick().subscribe(() => {
      if (this.data.status === 'LABEL') {
        this.dialogRef.close({
          finalSelection: true,
          labels: this.data.selectedLabels || []
        });
      } else if (this.data.status === 'ASSIGNEE') {
        this.dialogRef.close({
          finalSelection: true,
          assignees: this.data.selectedAssignees || []
        });
      } else {
        this.dialogRef.close();
      }
    });
  }
  
  ngOnInit() {
    this.projectId = this.data.projectId;
    this.generateCalendarDays();
    this.getFilterValues();
    if (this.data?.type === 'EPIC') {
      this.getEpicWorkitemList();
    } else if (this.data?.type === 'SUB_WORK') {
      this.getSubWorkItemList();
    } else {
      this.onExistingWorkItemSelect();
    }
  }

  getFilterValues(){
    if(this.data.status ===  'PROJECT_VIEW'){
      this.selectedProjectView = this.data.values.selectedViewType;
      this.selectedAscending = this.data.values.ascendingType;
    }
    if(this.data.status === 'INBOX_MORE' && !this.data.selectedMoreType){
      this.data.selectedMoreType = 'SHOW_ALL';
    }
  }

    toggleValue = false;

  onToggleChange(event: any) {
    
    this.toggleValue = event.checked;
  }

  searchTerm: string = '';
   selectedProjectView:any = 'manual';
    selectedAscending:any = 'DESC';
    newMemberName:any;
    newMemberEmail:any;
    selectedStartDate:any;
    selectedEndDate:any;



  statuses = [
    { id: 1, name: 'Backlog', class: 'backlog' },
    { id: 2, name: 'Todo', class: 'todo' },
    { id: 3, name: 'In Progress', class: 'in-progress' },
    { id: 4, name: 'Done', class: 'done' },
    { id: 5, name: 'Cancelled', class: 'cancelled' }
  ];

  priorities = [
    { 
      id: 1, 
      name: 'URGENT', 
      class: 'urgent',
      icon: '<path d="M8 2L10 6H6L8 2Z" fill="#dc2626"/><path d="M8 14L6 10H10L8 14Z" fill="#dc2626"/>'
    },
    { 
      id: 2, 
      name: 'HIGH', 
      class: 'high',
      icon: '<path d="M8 4L10 8H6L8 4Z" fill="#ff6b00"/>'
    },
    { 
      id: 3, 
      name: 'MEDIUM', 
      class: 'medium',
      icon: '<circle cx="8" cy="8" r="3" fill="#fbbf24"/>'
    },
    { 
      id: 4, 
      name: 'LOW', 
      class: 'low',
      icon: '<path d="M8 12L6 8H10L8 12Z" fill="#22c55e"/>'
    },
    { 
      id: 5, 
      name: 'NONE', 
      class: 'none',
      icon: '<circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="2"/><line x1="3" y1="8" x2="13" y2="8" stroke="currentColor" stroke-width="2"/>'
    }
  ];
  estimatedTimes = [
    { id: 1, name: '15 mins', value: 15 },
    { id: 2, name: '30 mins', value: 30 },
    { id: 3, name: '1 hour', value: 60 },
    { id: 4, name: '2 hours', value: 120 },
    { id: 5, name: '4 hours', value: 240 }
  ];

  selectedExistingWorkItems:any =[];

addExistingItem(data: any) {
  const itemId = typeof data === 'object' && data.id ? data.id : data;
  
  const alreadySelected = this.selectedExistingWorkItems.some(id => id === itemId);
  if (!alreadySelected) {
    this.selectedExistingWorkItems.push(itemId); 
    const itemInResponse = this.responseData.find(item => item.id === itemId);
    if (itemInResponse) {
      itemInResponse.selected = true;
    }
  } else {
    this.selectedExistingWorkItems = this.selectedExistingWorkItems.filter(id => id !== itemId);
    const itemInResponse = this.responseData.find(item => item.id === itemId);
    if (itemInResponse) {
      itemInResponse.selected = false;
    }
  }
}



removeFromExistingList(data: any) {
  this.selectedExistingWorkItems = this.selectedExistingWorkItems.filter(
    item => item.id !== data.id
  );

  const itemInWorkItems = this.workItems.find(item => item.id === data.id);
  if (itemInWorkItems) {
    itemInWorkItems.selected = false;
  }
}

closeDialog(){
  this.dialogRef.close();
}

// subWorkitemList:any = [];

addWorkItem(){
  if(this.data?.type === 'SUB_WORK'){
    this.addSubWorkItem();
  }
  if(this.data?.type === 'EPIC'){
    this.addWorkItemEpic();
  }
}
addSubWorkItem() {
  let payload = {
    parentId: this.data.parentId,
    subWorkItemIdList: this.selectedExistingWorkItems 
  }
  this.projectService.createSubWorkItem(payload).subscribe({
    next: (res: any) => {
      
      this.dialogRef.close(res.data);
    }
  });
}
addWorkItemEpic(){
  let payload = {
    epicId: this.data.parentId,
    workItemIdList : this.selectedExistingWorkItems
  }
  this.projectService.addWorkitem(payload).subscribe({
    next: (res: any) => {
      this.dialogRef.close(res.data);
    },
    error: (err) => {
      console.error('Error adding workitem:', err);
    }
  });
}

  workItems: any[] = [];


    subWorkItems = [
    { id: 1, name: 'Create new',icon:'../../../../../../assets/images/work-management/plus_icon.png'},
    { id: 2, name: 'Add existing',icon:'../../../../../../assets/images/work-management/stack_icon.png'}
  ];

   relationsList = [
    { id: 1, name: 'Relates to',icon:'../../../../../../assets/images/work-management/stack_icon.png'},
    { id: 2, name: 'Duplicate of',icon:'../../../../../../assets/images/work-management/stack_icon.png'},
    { id: 2, name: 'Blocked by',icon:'../../../../../../assets/images/work-management/stack_icon.png'},
    { id: 2, name: 'Blocking',icon:'../../../../../../assets/images/work-management/stack_icon.png'}
  ];

  module :any= [ ];

  inboxFilters = [
  { id: 1, name: 'Assigned to me' },
    { id: 2, name: 'Created by me' },
    { id: 3, name: 'Subscribed by me'}
  ];
   
  inboxMoreItems = [
  { id: 1, name: 'Show unread', value:'SHOW_UNREAD' },
    { id: 2, name: 'Show archived', value:'SHOW_ARCHIVED' },
    // { id: 3, name: 'Show snoozed', value:'SHOW_SNOOZED' }
  ];

   inboxSnoozeItems = [
  { id: 1, name: '1 day' },
    { id: 2, name: '3 days' },
    { id: 3, name: '5 days'},
    { id: 3, name: '1 week'},
    { id: 3, name: '2 weeks'},
    { id: 3, name: 'Custom'}
  ];
   homeFilters = [
  { id: 1, name: 'All' },
    { id: 2, name: 'Work items' },
    { id: 3, name: 'Pages'},
    { id: 3, name: 'Projects'},
    
  ];

   projectViews = [
    {name:'Manual',value:'manual'},
    {name:'Name' ,value:'name'},
   { name:'Created date',value:'createddate'},
   { name:'Number of members',value:'numberofmembers'}
    
  ];
  increments=[
    {name:'Ascending',value:'ASC'},
    {name:'Descending',value:'DESC'}
  
  ];

  parents = [
    { 
      id: 'PMS-001', 
      title: 'Setup initial project structure',
      state: 'done',
      level: 0
    },
    { 
      id: 'PMS-002', 
      title: 'Implement user authentication',
      state: 'in-progress',
      level: 1
    },
    { 
      id: 'PMS-003', 
      title: 'Design database schema',
      state: 'todo',
      level: 1
    },
    { 
      id: 'PMS-004', 
      title: 'Create API endpoints',
      state: 'backlog',
      level: 2
    }
  ];

  filteredStatuses = this.data.states || [];
  filteredPriorities = [...this.priorities];
  filteredEstimatedTimes = this.data?.estimatedList || [];
  filteredAssignees = this.data.members || [];
  filteredLabels = this.data.label || [];
  filteredCycles = this.data.cycle || [];
  filteredModules = this.data.module || [];
  filteredParents = this.data.parent || [];
  filteredPages = this.data.page || [];

  weekDays = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
  currentDate = new Date();
  selectedDate: Date | null = null;
  calendarDays: Date[] = [];
  subWorkItemSearch:any;
  
  get currentMonth(): string {
    return this.currentDate.toLocaleString('default', { month: 'long' });
  }

  get currentYear(): number {
    return this.currentDate.getFullYear();
  }

  onSubWorkItemSearch(){
  if(!this.subWorkItemSearch){
    this.subWorkItemsList  = [...this.responseData];
  }
 
   this.subWorkItemsList = this.responseData.filter(item => {
    const searchLower = this.subWorkItemSearch.toLowerCase();
    return (
      item.title?.toLowerCase().includes(searchLower) ||
      item.displayBugNo?.toLowerCase().includes(searchLower)
    );
  });
  }

  

  onSearch() {
    const term = this.searchTerm.toLowerCase();
    
    this.filteredStatuses = (this.data.states || []).filter(item => 
      item.name.toLowerCase().includes(term)
    );
    
    this.filteredPriorities = this.priorities.filter(item => 
      item.name.toLowerCase().includes(term)
    );
    
    this.filteredAssignees = (this.data.members || []).filter(item => 
      item.name.toLowerCase().includes(term)
    );
    
    this.filteredLabels = (this.data.label || []).filter(item => 
      item.label.toLowerCase().includes(term)
    );
    
    this.filteredCycles = (this.data.cycle || []).filter(item => 
      item.title.toLowerCase().includes(term)
    );
    
    this.filteredModules = (this.data.module || []).filter(item => 
      item.title.toLowerCase().includes(term)
    );
    this.filteredPages = (this.data.page || []).filter(item => 
      item.title.toLowerCase().includes(term)
    );
    
    const allEstimates = (this.data.estimatedList || []);
    this.filteredEstimatedTimes = allEstimates.filter((est: any) => 
      this.formatEstimateDisplay(est).toLowerCase().includes(term)
    );
    
    this.filteredParents = this.parents.filter(item => 
      item.id.toLowerCase().includes(term) || 
      item.title.toLowerCase().includes(term)
    );
  }

   generateCalendarDays() {
    const firstDay = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth(), 1);
    const lastDay = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth() + 1, 0);
    
    const startingDay = firstDay.getDay();
    const monthLength = lastDay.getDate();

    this.calendarDays = [];
    
    for (let i = 0; i < startingDay; i++) {
      const day = new Date(firstDay);
      day.setDate(-startingDay + i + 1);
      this.calendarDays.push(day);
    }
    
    for (let i = 1; i <= monthLength; i++) {
      const day = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth(), i);
      this.calendarDays.push(day);
    }
    
    const remainingDays = 42 - this.calendarDays.length;
    for (let i = 1; i <= remainingDays; i++) {
      const day = new Date(lastDay);
      day.setDate(lastDay.getDate() + i);
      this.calendarDays.push(day);
    }
  }


  changeData(){
    this.dialogRef.close(this.selectedEndDate);
  }


  prevMonth() {
    this.currentDate.setMonth(this.currentDate.getMonth() - 1);
    this.generateCalendarDays();
  }

  nextMonth() {
    this.currentDate.setMonth(this.currentDate.getMonth() + 1);
    this.generateCalendarDays();
  }


  isToday(date: Date): boolean {
    const today = new Date();
    return date.toDateString() === today.toDateString();
  }

  isSelected(date: Date): boolean {
    return this.selectedDate?.toDateString() === date.toDateString();
  }

  isSameMonth(date: Date): boolean {
    return date.getMonth() === this.currentDate.getMonth();
  }

  selectDate(date: Date) {
    this.selectedDate = date;
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const dateString = `${year}-${month}-${day}`;
    this.dialogRef.close(dateString);
  }

  onItemSelect(item: any) {
    if (this.data.status === 'PRIORITY') {
      this.dialogRef.close(item);
    } else if (this.data.status === 'INBOX_MORE') {
      const isCurrentlySelected = this.isInboxMoreItemSelected(item);
      
      if (isCurrentlySelected) {
        this.dialogRef.close({ deselected: true, value: item.value });
      } else {
        this.dialogRef.close({ deselected: false, value: item.value });
      }
    } else {
      this.dialogRef.close(item);
    }
  }

  onModuleSelect(module:any){
    const isCurrentlySelected = this.isModuleSelected(module);
    
    if (isCurrentlySelected) {
      this.dialogRef.close(null);
    } else {
      let modules = {
        id: module.id,
        name: module.title
      }
      this.dialogRef.close(modules);
    }
  }
  onPageSelect(page:any){
    const isCurrentlySelected = this.isPageSelected(page);

    if (isCurrentlySelected) {
      this.dialogRef.close(null);
    } else {
      let pages = {
        id: page.id,
        name: page.title
      }
      this.dialogRef.close(pages);
    }
  }
  onCycleSelect(cycle:any){
    const isCurrentlySelected = this.isCycleSelected(cycle);
    
    if (isCurrentlySelected) {
      this.dialogRef.close(null);
    } else {
      let selectedCycle = {
        id: cycle.id,
        name: cycle.title
      }
      this.dialogRef.close(selectedCycle);
    }
  }
  onLabelSelect(label:any){
    if (!Array.isArray(this.data.selectedLabels)) {
      this.data.selectedLabels = [];
    }
    
    const existingIndex = this.data.selectedLabels.findIndex((l: any) => l.id === label.id);
    
    if (existingIndex > -1) {
      this.data.selectedLabels.splice(existingIndex, 1);
    } else {
      let selectedLabel = {
        id: label.id,
        name: label.label,
        color: label.color
      }
      this.data.selectedLabels.push(selectedLabel);
    }
  }

  isLabelSelected(label: any): boolean {
    const selectedLabels = this.data.selectedLabels || [];
    return selectedLabels.some((selected: any) => selected.id === label.id);
  }

  isAssigneeSelected(assignee: any): boolean {
    const selectedAssignees = this.data.selectedAssignees || [];
    return selectedAssignees.some((selected: any) => selected.id === assignee.memberId);
  }

  isStateSelected(state: any): boolean {
    const selectedState = this.data.selectedState;
    return selectedState && selectedState.id === state.id;
  }

  isPrioritySelected(priority: any): boolean {
    const selectedPriority = this.data.selectedPriority;
    return selectedPriority && selectedPriority.name === priority.name;
  }
  isEstimatedTimeSelected(estimate: any): boolean {
    const selectedEstimate = this.data.selectedEstimatedTime;
    if (!selectedEstimate) return false;

    const system = (this.data?.estimatedSystem || '').toUpperCase();
    if (system === 'TIME') {
      const sHr = parseInt(selectedEstimate?.hr ?? '0', 10) || 0;
      const sMin = parseInt(selectedEstimate?.min ?? '0', 10) || 0;
      const eHr = parseInt(estimate?.hr ?? '0', 10) || 0;
      const eMin = parseInt(estimate?.min ?? '0', 10) || 0;
      return sHr === eHr && sMin === eMin;
    }

    return selectedEstimate === estimate;
  }

  isCycleSelected(cycle: any): boolean {
    const selectedCycle = this.data.selectedCycle;
    return selectedCycle && selectedCycle.id === cycle.id;
  }

  isModuleSelected(module: any): boolean {
    const selectedModule = this.data.selectedModule;
    return selectedModule && selectedModule.id === module.id;
  }

  isPageSelected(page: any): boolean {
    const selectedPage = this.data.selectedPage;
    return selectedPage && selectedPage.id === page.id;
  }

  isInboxMoreItemSelected(item: any): boolean {
    const selectedMoreType = this.data.selectedMoreType;
    const isSelected = selectedMoreType && selectedMoreType === item.value;
    
    return isSelected;
  }
    isEpicEditSelected(item: any): boolean {
    const selectedMoreType = this.data.selectedMoreType;
    const isSelected = selectedMoreType && selectedMoreType === item.value;
    return isSelected;
  }

  onStateSelect(state:any){
    let selectedState = {
      id: state.id,
      name: state.name
    }
    this.dialogRef.close(selectedState);
  }

  formatEstimateDisplay(estimate: any): string {
    const system = (this.data?.estimatedSystem || '').toUpperCase();
    if (system === 'TIME') {
      const hr = parseInt(estimate?.hr ?? '0', 10) || 0;
      const min = parseInt(estimate?.min ?? '0', 10) || 0;
      if (hr === 0 && min > 0) return `${min}min`;
      if (min === 0 && hr > 0) return `${hr}hr`;
      if (hr > 0 && min > 0) return `${hr}hr ${min}min`;
      return '0min';
    }

    return String(estimate ?? '');
  }
  onAssigneeSelect(assignee:any){
    if (!Array.isArray(this.data.selectedAssignees)) {
      this.data.selectedAssignees = [];
    }
    
    const existingIndex = this.data.selectedAssignees.findIndex((a: any) => a.id === assignee.memberId);
    
    if (existingIndex > -1) {
      this.data.selectedAssignees.splice(existingIndex, 1);
    } else {
      let selectedAssignee = {
        id: assignee.memberId,
        name: assignee.name
      }
      this.data.selectedAssignees.push(selectedAssignee);
    }
  }
  onSubWorkItemSelection(item:any){
    let subWorkItem = {
      id: item.id,
      name: item.title
    }
    this.dialogRef.close(subWorkItem);
  }

  onProjectViewSelect(item: any, type: any) {
    if (type == 'VIEW') {
      this.selectedProjectView = item;
    } else {
      this.selectedAscending = item;
    }
    let data = { selectedViewType: this.selectedProjectView, ascendingType: this.selectedAscending }
    this.dialogRef.close(data);
  }

  addNewMember(){
    let payload = {
      name:this.newMemberName,
      email:this.newMemberEmail
    }
     this.dialogRef.close(payload);
  }



  onSubWorkItemSelect(item:any){
 this.dialogRef.close(item);
  }

  onRelationItemSelect(item:any){
 this.dialogRef.close(item);
  }

 
    pageLoader:boolean= false;
    projectId: any;
    responseData: any;
    subWorkItemsList:any
  //     states = [
  //   {
  //     title: 'Backlog',
  //     count: 6,
  //     isOpened: true,
  //     issues: [
  //       {
  //         id: 'ORRAP-534',
  //         title: 'Target Master Bulk upload',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Abhi',
  //         tag: 'Backend',
  //         state: 'Ready'
  //       },
  //       {
  //         id: 'ORRAP-514',
  //         title: 'Target Master issue',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Shiva',
  //         tag: 'Backend',
  //         state: 'Backend'
  //       },
  //     ]
  //   },
  //   {
  //     title: 'Todo',
  //     count: 6,
  //     isOpened: true,
  //     issues: [
  //       {
  //         id: 'ORRAP-534',
  //         title: 'Target Master Bulk upload',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Abhi',
  //         tag: 'Backend',
  //         state: 'Backend'
  //       },
  //       {
  //         id: 'ORRAP-534',
  //         title: 'Target Master Bulk upload',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Abhi',
  //         tag: 'Backend',
  //         state: 'Backend'
  //       },
  //       {
  //         id: 'ORRAP-534',
  //         title: 'Target Master Bulk upload',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Abhi',
  //         tag: 'Backend',
  //         state: 'Backend'
  //       },
  //       {
  //         id: 'ORRAP-534',
  //         title: 'Target Master Bulk upload',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Abhi',
  //         tag: 'Backend',
  //         state: 'Backend'
  //       },
  //       {
  //         id: 'ORRAP-514',
  //         title: 'Target Master issue',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Shiva',
  //         tag: 'Backend',
  //         state: 'Backend'
  //       },
  //     ]
  //   },
  //   {
  //     title: 'In Progress',
  //     count: 6,
  //     isOpened: true,
  //     issues: [
  //       {
  //         id: 'ORRAP-534',
  //         title: 'Target Master Bulk upload',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Abhi',
  //         tag: 'Backend',
  //         state: 'Backend'
  //       },
  //       {
  //         id: 'ORRAP-514',
  //         title: 'Target Master issue',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Shiva',
  //         tag: 'Backend',
  //         state: 'Backend'
  //       },
  //     ]
  //   },
  //   {
  //     title: 'Done',
  //     count: 6,
  //     isOpened: true,
  //     issues: [
  //       {
  //         id: 'ORRAP-534',
  //         title: 'Target Master Bulk upload',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Abhi',
  //         tag: 'Backend',
  //         state: 'Backend'
  //       },
  //       {
  //         id: 'ORRAP-514',
  //         title: 'Target Master issue',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Shiva',
  //         tag: 'Backend',
  //         state: 'Backend'
  //       },
  //     ]
  //   },
  //   {
  //     title: 'Cancelled',
  //     count: 6,
  //     isOpened: true,
  //     issues: [
  //       {
  //         id: 'ORRAP-534',
  //         title: 'Target Master Bulk upload',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Abhi',
  //         tag: 'Backend',
  //         state: 'Backend'
  //       },
  //       {
  //         id: 'ORRAP-514',
  //         title: 'Target Master issue',
  //         isError: false,
  //         date: '09/02/2025',
  //         assignee: 'Shiva',
  //         tag: 'Backend',
  //         state: 'Backend'
  //       },
  //     ]
  //   },
  // ];


onExistingWorkItemSelect(searchText: string = ''): void {
  this.pageLoader = true;
  const businessId = localStorage.getItem("businessId");

  const payload: any = {
    projectId: this.projectId,
    businessId: businessId,
  };

  if (searchText && searchText.trim() !== '') {
    payload.searchText = searchText.trim();
  }

  this.projectService.getAllWorkItems(payload).subscribe({
    next: (res: any) => {
      const apiItems = Array.isArray(res?.data) ? res.data : [];

      const normalizeId = (value: any): string | null => {
        if (value === null || value === undefined) {
          return null;
        }
        if (typeof value === 'object' && value !== null) {
          return value.id !== undefined && value.id !== null ? String(value.id) : null;
        }
        return String(value);
      };

      const selectedIds = new Set(
        (this.selectedExistingWorkItems || [])
          .map((entry: any) => normalizeId(entry))
          .filter((id: string | null): id is string => !!id)
      );

      const linkedIds = new Set<string>();

      if (this.data?.type === 'EPIC') {
        (this.epicWorkitemList || []).forEach((item: any) => {
          const id = normalizeId(item);
          if (id) {
            linkedIds.add(id);
          }
        });
      }

      if (this.data?.type === 'SUB_WORK') {
        (this.subWorkItemList || []).forEach((item: any) => {
          const id = normalizeId(item);
          if (id) {
            linkedIds.add(id);
          }
        });
      }

      const excludeIds = linkedIds.size > 0 ? linkedIds : null;

      const availableItems = excludeIds
        ? apiItems.filter((item: any) => {
            const id = normalizeId(item);
            return id ? !excludeIds.has(id) : true;
          })
        : apiItems;

      // Combine API data with selected items
      this.responseData = availableItems.map((item: any) => {
        const itemId = normalizeId(item);
        const alreadySelected = itemId ? selectedIds.has(itemId) : false;

        return {
          ...item,
          checked: alreadySelected,
          selected: alreadySelected
        };
      });
      this.subWorkItemsList = this.responseData;

      this.pageLoader = false;
    },
    error: () => {
      this.pageLoader = false;
    }
  });
}
getIconForPriority(priority: string | null | undefined): string {
  switch (priority) {
    case 'URGENT':
      return 'https://d2z9497xp8xb12.cloudfront.net/prod-images/614160c1752326546527fi_545684.svg';
    case 'HIGH':
      return 'https://d2z9497xp8xb12.cloudfront.net/prod-images/699554c1752326585037fi_483071 (1).svg';
    case 'MEDIUM':
      return 'https://d2z9497xp8xb12.cloudfront.net/prod-images/241336c1752326678945fi_483071 (2).svg';
    case 'LOW':
      return 'https://d2z9497xp8xb12.cloudfront.net/prod-images/627616c1752326716290fi_483071 (3).svg';
    case 'NONE':
      return 'https://d2z9497xp8xb12.cloudfront.net/prod-images/873930c1752326764416fi_11741047.svg';
    default:
      return 'assets/icons/priority-none.svg';
  }
}

getIconForState(state: string): string {
    switch (state) {
      case 'Cancelled': return 'https://d2z9497xp8xb12.cloudfront.net/prod-images/569422c1752326080397fi_4347434.svg';
      case 'Completed': return 'https://d2z9497xp8xb12.cloudfront.net/prod-images/413374c1752326128888fi_1442912.svg';
      case 'Backlog': return 'https://d2z9497xp8xb12.cloudfront.net/prod-images/291081c1752326307453fi_4785877.svg';
      case 'Unstarted': return 'https://d2z9497xp8xb12.cloudfront.net/prod-images/599798c1752326366897fi_481078.svg';
      case 'Started': return 'https://d2z9497xp8xb12.cloudfront.net/prod-images/415157c1752326421452fi_12595829 (1).svg';
      default: return 'https://d2z9497xp8xb12.cloudfront.net/prod-images/594903c1752326486747fi_12595829 (2).svg';
    }
  }

epicWorkitemList: any = [];
  getEpicWorkitemList(){
  const epicId = this.data?.parentId || this.data?.id;

  if (!epicId) {
    this.epicWorkitemList = [];
    this.onExistingWorkItemSelect();
    return;
  }

  this.projectService.getEpicWorkitemList(epicId).subscribe({
    next: (response: any) => {
      this.epicWorkitemList = Array.isArray(response?.data) ? response.data : [];
      this.onExistingWorkItemSelect();
    },
    error: (error) => {
      console.error('Error fetching epic workitem list:', error);
      this.epicWorkitemList = [];
      this.onExistingWorkItemSelect();
    }
  });
}

subWorkItemList: any = [];
getSubWorkItemList() {
  const parentId = this.data?.parentId || this.data?.id;

  if (!parentId) {
    this.subWorkItemList = [];
    this.onExistingWorkItemSelect();
    return;
  }

  this.projectService.getSubWorkItemByParentId(parentId).subscribe({
    next: (response: any) => {
      this.subWorkItemList = Array.isArray(response?.data) ? response.data : [];
      this.onExistingWorkItemSelect();
    },
    error: (error) => {
      console.error('Error fetching sub work items:', error);
      this.subWorkItemList = [];
      this.onExistingWorkItemSelect();
    }
  });
}

}
