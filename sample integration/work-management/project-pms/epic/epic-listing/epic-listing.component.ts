import { Component, EventEmitter, HostListener, Input, OnInit, Output } from '@angular/core';
import { CreateWorkitemComponent } from '../../work-item-pms/create-workitem/create-workitem.component';
import { MatDialog } from '@angular/material/dialog';
import { ActivatedRoute, Router } from '@angular/router';
import { WorkManagementService } from '../../../work-management.service';
import { EventEmmiterService } from 'simpo-components';
import { DetailWorkitemComponent } from '../../work-item-pms/detail-workitem/detail-workitem.component';

@Component({
  selector: 'app-epic-listing',
  templateUrl: './epic-listing.component.html',
  styleUrls: ['./epic-listing.component.scss']
})
export class EpicListingComponent implements OnInit {
  @Input() data: any;
  @Output() changeTab: EventEmitter<{ tab: string, data?: any, feature?: string }> = new EventEmitter();

  emitTabChange(tab: string, data?: any, feature?: string) {
    this.changeTab.emit({ tab, data, feature });
  }

  @HostListener('window:resize', ['$event'])
  getScreenSize(event?: any) {
    this.screenWidth = window.innerWidth;
  }

  screenWidth: any;
  response: any[] = [];
  originalResponse: any[] = [];
  loading: boolean = false;
  selectTab: string = 'TABLE';
  filterGroups: { key: string, value: any[] }[] = [];
  searchText: string = '';
  displayedColumns: string[] = ['Epic', 'state', 'priority', 'assignee', 'label', 'start_date', 'due_date', 'created_on', 'updated_on', 'link', 'attachment'];
  skeletonColumns: string[] = ['Epic', 'state', 'priority', 'assignee', 'label', 'start_date', 'due_date', 'created_on', 'updated_on', 'link', 'attachment'];
  feature: any = {};
  projectSettingsData: any;
  selectedName: any;
  selectedId: any;
  selectedFeature: any;
  projectId: any;
  projectname: any;
  projectStates:any;
  




  // states/sub-states used to render LIST/KANBAN columns
  stateList: any[] = [];
  subStateList: any[] = [];
  states: any[] = [];
  secondTabResponse: any[] = [];


  isDragging: boolean = false;
  activeDropdownIndex: number | null = null;
  selectedItemForDelete: any = null;

  constructor(
    private matDialog: MatDialog,
    private route: ActivatedRoute,
    private projectService: WorkManagementService,
    private eventService: EventEmmiterService,
    private router: Router,

  ) {
  }

  ngOnInit(): void {
    this.getProjectSettingsData();
    this.getAllSubStatesList();
  }
  getAllSubStatesList(): void {
    const projectId = localStorage.getItem('projectId');
    this.projectService.getAllSubStatesList(projectId).subscribe({
      next: (res: any) => {
        this.stateList = res?.data || [];
        this.subStateList = this.stateList.flatMap((s: any) => (s.subStates || []).map((sub: any) => ({ ...sub, stateName: s.name, stateId: s.id })));

        if (!this.subStateList.length) {
          this.subStateList = this.stateList.map((s: any) => ({ id: s.id, name: s.name, stateId: s.id }));
        }
        this.getEpicListing();
      },
      error: () => {

        this.getEpicListing();
      }
    });
  }

  buildStatesFromResponse(): void {
    const groupedData: { [key: string]: any[] } = {};
    for (const item of this.response || []) {
      const subStateId = item.state?.id;

      const key = subStateId || item.state?.name || 'no-state';
      if (!groupedData[key]) groupedData[key] = [];
      groupedData[key].push(item);
    }

    // Build secondTabResponse based on known subStateList (so empty columns show too)
    if (this.subStateList && this.subStateList.length) {
      this.secondTabResponse = this.subStateList.map(sub => ({
        id: sub.id,
        name: sub.name || sub.stateName || 'No State',
        items: groupedData[sub.id] || [],
        isOpened: false,
        isMinimized: false
      }));
    } else {

      this.secondTabResponse = Object.keys(groupedData).map(k => ({ id: k, name: k, items: groupedData[k], isOpened: false, isMinimized: false }));
    }

    this.states = this.secondTabResponse;
  }

  // --- Template action handlers (lightweight implementations) ---
  onSearchChange(): void {
    const q = (this.searchText || '').trim().toLowerCase();
    if (!q) {
      this.response = [...this.originalResponse];
    } else {
      this.response = this.originalResponse.filter(i => (i.title || '').toLowerCase().includes(q) || (i.displayBugNo || '').toLowerCase().includes(q));
    }
    this.buildStatesFromResponse();
  }

  closeStateCard(state: any): void {

    state.isOpened = !state.isOpened;
  }

  minimizeState(state: any, event?: MouseEvent): void {
    if (event) {
      event.stopPropagation?.();
    }
    state.isMinimized = !state.isMinimized;
  }

  onDragStarted(): void {
    this.isDragging = true;
  }

  onDragEnded(): void {
    this.isDragging = false;
  }

  onDragMoved(event: any): void {
    // placeholder: could be used for visual feedback while dragging
  }

  onWorkItemClick(item: any, event?: MouseEvent): void {
    // prevent click-through when interacting with drag handlers
    event?.stopPropagation?.();
    this.detailWorkitem(item);
  }

  refreshWorkItems(): void {
    this.getAllSubStatesList();
  }

  openFilterMenu(): void {
    // placeholder for opening filters - keeping minimal
    console.log('openFilterMenu');
  }

  getInitials(name: string): string {
    if (!name) return '';
    return name.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase();
  }

  getInitial(name: string): string {
    if (!name) return '';
    return name.trim().charAt(0).toUpperCase();
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

  detailWorkitem(item: any) {
    const dialogRef =this.matDialog.open(DetailWorkitemComponent, {
            width: '70%',
            //  width: '45%',
            height: '100%',
            panelClass: 'custom-dialog',
            position: { top: '0', right: '0' },
            data: { item, projectData: this.data, fromScreen:'EPIC' }
          });
          dialogRef.afterClosed().subscribe(res => {
                this.getEpicListing();
              if (res && res.updatedItem) {
                this.refreshDataBasedOnContext();
              }
            
          });
  }

  onStateEdit(event: MouseEvent, item: any) {
    event?.stopPropagation?.();
    console.log('onStateEdit', item);
  }

  onPriorityEdit(event: MouseEvent, item: any) {
    event?.stopPropagation?.();
    console.log('onPriorityEdit', item);
  }

  onLabelEdit(event: MouseEvent, item: any) {
    event?.stopPropagation?.();
    console.log('onLabelEdit', item);
  }

  onAssigneeEdit(event: MouseEvent, item: any) {
    event?.stopPropagation?.();
    console.log('onAssigneeEdit', item);
  }

  onModuleEdit(event: MouseEvent, item: any) {
    event?.stopPropagation?.();
    console.log('onModuleEdit', item);
  }

  onCycleEdit(event: MouseEvent, item: any) {
    event?.stopPropagation?.();
    console.log('onCycleEdit', item);
  }

  onStartDateEdit(event: MouseEvent, item: any) {
    event?.stopPropagation?.();
    console.log('onStartDateEdit', item);
  }

  onEndDateEdit(event: MouseEvent, item: any) {
    event?.stopPropagation?.();
    console.log('onEndDateEdit', item);
  }

  // --- Filters & chips ---
  removeFilter(key: string, item: any): void {
    // minimal: remove from filterGroups
    this.filterGroups = this.filterGroups.map(g => ({ ...g, value: g.value.filter((v: any) => v !== item) })).filter(g => g.value.length > 0);
  }

  clearAll(): void {
    this.filterGroups = [];
  }

  toggleMoreOptions(event: MouseEvent, index: number): void {
    event?.stopPropagation?.();
    this.activeDropdownIndex = this.activeDropdownIndex === index ? null : index;
  }

  openDeleteModal(item: any) {
    this.selectedItemForDelete = item;
  }

  confirmDelete() {
    if (!this.selectedItemForDelete) return;
    const id = this.selectedItemForDelete.id || this.selectedItemForDelete.displayBugNo;
    this.response = this.response.filter(i => (i.id || i.displayBugNo) !== id);
    this.originalResponse = this.originalResponse.filter(i => (i.id || i.displayBugNo) !== id);
    
    this.selectedItemForDelete = null;
    this.buildStatesFromResponse();
  }

  getAssigneeNames(assignees: any[]): string {
    if (!assignees || !assignees.length) return '';
    return assignees.map(a => a?.name || a).join(', ');
  }

  getLabelsTooltip(labels: any[]): string {
    if (!labels || !labels.length) return '';
    return labels.map(l => l?.name || l?.label || l).join(', ');
  }

  // --- Drag & drop helpers (lightweight) ---
  getConnectedDropLists(): string[] {
    return this.secondTabResponse.map((s, i) => `state-${i}`);
  }

  drop(event: any, targetState: any) {
    const item = event.item?.data;
    const prevState = event.previousContainer?.data;
    if (!item) return;
    if (prevState && prevState !== targetState) {
      prevState.items = prevState.items.filter((it: any) => (it.id || it.displayBugNo) !== (item.id || item.displayBugNo));
      targetState.items = targetState.items || [];
      targetState.items.splice(event.currentIndex, 0, item);
    }
  }

  addworkitemThroughDefaultState(state: any) {
    const newItem = {
      id: `epic-${Math.random().toString(36).slice(2, 9)}`,
      displayBugNo: `EPIC-${(this.response.length + 1)}`,
      title: 'New Epic',
      assignee: [],
      label: [],
      modules: null,
      cycle: null
    };
    state.items = state.items || [];
    state.items.unshift(newItem);
    this.response.unshift(newItem);
    this.originalResponse.unshift(newItem);
  }


  createEpic() {
    const dialogConfig = {
      width: this.screenWidth > 992 ? '50%' : '55%',
      height: 'fit-content',
      maxWidth: '100vw',
      position: { top: '10vh' },
      data: { mode: 'EPIC', projectData: this.projectSettingsData }
    };

    const dialog = this.matDialog.open(CreateWorkitemComponent, dialogConfig);
    dialog.afterClosed().subscribe(() => {
        this.getEpicListing();
      this.refreshDataBasedOnContext();
    });
  }

  refreshDataBasedOnContext() { }


  getEpicListing(){
     const projectId = localStorage.getItem('projectId');
     const businessId = localStorage.getItem("businessId");
    
    let payload = {
      businessId: businessId,
      projectId: projectId,
    }

    this.loading = true;
    this.projectService.getEpicListing(payload).subscribe({
      next: (res: any) => {
        this.response = res?.data || [];
        this.originalResponse = [...this.response];
        this.buildStatesFromResponse();
        this.loading = false;
          this.workItemList = Array.isArray(res?.data) ? res.data : (res?.data?.workitemList || []);
      },
      error: () => {
        this.loading = false;
      }
    });
  }

  switchTab(res: any) {
    this.selectTab = res;
  }

  getProjectSettingsData() {
    let businessId = localStorage.getItem("businessId");
    const projectId = localStorage.getItem('projectId');
    this.projectService.getProjectSettingsData(projectId, businessId).subscribe(
      (res: any) => {
        this.projectSettingsData = res.data[0];
        this.projectname = this.projectSettingsData?.projectName;
        this.projectStates = this.projectSettingsData?.states;
        this.feature = this.projectSettingsData?.features;
        // this.updateDisplayedColumns();
        

      }
    )
  }

  workItemList: any[] = [];

  getCompletedCount(issue: any): number {
    if (!issue.workItemList || !issue.workItemList.length) return 0;
    return issue.workItemList.filter(item => item?.state?.name === 'Completed').length;
  }
}
