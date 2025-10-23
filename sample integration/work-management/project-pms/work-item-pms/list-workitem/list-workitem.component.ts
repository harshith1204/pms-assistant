import { Component, HostListener, OnDestroy, ViewChild, ElementRef } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { CreateWorkitemComponent } from '../create-workitem/create-workitem.component';
import { DetailWorkitemComponent } from '../detail-workitem/detail-workitem.component';
import { FilterPmsComponent } from '../../filter-pms/filter-pms.component';
import { DisplayPmsComponent } from '../../display-pms/display-pms.component';
import { ActivatedRoute, Router } from '@angular/router';
import { WorkManagementService } from '../../../work-management.service';
import { MatDatepickerInputEvent } from '@angular/material/datepicker';
import { PopupPmsComponent } from '../../popup-pms/popup-pms.component';
import { CdkDragDrop, moveItemInArray, transferArrayItem, CdkDragMove } from '@angular/cdk/drag-drop';
import { EventEmmiterService } from '../../../../../../services/event-emmiter.service';


interface PriorityItem {
  name: string;
  icon: string;
  class: string;
  checked: boolean;
}
@Component({
  selector: 'app-list-workitem',
  templateUrl: './list-workitem.component.html',
  styleUrls: ['./list-workitem.component.scss']
})
export class ListWorkitemComponent implements OnDestroy {

  screenWidth: any;
  projectId: any;
  projectname: any;
  response: any;
  @HostListener('window:resize', ['$event'])
  getScreenSize(event?: any) {
    this.screenWidth = window.innerWidth;
  }

  @HostListener('window:beforeunload', ['$event'])
  onBeforeUnload(event?: any) {
    window.localStorage.removeItem('WORK_ITEM_FILTER');
  }

  showWorkItemForm = false;
  loading = false;

  hoveredIndex: number | null = null;
  hoveredDate: number | null = null;
  hoveredCell: { row: number | null; date: any } = { row: null, date: null };
    filters: { [key: string]: any[] } = {};
   filterGroups: { key: string, value: any[] }[] = [];
     filtersPayload: any;

  constructor(
    private matDialog: MatDialog,
    private route: ActivatedRoute,
    private projectService: WorkManagementService,
    private eventService: EventEmmiterService,
    private router: Router,
    
  ) {
  }

  displayedColumns: string[] = ['workItem', 'state', 'priority', 'assignee', 'start_date', 'due_date' , 'label', 'module', 'cycle','created_on', 'updated_on', 'attachment', 'sub_work_item'];

  flattenedIssues: any = [];
  listWorkitem: any[] = [];
  preservedSelectedWorkItemId: string | null = null;
  preservedWindowScroll: number = 0;
  preservedMainScroll: number = 0;
  preservedTableScroll: number = 0;
  preservedKanbanScroll: number = 0;
  selectedWorkItem: any = null;
  currentDate = new Date();
  calendarDays: any[] = [];
  months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  weekDays = ['Su', 'M', 'T', 'W', 'Th', 'F', 'Sa'];

  screen:any;
  isMyprojects:boolean = false;
  staffListresp:any;
  selectedmembers:any[]=[];
  selectedAssignees: any[] = [];
  selectedLeads: any[] = [];
  selectedBusinessMembers:any[]=[];
  selectedmentions:any[]=[];
  selectedCreatedBy:any[]=[];
  selectedPriorities:any[]=[];
  selectedStates:any[]=[];
  projectStates:any;
   projectLablels:any;
  selectedViewType: any;
  ascendingType: any;
  projectData: any;
  projectCycles:any;
  selectedCycles:any[]=[];
  projectModules:any;
  selectedModules:any[]=[];
  selectedLabels:any[]=[];
  customStartDate1:any;
  customEndDate:any;
  states: any[] = [];
  feature: any;

  // Drag and scroll properties
  @ViewChild('kanbanContainer', { static: false }) kanbanContainer!: ElementRef;
  autoScrollSpeed = 2;
  scrollThreshold = 100;

  currentSelectedModuleId: any = null;
  
  currentViewId: any = null;
  isInViewContext: boolean = false;

  moduleList: any[] = [];
  cycleList: any[] = [];
  labelsList: any[] = [];
  membersList: any[] = [];

  ngOnInit() {

  this.eventService.workItemTabChange.subscribe((event: any) => {
    if (event) {
      this.tabChange(event);
    }
  });
        this.route.queryParams.subscribe(params => {
      this.projectId = params['projectId'] || localStorage.getItem('projectId');
    //  this.projectId = localStorage.getItem('projectId');
      this.currentSelectedModuleId = params['moduleId'] || null;
    this.staffListresp = JSON.parse(String(localStorage.getItem('staffList')));
      this.getProjectSettingsData();
    this.getAllSubStatesList();
      const postData = JSON.parse(window.localStorage.getItem('WORK_ITEM_FILTER') || '[]');
      this.getAppliedFilters(postData);
  
    
      // this.showButton();
    });

    this.selectedTab = 'WORKITEM_TAB';
    //  const workItemTab = window.localStorage.getItem('WORKITEM_VIEW');
    // this.selectTab = workItemTab || 'FIRST_TAB';
    this.route.queryParams.subscribe(params => {
      this.selectedTab = params['tab'] || 'WORKITEM_TAB';
      this.projectId = params['projectId'] || this.projectId;
    });
  const navigation = this.router.getCurrentNavigation();
  const state = navigation?.extras?.state || history.state;

    if (state && state.tab && state.data && state.feature) {
      
        this.tabChange({
          tab: state.tab,
          data: state.data,
          feature: state.feature
        });
      
      // if (state.feature === 'VIEW') {
      //   this.handleTabChange({
      //     tabIndex: state.tab,
      //     data: state.data
      //   });
      // } else if(state.feature === 'YOUR_WORK'){
      //   // this.yourWorkTabChange()
      // }
      // else {
      //   this.tabChange({
      //     tab: state.tab,
      //     data: state.data,
      //     feature: state.feature
      //   });
      // }
    }
  this.route.queryParams.subscribe(params => {
    this.projectId = params['projectId'] || state?.projectId;
  });

    this.generateCalendar();
    this.flattenedIssues = this.states.flatMap(state =>
      state.issues.map(issue => ({
        ...issue,
        state: state.title
      }))
    );
    this.generateHorizontalCalendar();
    // this.projectDetailData();
    // this.showButton();
    this.getAllCycles();
    this.getProjectMembers();
    this.getAllLabels();
    this.getallModules();
    this.getProjectMemberDetails();

    this.route.queryParams.subscribe(params => {
    const workitemId = params['workitemId'];
    if (workitemId) {
      this.handleWorkitemFromUrl(workitemId);
    }
  });
  }


  
  allWorkitems: any[] = [];
  findWorkitemById(id: string) {
    this.getAllWorkItemsAPI();
    this.allWorkitems = this.originalResponse;
    return this.allWorkitems?.find(w => w.id === id);
  }

  openWorkitemDialog(item: any) {
    const dialogRef = this.matDialog.open(DetailWorkitemComponent, {
      width: '45%',
      height: '100%',
      panelClass: 'custom-dialog',
      position: { top: '0', right: '0' },
      data: { item, projectData: this.projectSettingsData, fromScreen: 'WORK_ITEM' },
    });

    dialogRef.afterClosed().subscribe((res) => {
      if (res && res.updatedItem) {
        this.mergeUpdatedItem(res.updatedItem);
        this.applySelectedWorkItemHighlight();
      }
      // Do not refresh data when there are no changes; preserve current list state

      this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { workitemId: null },
        queryParamsHandling: 'merge',
      });
    });
  }

  handleWorkitemFromUrl(workitemId: string) {
  if (this.originalResponse?.length) {
    const item = this.originalResponse.find(w => w.id === workitemId);
    if (item) this.openWorkitemDialog(item);
  } else {

    this.getAllWorkItemsAPI(undefined, workitemId);
  }
}

  updateDisplayedColumns() {
  this.displayedColumns = ['workItem', 'state', 'priority', 'assignee', 'start_date', 'due_date'];
  
  if (this.feature?.modules) {
    this.displayedColumns.push('module');
  }
  
  if (this.feature?.cycles) {
    this.displayedColumns.push('cycle');
  }
  
  this.displayedColumns.push('label',  'created_on', 'updated_on', 'attachment', 'sub_work_item');
}
  generateHorizontalCalendar() {
    const startDate = new Date(2025, 0, 1);
    const endDate = new Date(2025, 11, 31);

    let currentDate = new Date(startDate);
    this.calendarDays = [];

    while (currentDate <= endDate) {
      this.calendarDays.push({
        month: this.months[currentDate.getMonth()],
        date: currentDate.getDate(),
        day: this.weekDays[currentDate.getDay()],
        fullDate: new Date(currentDate),
        isToday: this.isSameDay(currentDate, this.currentDate),
        monthYear: `${this.months[currentDate.getMonth()]} ${currentDate.getFullYear()}`
      });

      currentDate.setDate(currentDate.getDate() + 1);
    }
  }

  scrollToToday() {
    const today = this.calendarDays.findIndex(day => day.isToday);
    if (today > -1) {
      setTimeout(() => {
        const calendarContainer = document.querySelector('.horizontal-calendar');
        const todayColumn = document.querySelector('.date-column.today');
        if (calendarContainer && todayColumn) {
          const scrollLeft = (todayColumn as HTMLElement).offsetLeft - calendarContainer.clientWidth / 2;
          calendarContainer.scrollTo({ left: scrollLeft, behavior: 'smooth' });
        }
      }, 100);
    }
  }

  isSameDay(date1: Date, date2: Date): boolean {
    return date1.getDate() === date2.getDate() &&
      date1.getMonth() === date2.getMonth() &&
      date1.getFullYear() === date2.getFullYear();
  }

  isStateCardOpened: boolean = false;
  selectedTab: any;
  groupedDates: number[][] = [];
  selectedDay: string = 'M 23';
  selectTab : any;

  changeTab(res: any) {
    this.selectedTab = res;
  }
  switchTab(res: any) {
    this.selectTab = res;
    this.saveLayout(res);
  }
 
  closeStateCard(res: any) {
    res.isOpened = !res.isOpened;
  }

  minimizeState(res: any, event: Event) {
    event.stopPropagation();
    res.isMinimized = !res.isMinimized;
  }

  index = 0;

  year: number = 2025;
  month: number = 5;
  weekdays: string[] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  calendar: (number | null)[][] = [];

  get monthName(): string {
    return new Date(this.year, this.month).toLocaleString('default', { month: 'long' });
  }

  generateCalendar() {
    const firstDay = new Date(this.year, this.month, 1);
    const lastDay = new Date(this.year, this.month + 1, 0);
    const startDay = (firstDay.getDay() + 6) % 7;
    const daysInMonth = lastDay.getDate();

    let dayCounter = 1;
    this.calendar = [];

    for (let i = 0; i < 6; i++) {
      const week: (number | null)[] = [];

      for (let j = 0; j < 7; j++) {
        if ((i === 0 && j < startDay) || dayCounter > daysInMonth) {
          week.push(null);
        } else {
          week.push(dayCounter++);
        }
      }

      this.calendar.push(week);
    }
  }

  prevMonth() {
    if (this.month === 0) {
      this.month = 11;
      this.year--;
    } else {
      this.month--;
    }
    this.generateCalendar();
  }

  nextMonth() {
    if (this.month === 11) {
      this.month = 0;
      this.year++;
    } else {
      this.month++;
    }
    this.generateCalendar();
  }

  showInlineForm: boolean = false;
  showTemplates: boolean = false;
  newWorkItem = {
    id: '',
    title: '',
    duration: '2d'
  };

  startInlineForm() {
    this.showInlineForm = true;
    this.newWorkItem = {
      id: this.generateWorkItemId(),
      title: '',
      duration: '2d'
    };

    setTimeout(() => {
      const titleInput = document.querySelector('.work-item-title-input') as HTMLInputElement;
      if (titleInput) {
        titleInput.focus();
      }
    }, 50);
  }

  onInlineKeyPress(event: KeyboardEvent) {
    if (event.key === 'Enter' && this.newWorkItem.title.trim()) {
      this.saveInlineWorkItem();
    } else if (event.key === 'Escape') {
      this.cancelInlineForm();
    }
  }

  saveInlineWorkItem() {
    if (this.newWorkItem.title.trim()) {

      const newItem = {
        id: this.newWorkItem.id,
        title: this.newWorkItem.title,
        duration: this.newWorkItem.duration
      };
      this.workItems.push(newItem);


      const backlogState = this.states.find(state => state.title === 'Backlog');
      if (backlogState) {
        backlogState.issues.push({
          id: this.newWorkItem.id,
          title: this.newWorkItem.title,
          isError: false,
          date: new Date().toLocaleDateString(),
          assignee: 'Unassigned',
          tag: 'New',
          state: 'Backlog'
        });
        backlogState.count = backlogState.issues.length;
      }

      this.newWorkItem = {
        id: this.generateWorkItemId(),
        title: '',
        duration: '2d'
      };


      setTimeout(() => {
        const titleInput = document.querySelector('.work-item-title-input') as HTMLInputElement;
        if (titleInput) {
          titleInput.focus();
        }
      }, 50);


      setTimeout(() => {
        const cells = document.querySelectorAll('.task-cell');
        cells.forEach(cell => {
          (cell as HTMLElement).style.height = '48px';
        });
      }, 0);
    }
  }

  cancelInlineForm() {
    this.showInlineForm = false;
    this.newWorkItem = {
      id: '',
      title: '',
      duration: '2d'
    };
  }

  selectedName: any;
  selectedId: any;
  workitemData: any;
  createWorkItem(): void {
    const dialogConfig = {
      width: this.screenWidth > 992 ? '52%' : '57%',
      height: 'fit-content',
      maxWidth: '100vw',
      position: { top: '10vh' },
      data: { mode: 'WORK_ITEM', projectData: this.projectSettingsData , selectedId: this.selectedId, selectedName: this.selectedName, feature: this.selectedFeature }
    };

    const dialog = this.matDialog.open(CreateWorkitemComponent, dialogConfig);
    dialog.afterClosed().subscribe(() => {
      this.refreshDataBasedOnContext();
    });

  }

  openTemplates(): void {
    const dialogConfig = {
      width: this.screenWidth > 992 ? '50%' : '55%',
      height: 'fit-content',
      maxWidth: '100vw',
      position: { top: '8vh' },
      data: { mode: 'TEMPLATES', projectData: this.projectSettingsData }
    };

    const dialog = this.matDialog.open(CreateWorkitemComponent, dialogConfig);
    dialog.afterClosed().subscribe(() => {
      this.refreshDataBasedOnContext();
    });
  }

  private normalizeGeneratedResult(result: any): any {
    // If already wrapped as template, return as-is
    if (result?.template) {
      return result;
    }

    const normalized: any = { ...result };
    let text: string | undefined = (result?.description ?? result?.content);

    if (typeof text === 'string') {
      // Try to extract JSON from a code fence
      const fenceMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
      const inside = fenceMatch ? fenceMatch[1] : text;

      // Attempt to parse JSON object within
      try {
        const start = inside.indexOf('{');
        const end = inside.lastIndexOf('}');
        if (start !== -1 && end !== -1 && end > start) {
          const jsonSlice = inside.substring(start, end + 1);
          const parsed = JSON.parse(jsonSlice);
          if (parsed && typeof parsed === 'object') {
            if (parsed.title) normalized.title = parsed.title;
            if (parsed.description) normalized.description = parsed.description;
          }
        }
      } catch {
        // ignore parse errors; fall back to raw text
      }

      // If description still missing but we had a code fence, strip the fences for display
      if (!normalized.description && fenceMatch) {
        normalized.description = inside;
      }

      // Fix titles that came in as the fence tag
      if (normalized.title === '```json' || normalized.title === '```') {
        // Use first non-empty line from parsed description as a fallback title
        const d = String(normalized.description || text);
        const firstLine = d.split(/\r?\n/).find(l => l.trim().length > 0) || '';
        normalized.title = firstLine.slice(0, 120);
      }
    }

    return normalized;
  }





  workItems = [
    { id: 'WMS-2', title: 'UI', duration: '2d' },
    { id: 'WMS-1', title: 'wms', duration: '3d' },
    { id: 'WMS-3', title: 'sprint-21', duration: '1w' }
  ];

  getDayLabel(date: number): string {
    const days = ['Su', 'M', 'T', 'W', 'Th', 'F', 'Sa'];
    const dateObj = new Date(2025, 5, date); // June 2025
    return days[dateObj.getDay()];
  }

  generateWorkItemId(): string {
    const prefix = 'HELLO-';
    const existingIds = this.workItems.map(item => item.id);
    let counter = 1;

    while (existingIds.includes(`${prefix}${counter}`)) {
      counter++;
    }

    return `${prefix}${counter}`;
  }


  updateWorkItemTitle(event: any) {
    this.newWorkItem.title = event.target.value;
  }


  addTask(workItem: any, day: any) {
    this.startInlineForm();
  }
  priorities = [
    {
      id: 1,
      name: 'Urgent',
      class: 'urgent',
      icon: '<path d="M8 2L10 6H6L8 2Z" fill="#dc2626"/><path d="M8 14L6 10H10L8 14Z" fill="#dc2626"/>'
    },
    {
      id: 2,
      name: 'High',
      class: 'high',
      icon: '<path d="M8 4L10 8H6L8 4Z" fill="#ff6b00"/>'
    },
    {
      id: 3,
      name: 'Medium',
      class: 'medium',
      icon: '<circle cx="8" cy="8" r="3" fill="#fbbf24"/>'
    },
    {
      id: 4,
      name: 'Low',
      class: 'low',
      icon: '<path d="M8 12L6 8H10L8 12Z" fill="#22c55e"/>'
    },
    {
      id: 5,
      name: 'None',
      class: 'none',
      icon: '<circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="2"/><line x1="3" y1="8" x2="13" y2="8" stroke="currentColor" stroke-width="2"/>'
    }
  ];

  getPriorityClass(priority: string): string {
    switch (priority.toLowerCase()) {
      case 'urgent':
        return 'priority-urgent';
      case 'high':
        return 'priority-high';
      case 'medium':
        return 'priority-medium';
      case 'low':
        return 'priority-low';
      case 'none':
        return 'priority-none';
      default:
        return '';
    }
  }



  setHoveredCell(row: number | null, date: any) {
    if (row === null || date === null) {
      this.hoveredCell = { row: null, date: null };
      this.hoveredIndex = null;
    } else {
      this.hoveredCell = { row, date };
      this.hoveredIndex = row;
    }
  }

  // Add missing setHoveredDate method
  setHoveredDate(date: number | null) {
    this.hoveredDate = date;
  }
  wholeData: any;
  // detailWorkitem(item: any) {
  //   if (item) {
  //     try {
  //       this.preservedSelectedWorkItemId = item.id;
  //       this.preservedWindowScroll = window.scrollY || window.pageYOffset || 0;
  //       const mainEl = document.querySelector('.main_container') as HTMLElement;
  //       this.preservedMainScroll = mainEl ? mainEl.scrollTop : 0;
  //       const tableEl = document.querySelector('.table-wrapper') as HTMLElement;
  //       this.preservedTableScroll = tableEl ? tableEl.scrollTop : 0;
  //       this.preservedKanbanScroll = this.kanbanContainer?.nativeElement?.scrollLeft || 0;
  //     } catch (e) {
  //     }

  //     const dialogRef =this.matDialog.open(DetailWorkitemComponent, {
  //        width: '45%',
  //       height: '100%',
  //       panelClass: 'custom-dialog',
  //       position: { top: '0', right: '0' },
  //       data: { item, projectData: this.projectSettingsData, fromScreen:'WORK_ITEM' }
  //     });
  //     dialogRef.afterClosed().subscribe(res => {
  //         if (res && res.updatedItem) {
  //           this.mergeUpdatedItem(res.updatedItem);
  //           this.applySelectedWorkItemHighlight();
  //         } else {
  //           this.refreshDataBasedOnContext();
  //         }
        
  //     });
  //   } else {
  //     console.warn('Tried to open dialog with undefined item');
  //   }
    
    
  // }
  detailWorkitem(item: any) {
    if (!item) {
      console.warn('Tried to open dialog with undefined item');
      return;
    }

    try {
      this.preservedSelectedWorkItemId = item.id;
      this.preservedWindowScroll = window.scrollY || window.pageYOffset || 0;
      const mainEl = document.querySelector('.main_container') as HTMLElement;
      this.preservedMainScroll = mainEl ? mainEl.scrollTop : 0;
      const tableEl = document.querySelector('.table-wrapper') as HTMLElement;
      this.preservedTableScroll = tableEl ? tableEl.scrollTop : 0;
      this.preservedKanbanScroll = this.kanbanContainer?.nativeElement?.scrollLeft || 0;
    } catch (e) {}

    // Update URL with workitemId - the query param subscription will handle opening the dialog
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { workitemId: item.id },
      queryParamsHandling: 'merge',
    });

    // Removed: this.openWorkitemDialog(item) - Dialog is now opened by query param subscription
  }


filterPayloadWorkitem:any;
  openFilterMenu() {
    const transformedFilters = this.transformFiltersForDialog();
    
    const dialogRef = this.matDialog.open(FilterPmsComponent, {
      width: '20%',
      height: '67%',
      data: { screen: 'WORK_ITEM', projectData: this.projectSettingsData ,selectedFilters: transformedFilters, status: 'WORK_ITEM_FILTER' },
      position: { top: '21vh', right: '60vh'},
    });

    dialogRef.componentInstance.dataChanged.subscribe((cleanedPayload: any) => {
       window.localStorage.setItem('WORK_ITEM_FILTER', JSON.stringify(cleanedPayload));
    
     this.getAppliedFilters(cleanedPayload);
 
    });
  }

  getAppliedFilters(cleanedPayload:any){     
      this.updateFiltersFromPayload(cleanedPayload);
      this.filterPayloadWorkitem = {
        ...(cleanedPayload?.startDate && { startDate: cleanedPayload.startDate }),
        ...(cleanedPayload?.endDate && { endDate: cleanedPayload.endDate }),
        ...(cleanedPayload?.state?.length && { stateId: cleanedPayload.state.map(s => s.id) }),
        ...(cleanedPayload?.lead?.length && { leadId: cleanedPayload.lead.map(s => s.id) }),
        ...(cleanedPayload?.priority?.length && { priority: cleanedPayload.priority }),
        ...(cleanedPayload?.assignee?.length && { assigneeId: cleanedPayload.assignee.map(s => s.id) }),
        ...(cleanedPayload?.label?.length && { labelId: cleanedPayload.label.map(s => s.id) }),
        ...(cleanedPayload?.cycle?.length && { cycleId: cleanedPayload.cycle.map(s => s.id) }),
        ...(cleanedPayload?.modules?.length && { moduleId: cleanedPayload.modules.map(s => s.id) }),
        ...(cleanedPayload?.createdBy?.length && { createdById: cleanedPayload.createdBy.map(s => s.id) })
      };
      this.updateFilterGroups();
     this.refreshDataWithFilters(); 
  }



  onIssueStartDateSelection(event: MatDatepickerInputEvent<Date>) {
    
  }

  openDisplay() {
    this.matDialog.open(DisplayPmsComponent, {
      width: '20%',
      height: '67%',
      position: { top: '21vh', right: '44vh' },
    });
  }

handleTabChange(event: { tabIndex: string, data?: any }) {
  this.selectedTab = event.tabIndex;

  this.currentSelectedModuleId = null;
  this.selectedFeature = null;
  this.filtersPayload = {};
  this.filterPayloadWorkitem = {}; 
  
  this.isInViewContext = true;
  this.currentViewId = event.data?.view?.id || null;

  this.getAllWorkItemsByViewIdAPI(event.data.view.id);
  if (event.data) {
    const view = event.data.view || {};
    const selectedFilters: { [key: string]: any } = {};

    // Match your `getUpdatedFilters()` structure
    if (view.state) {
      selectedFilters['state'] = [...view.state]; 
    }
    

    if (view.priority?.length) {
      selectedFilters['priority'] = [...view.priority];
    }

      if (view.assignee) {
      selectedFilters['assignee'] = view.assignee.map((a: any) => ({
        id: a.id,
        name: a.name
      }));
    }

    if (view.label?.length) {
      selectedFilters['label'] = [...view.label];
    }

    if (view.modules?.length) {
      selectedFilters['modules'] = view.modules.map((m: any) => ({
        id: m.id,
        name: m.name
      }));
    }

    if (view.cycle) {
       selectedFilters['cycle'] = view.cycle.map((m: any) => ({
        id: m.id,
        name: m.name
      }));
    }

    if (view.lead) {
       selectedFilters['lead'] = view.lead.map((m: any) => ({
        id: m.id,
        name: m.name
      }));
    }

    if (view.createdBy?.length) {
      selectedFilters['createdBy'] = view.createdBy.map((m: any) => ({
        id: m.id,
        name: m.name
      }));
    }

    if (view.startDate) {
      selectedFilters['startDate'] = view.startDate;
    }

    if (view.endDate) {
      selectedFilters['endDate'] = view.endDate;
    }

    // Set and use the filtered payload
    this.filtersPayload = selectedFilters;
   
    this.updateFiltersFromPayload(selectedFilters);
  }
}

clearModuleSelection() {
  this.currentSelectedModuleId = null;
  this.selectedFeature = null;
  this.filtersPayload = {};
  this.filterPayloadWorkitem = {};
  this.isInViewContext = false;
  this.currentViewId = null;
}

refreshDataBasedOnContext() {
  if (this.isInViewContext && this.currentViewId) {
    this.getAllWorkItemsByViewIdAPI(this.currentViewId);
  } else {
    this.getAllWorkItemsAPI(this.currentSelectedModuleId);
  }
}

refreshDataWithFilters() {
  if (this.isInViewContext) {
    this.getAllWorkItemsAPI();
  } else {
    this.getAllWorkItemsAPI(this.currentSelectedModuleId);
  }
}

selectedFeature: any;
tabChange(event: { tab: string, data?: any, feature?: any }) {
  this.selectedTab = event.tab;
  this.selectedFeature = event?.feature || null;

  const tempData = event.data || {};
  const id = tempData.itemId || tempData.id || tempData.moduleId || tempData.cycleId || null;
  const name = tempData.title || tempData.name || null;

  this.currentSelectedModuleId = id;
  this.selectedId = id;
  this.selectedName = name;

  this.filtersPayload = {};
  this.filterPayloadWorkitem = {};
  this.filterGroups = [];

  if (!event.data) {
    this.isInViewContext = false;
    this.currentViewId = null;
    this.getAllWorkItemsAPI();
    return;
  }

  const selectedFilters: { [key: string]: any } = {};

  if (this.selectedFeature === 'MODULE' && id) {
    this.isInViewContext = false;
    this.currentViewId = null;
    selectedFilters['modules'] = [{ id, name }];
    this.filtersPayload = selectedFilters;
    this.updateFiltersFromPayload(selectedFilters);
    this.getAllWorkItemsAPI(id);
    return;
  }

  if (this.selectedFeature === 'CYCLE' && id) {
    this.isInViewContext = false;
    this.currentViewId = null;
    selectedFilters['cycle'] = [{ id, name }];
    this.filtersPayload = selectedFilters;
    this.updateFiltersFromPayload(selectedFilters);
    this.getAllWorkItemsAPI(id);
    return;
  }

  if (this.selectedFeature === 'VIEW' && id) {
    this.isInViewContext = true;
    this.currentViewId = id;
    const projectId = tempData.projectId || this.projectId;

    this.projectService.viewById(projectId, id).subscribe((res: any) => {
      const viewData = res.data || {};
      const viewFilters: { [key: string]: any } = {};

      if (viewData.state?.length) viewFilters['state'] = viewData.state;
      if (viewData.assignee?.length) viewFilters['assignee'] = viewData.assignee;
      if (viewData.priority?.length) viewFilters['priority'] = viewData.priority;
      if (viewData.cycle?.length) viewFilters['cycle'] = viewData.cycle;
      if (viewData.modules?.length) viewFilters['modules'] = viewData.modules;
      if (viewData.label?.length) viewFilters['label'] = viewData.label;
      if (viewData.lead?.length) viewFilters['lead'] = viewData.lead;
      if (viewData.createdBy?.length) viewFilters['createdBy'] = viewData.createdBy;
      if (viewData.startDate) viewFilters['startDate'] = viewData.startDate;
      if (viewData.endDate) viewFilters['endDate'] = viewData.endDate;

      this.filtersPayload = viewFilters;
      this.updateFiltersFromPayload(viewFilters);

      this.getAllWorkItemsByViewIdAPI(id);
    });
    return;
  }

  this.isInViewContext = false;
  this.currentViewId = null;
  this.getAllWorkItemsAPI();
}

// yourWorkTabChange(event: any){
//   this.selectedTab = 'WORKITEM_TAB';

//   if (event.data) {
//     const yourWork = event.selectedData || {};
//     const selectedFilters: { [key: string]: any } = {};

//     // Match your `getUpdatedFilters()` structure
//     if (yourWork.state) {
//       selectedFilters['state'] = [...yourWork.state];
//     }

//     if (yourWork.priority?.length) {
//       selectedFilters['priority'] = [...yourWork.priority];
//     }

//     if (yourWork.assignee) {
//       selectedFilters['assignee'] = yourWork.assignee.map((a: any) => ({
//         id: a.id,
//         name: a.name
//       }));
//     }

//     if (yourWork.label?.length) {
//       selectedFilters['label'] = [...yourWork.label];
//     }

//     if (yourWork.modules?.length) {
//       selectedFilters['modules'] = yourWork.modules.map((m: any) => ({
//         id: m.id,
//         name: m.name
//       }));
//     }

//     if (yourWork.cycle) {
//        selectedFilters['cycle'] = yourWork.cycle.map((m: any) => ({
//         id: m.id,
//         name: m.name
//       }));
//     }

//     if (yourWork.lead) {
//        selectedFilters['lead'] = yourWork.lead.map((m: any) => ({
//         id: m.id,
//         name: m.name
//       }));
//     }

//     if (yourWork.createdBy?.length) {
//       selectedFilters['createdBy'] = yourWork.createdBy.map((m: any) => ({
//         id: m.id,
//         name: m.name
//       }));
//     }

//     // Set and use the filtered payload
//     this.filtersPayload = selectedFilters;
   
//     this.updateFiltersFromPayload(selectedFilters);
//   }

// }

  searchText: string = '';
  searchDebounceTimer: any;
  originalResponse: any[] = []; 

onSearchChange(): void {
  if (this.searchDebounceTimer) {
    clearTimeout(this.searchDebounceTimer);
  }

  this.searchDebounceTimer = setTimeout(() => {
    const trimmedText = this.searchText.trim();
    this.searchWorkItemsLocally(trimmedText);
  }, 300);
}

searchWorkItemsLocally(searchText: string): void {
  if (!searchText) {
    this.response = [...this.originalResponse];

    const groupedData: { [key: string]: any[] } = {};

for (const item of this.response) {
  const subStateId = item.state?.id;
  if (subStateId) {
    if (!groupedData[subStateId]) {
      groupedData[subStateId] = [];
    }
    groupedData[subStateId].push(item);
  }
}

this.secondTabResponse = this.subStateList.map(subState => {
  return {
    id: subState.id,
    name: subState.name,
    items: groupedData[subState.id] || [],
    isOpened: false
  };
});
    return;
  }

  const filteredItems = this.originalResponse.filter(item => {
    const searchLower = searchText.toLowerCase();
    return (
      item.title?.toLowerCase().includes(searchLower) ||
      item.displayBugNo?.toLowerCase().includes(searchLower)
    );
  });

  this.response = filteredItems;

    const groupedData: { [key: string]: any[] } = {};

for (const item of this.response) {
  const subStateId = item.state?.id;
  if (subStateId) {
    if (!groupedData[subStateId]) {
      groupedData[subStateId] = [];
    }
    groupedData[subStateId].push(item);
  }
}

this.secondTabResponse = this.subStateList.map(subState => {
  return {
    id: subState.id,
    name: subState.name,
    items: groupedData[subState.id] || [],
    isOpened: false
  };
});
}
pageLoader:boolean= false;
secondTabResponse:any;
groupedWorkItems: { [key: string]: any[] } = {};
selectedItemForDelete: any = null;

getAllWorkItemsAPI(moduleOrCycleId?:any,workitemIdToOpen?: string) {
  this.loading = true;
  // this.pageLoader = true;
  const businessId = localStorage.getItem("businessId");

  const payload: any = {
    projectId: this.projectId,
    businessId: businessId,
  };

  if (this.filterPayloadWorkitem && Object.keys(this.filterPayloadWorkitem).length > 0) {
    Object.assign(payload, this.filterPayloadWorkitem);
  }

  if (this.selectedFeature === 'MODULE' && moduleOrCycleId) {
    payload.moduleId = [moduleOrCycleId];
    payload.cycleId = null;
  } else if (this.selectedFeature === 'CYCLE' && moduleOrCycleId) {
    payload.cycleId = [moduleOrCycleId];
    payload.moduleId = null;
  }
  
  this.projectService.getAllWorkItems(payload).subscribe({
    next: (res: any) => {
      this.originalResponse = res.data || []; 
      this.response = [...this.originalResponse]; 
      // Apply any current search filter
      if (this.searchText.trim()) {
        this.searchWorkItemsLocally(this.searchText.trim());
      }
      // this.secondTabResponse = res.data;
      this.loading = false;
      // this.pageLoader = false;
      console.log('Fetched work items:', this.response);


    const groupedData: { [key: string]: any[] } = {};

for (const item of this.response) {
  const subStateId = item.state?.id;
  if (subStateId) {
    if (!groupedData[subStateId]) {
      groupedData[subStateId] = [];
    }
    groupedData[subStateId].push(item);
  }
}

this.secondTabResponse = this.subStateList.map(subState => {
  return {
    id: subState.id,
    name: subState.name,
    items: groupedData[subState.id] || [],
    isOpened: false
  };
});
  console.log('Grouped work items by subState:', this.secondTabResponse);
      if (this.preservedSelectedWorkItemId) {
        this.applySelectedWorkItemHighlight();
        this.restoreScrollState();
      }

       if (workitemIdToOpen) {
        const item = this.originalResponse.find(w => w.id === workitemIdToOpen);
        if (item) {
          this.openWorkitemDialog(item);
        }
      }

    },
    error: () => {
      this.loading = false;
      // this.pageLoader = false;
    } 
  });
}


getAllWorkItemsByViewIdAPI(id:any): void {
  this.loading = true;
  this.projectService.getAllWorkItemsByView(id).subscribe({
    next: (res: any) => {
      this.response = res.data;
      this.loading = false;
      if (this.preservedSelectedWorkItemId) {
        this.applySelectedWorkItemHighlight();
        this.restoreScrollState();
      }
    },
    error: () => {
      this.loading = false;
      // this.pageLoader = false;
    }
  });
}

  getAssigneeNames(assignees: any[]): string {
    if (!assignees || assignees.length === 0) return 'No Assignee';
    return assignees.map(a => a.name).join(', ');
  }
  getInitial(name: string): string {
    return name?.charAt(0).toUpperCase() || '';
  }
  projectSettingsData: any;
  getProjectSettingsData() {
    let businessId = localStorage.getItem("businessId");
    this.projectService.getProjectSettingsData(this.projectId, businessId).subscribe(
      (res: any) => {
        this.projectSettingsData = res.data[0];
        this.projectname = this.projectSettingsData?.projectName;
        this.projectStates = this.projectSettingsData?.states;
        this.feature = this.projectSettingsData?.features;
        this.updateDisplayedColumns();
        

      }
    )
  }

  getButtonPosition(event: MouseEvent, dialogWidth: number = 200, dialogHeight: number = 200): { top: string, right: string } {
    const button = event.currentTarget as HTMLElement;
    const buttonRect = button.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    const viewportWidth = window.innerWidth;
    const margin = 10; // Safety margin

    // Calculate available spaces with margin
    const spaceBelow = viewportHeight - buttonRect.bottom - margin;
    const spaceAbove = buttonRect.top - margin;
    const spaceRight = viewportWidth - buttonRect.right - margin;
    const spaceLeft = buttonRect.left - margin;

    // Mobile fallback (centered)
    if (viewportWidth < 768) {
      return {
        top: '50%',
        right: '50%'
      };
    }

    // Determine vertical position
    let top: number;
    if (spaceBelow >= dialogHeight || (spaceBelow < dialogHeight && spaceAbove < dialogHeight)) {
      // Default to below if there's space or if neither has enough space
      top = buttonRect.bottom + window.scrollY;
    } else {
      // Place above if there's not enough space below but enough above
      top = buttonRect.top + window.scrollY - dialogHeight;
    }

    // Determine horizontal position
    let right: number;
    if (spaceRight >= dialogWidth || (spaceRight < dialogWidth && spaceLeft < dialogWidth)) {
      // Default to right-aligned
      right = window.innerWidth - buttonRect.right + window.scrollX;
    } else {
      // Place left-aligned if not enough space on right
      right = window.innerWidth - buttonRect.left + window.scrollX;
    }

    // Ensure we don't go beyond viewport boundaries
    top = Math.max(margin, Math.min(top, viewportHeight - dialogHeight - margin + window.scrollY));
    right = Math.max(margin, Math.min(right, viewportWidth - dialogWidth - margin + window.scrollX));

    return {
      top: top + 'px',
      right: right + 'px'
    };
  }


  selectedIssueStartDate: any;
  selectedIssueDueDate: any;
  selectedIssuePriority: any;



  onPriority(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '32%',
      position: { top: position.top, right: position.right },
      data: { status: 'PRIORITY' }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.selectedIssuePriority = result;
      }
    });
  }

  onStartDate(event: MouseEvent, pId: any) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.5, window.innerHeight * 0.44);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '22%',
      height: 'fit-content',
      position: { top: position.top, right: position.right },
      data: { status: 'START_DATE' }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.selectedIssueStartDate = result;
        
      }
    });
  }

  onDueDate(event: MouseEvent, pId: any) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.5, window.innerHeight * 0.44);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '22%',
      height: 'fit-content',
      position: { top: position.top, right: position.right },
      data: { status: 'DUE_DATE' }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.selectedIssueDueDate = result;
        
      }
    });
  }

  // Drag tracking
  isDragging = false;

  onDragStarted() {
    this.isDragging = true;
  }

  onDragEnded() {
    this.isDragging = false;
  }

  // Auto-scroll functionality during drag
  onDragMoved(event: CdkDragMove) {
    if (!this.kanbanContainer) return;

    const container = this.kanbanContainer.nativeElement;
    const containerRect = container.getBoundingClientRect();
    const pointerPosition = event.pointerPosition;

    // Calculate distance from pointer to container edges
    const leftDistance = pointerPosition.x - containerRect.left;
    const rightDistance = containerRect.right - pointerPosition.x;

    // Auto-scroll logic
    if (leftDistance < this.scrollThreshold) {
      // Scroll left
      container.scrollLeft -= this.autoScrollSpeed;
    } else if (rightDistance < this.scrollThreshold) {
      // Scroll right
      container.scrollLeft += this.autoScrollSpeed;
    }
  }

  // Handle work item click during drag operations
  onWorkItemClick(item: any, event: Event) {
    // Only handle click if not dragging
    if (!event.defaultPrevented) {
      this.detailWorkitem(item);
    }
  }

  // Drag and Drop functionality
  drop(event: CdkDragDrop<any>, targetState: any) {
    const item = event.item.data;
    const previousStateData = event.previousContainer.data as any;
    const currentStateData = event.container.data as any;

    if (event.previousContainer === event.container) {
      // Reordering within the same state
      moveItemInArray(currentStateData.items, event.previousIndex, event.currentIndex);
    } else {
      // Moving between different states
      transferArrayItem(
        previousStateData.items,
        currentStateData.items,
        event.previousIndex,
        event.currentIndex
      );

      // Update the item's state information to match the target state
      item.state = {
        id: targetState.id,
        name: targetState.name
      };

      // Store the change temporarily for later API call
      this.storeStateChange(item, targetState);

      this.updateWorkItemState(item, targetState);
    }
  }

  // Handle item dropped in delete zone
  deleteDroppedItem(event: CdkDragDrop<any>) {
    const item = event.item.data;
    
    
    // Remove from previous container immediately
    const previousStateData = event.previousContainer.data as any;
    const itemIndex = previousStateData.items.findIndex((i: any) => i.id === item.id);
    
    if (itemIndex > -1) {
      previousStateData.items.splice(itemIndex, 1);
    }

    // Call delete API
    this.deleteWorkItem(item);
    
    
  }

  // Store state changes temporarily until API call
  private pendingStateChanges: any[] = [];

  storeStateChange(item: any, newState: any) {
    const changeIndex = this.pendingStateChanges.findIndex(change => change.itemId === item.id);
    
    if (changeIndex > -1) {
      // Update existing change
      this.pendingStateChanges[changeIndex].newState = newState;
    } else {
      // Add new change
      this.pendingStateChanges.push({
        itemId: item.id,
        item: item,
        newState: newState,
        timestamp: new Date()
      });
    }

    
  }

  // Method to get connected drop lists for drag-drop
  getConnectedDropLists(): string[] {
    const stateLists = this.secondTabResponse?.map((_, index) => `state-${index}`) || [];
    return [...stateLists, 'delete-zone'];
  }

  // Future method for API call (placeholder)
  updateState(item: any, newState: any) {
    // This will be implemented later when you provide the API
    
  }

  deleteWorkItem(item: any) {
    this.projectService.deleteWorkItem(item.id).subscribe((res: any) => {
      
      this.refreshDataBasedOnContext();
    });
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

// workitemButton: any; // Store subscription reference
// showAddBtn: any = null; // Initialize with default value

// showButton() {
//   this.workitemButton = this.eventService.showButton.subscribe((data:any) => {
//     
//     setTimeout(() => {
//       // Defer changes to next change detection cycle
//       this.showAddBtn = data?.data;
//       
//     });
//   });
// }

// ngOnDestroy() {
//   // Clean up subscription to prevent memory leaks
//   if (this.workitemButton) {
//     this.workitemButton.unsubscribe();
//   }
// }

// projectData: any;
// projectDetail: any;
// projectDetailData(){
//     this.projectDetail = this.eventService.projectDetails.subscribe((data:any)=>{
//       this.projectData = data.data;
//       
//     });
//   }


// filter data

// filter variables
  searchTerm:any;
  filteredPriorities:any[]=[];
  filteredStates:any[]=[];
  filteredAssignees:any[]=[];
  filteredCycles:any[]=[];
  filteredModules:any[]=[];
  filteredCreatedBy:any[]=[];
  filteredLabels:any[]=[];
  panelExpanded:boolean = true;

 priorityItems: PriorityItem[] = [
    { name: 'URGENT', icon: 'error_outline', class: 'urgent', checked: false },
    { name: 'HIGH', icon: 'signal_cellular_alt', class: 'high', checked: false },
    { name: 'MEDIUM', icon: 'signal_cellular_alt_2_bar', class: 'medium', checked: false },
    { name: 'LOW', icon: 'signal_cellular_alt_1_bar', class: 'low', checked: false },
    { name: 'NONE', icon: 'remove_circle_outline', class: 'none', checked: false }
  ];

  getInitials(name: string): string {
  return name?.trim().charAt(0).toUpperCase() || '';
}



 returnPayload() {
  const businessId = localStorage.getItem('businessId');
  const projectId = this.projectId;

  let payload: any = {
    startDate: this.customStartDate1,
    endDate: this.customEndDate,
    state: this.selectedStates.map(s => ({ id: s.masterStateId, name: s.name })),
    lead: this.selectedLeads.map(s => ({ id: s.id, name: s.name })),
    createdBy: this.selectedCreatedBy.map(s => ({ id: s.id, name: s.name })),
    priority: this.selectedPriorities,
    assignee: this.selectedAssignees.map(s => ({ id: s.id, name: s.name })),
    label: this.selectedLabels.map(s => ({ id: s.id, name: s.name })),
    cycle: this.selectedCycles.map(s => ({ id: s.id, name: s.title })),
    modules: this.selectedModules.map(s => ({ id: s.id, name: s.title })),
  
  };

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
   
   return cleanedPayload;
}

removeFilter(key: string, item: any): void {
  const filterValue = this.filters[key];

  if (Array.isArray(filterValue)) {
    const index = filterValue.findIndex((x: any) => {
    
      if (key === 'priority') {
        return x === item || (typeof item === 'object' && (x === item.name || x === item.displayName));
      }

  
      if (typeof x === 'object' && typeof item === 'object') {
        return x.name === item.name || x.id === item.id;
      }

      
      return typeof x === 'object' ? x.name === item : x === item;
    });

    if (index > -1) {
      filterValue.splice(index, 1);
    }
  } else {
    if (filterValue === item || (typeof item === 'object' && (filterValue === item.name || filterValue === item.displayName))) {
    delete this.filters[key]; 
    }
  }

  this.updateFilterGroups();

  // Regenerate the filter payload and refresh
  this.regenerateFilterPayload();
  window.localStorage.setItem('WORK_ITEM_FILTER', JSON.stringify(this.filterPayloadWorkitem));
  this.refreshDataWithFilters();
}

  // Helper method to regenerate filter payload from current filters
  regenerateFilterPayload(): void {
  
    this.filterPayloadWorkitem = {
      stateId: this.filters['state']?.map((s: any) => s.id) || [],
      leadId: this.filters['lead']?.map((s: any) => s.id) || [],
      priority: this.filters['priority'] || [],
      startDate:this.filters['startDate'] || null,
      endDate:this.filters['endDate'] || null,
      assigneeId: this.filters['assignee']?.map((s: any) => s.id) || [],
      labelId: this.filters['label']?.map((s: any) => s.id) || [],
      cycleId: this.filters['cycle']?.map((s: any) => s.id) || [],
      moduleId: this.filters['modules']?.map((s: any) => s.id) || [],
      createdById: this.filters['createdBy']?.map((s: any) => s.id) || []
    };

    Object.keys(this.filterPayloadWorkitem).forEach(key => {
      if (Array.isArray(this.filterPayloadWorkitem[key]) && this.filterPayloadWorkitem[key].length === 0) {
        delete this.filterPayloadWorkitem[key];
      }
    });
  }

  clearAll(): void {
    this.isFilter = false;
    // Clear all filters and search text
     window.localStorage.removeItem('WORK_ITEM_FILTER');
    for (let key in this.filters) {
      this.filters[key] = [];
    }
    this.searchText = ''; 
    this.filterPayloadWorkitem = {}; 
    this.filtersPayload = {};
    
    // Clear all context - this should show ALL work items
    this.currentSelectedModuleId = null;
    this.selectedFeature = null;
    this.isInViewContext = false;
    this.currentViewId = null;
    
    this.updateFilterGroups();
    
    // Always use regular API without any filters to show everything
    this.getAllWorkItemsAPI();
  }

  transformFiltersForDialog(): any {
    const transformedFilters: any = {};

    if (this.filters['state']?.length) {
      // Extract just the names for the filter component
      transformedFilters['State'] = this.filters['state'].map((s: any) => 
        typeof s === 'string' ? s : s.name
      );
    }

    if (this.filters['priority']?.length) {
      transformedFilters['Priority'] = this.filters['priority'];
    }

    if (this.filters['assignee']?.length) {
      // Transform assignee objects to match expected structure
      transformedFilters['Assignees'] = this.filters['assignee'].map((a: any) => ({
        name: a.name,
        memberId: a.memberId || a.id || '',
        avatar: a.avatar || this.getInitials(a.name)
      }));
    }

    if (this.filters['label']?.length) {
      // Extract just the names for the filter component
      transformedFilters['Labels'] = this.filters['label'].map((l: any) => 
        typeof l === 'string' ? l : l.name
      );
    }

    if (this.filters['modules']?.length) {
      // Transform module objects to match expected structure
      transformedFilters['Modules'] = this.filters['modules'].map((m: any) => ({
        name: typeof m === 'string' ? m : m.name,
        id: typeof m === 'object' ? (m.id || '') : ''
      }));
    }

    if (this.filters['cycle']?.length) {
      transformedFilters['Cycles'] = this.filters['cycle'].map((c: any) => 
        typeof c === 'string' ? c : c.name
      );
    }

    if (this.filters['lead']?.length) {
      transformedFilters['Leads'] = this.filters['lead'].map((l: any) => 
        typeof l === 'string' ? l : l.name
      );
    }

    if (this.filters['createdBy']?.length) {
      transformedFilters['CreatedBy'] = this.filters['createdBy'].map((c: any) => 
        typeof c === 'string' ? c : c.name
      );
    }

    console.log('Transformed filters for dialog:', transformedFilters);
    return transformedFilters;
  }

  refreshWorkItems(): void {
    // Clear all filters and search text
    this.searchText = '';
    this.filters = {};
    this.filtersPayload = {};
    this.filterPayloadWorkitem = {}; // Clear the saved filter payload
    this.filterGroups = [];
    this.currentSelectedModuleId = null; // Clear module selection as well
    this.selectedFeature = null;
    // Clear view context as well
    this.isInViewContext = false;
    this.currentViewId = null;

    this.getAllWorkItemsAPI();
  }


  updateFiltersFromPayload(payload: any) {
    this.filters = {}; // Clear previous selections

    if (payload.state) {
      this.filters['state'] = payload.state.map((s: any) => ({
        id: s.id,
        name: s.name
      }));
    }

    if (payload.startDate) {
      this.filters['startDate'] = payload.startDate;
    }

     if (payload.endDate) {
      this.filters['endDate'] = payload.endDate;
    }

     if (payload.priority) {
      this.filters['priority'] = payload.priority;
    }

    if (payload.assignee) {
      this.filters['assignee'] = payload.assignee.map((s: any) => ({
        id: s.id,
        name: s.name,
        memberId: s.id, // Store the ID as memberId for consistency
        avatar: this.getInitials(s.name)
      }));
    }

    if (payload.label) {
      this.filters['label'] = payload.label.map((s: any) => ({
        id: s.id,
        name: s.name
      }));
    }

    if (payload.modules) {
      this.filters['modules'] = payload.modules.map((s: any) => ({
        id: s.id,
        name: s.name
      }));
    }

    if (payload.cycle) {
      this.filters['cycle'] = payload.cycle.map((s: any) => ({
        id: s.id,
        name: s.name
      }));
    }

    if (payload.lead) {
      this.filters['lead'] = payload.lead.map((s: any) => ({
        id: s.id,
        name: s.name
      }));
    }

    if (payload.createdBy) {
      this.filters['createdBy'] = payload.createdBy.map((s: any) => ({
        id: s.id,
        name: s.name
      }));
    }


    this.updateFilterGroups();
  }

  isFilter:boolean = false;
  updateFilterGroups() {
  this.filterGroups = Object.entries(this.filters as Record<string, unknown>)
    .filter(([_, value]) => {
      if (Array.isArray(value)) {
        return value.length > 0;
      }
      if (typeof value === 'string') {
        return value.trim() !== '';
      }
      if (typeof value === 'number') {
        return !isNaN(value);
      }
      if (typeof value === 'boolean') {
        return true;
      }
      return false;
    })
    .map(([key, value]) => {
      if (Array.isArray(value)) {
        return {
          key,
          value: value.map((item: any) => {
            if (typeof item === 'object' && item && 'name' in item) {
              return { ...item, displayName: (item as any).name };
            }
            return typeof item === 'string'
              ? { name: item, displayName: item }
              : item;
          })
        };
      } else {
        return {
          key,
          value: [{ name: String(value), displayName: String(value) }]
        };
      }
    });
     this.isFilter = this.filterGroups.length > 0;
}


  activeDropdownIndex: number | null = null;
  toggleMoreOptions(event: MouseEvent, index: number): void {
    event.stopPropagation();
    this.activeDropdownIndex = this.activeDropdownIndex === index ? null : index;
  }

  editWorkitem(item:any){

  }
  deleteWorkitem(){

    let workitemId = this.selectedItemForDelete.id;

    this.projectService.deleteWorkItem(workitemId).subscribe((res: any) => {
      this.refreshDataBasedOnContext();
      this.selectedItemForDelete = null; 
    }, (error: any) => {
      console.error('Error deleting work item:', error);
    });
  }

  openDeleteModal(item: any) {
    this.selectedItemForDelete = item;
  }

  confirmDelete() {
    if (this.selectedItemForDelete) {
      this.deleteWorkitem();
    }
  }

  subStateList:any[] = [];
  stateList:any;
  getAllSubStatesList(){
    let projectId = this.projectId;
    this.projectService.getAllSubStatesList(projectId).subscribe({
      next: (response: any) => {
        this.stateList = response.data;
        this.subStateList = this.stateList.flatMap((state: any) =>
        state.subStates.map((subState: any) => ({
          ...subState,
          stateName: state.name,
          stateId: state.id
        }))
      )
        this.refreshDataBasedOnContext();
      },
      error: (error) => {
        console.error('Error fetching sub-states:', error);
      }
    });
  }

updateWorkItemState(item: any, targetState: any) {
  const staffId = localStorage.getItem('staffId');
  const staffName = window.localStorage.getItem('staffName');
  let payload = {
    workItemId: item.id,
    subState: {
      id: targetState.id,
      name: targetState.name
    },
    staff: {
      id: staffId,
      name: staffName
    }
  }

  this.projectService.updateWorkItemState(payload).subscribe((res: any) => {
        this.projectService.openSnack("Workitem State updated successfully", "Ok");
    
    this.refreshDataBasedOnContext();
  }, (error: any) => {
    console.error('Error updating work item state:', error);
    
    this.refreshDataBasedOnContext(); 
  });
}

getLabelsTooltip(labels: any[]): string {
  if (!labels || labels.length === 0) {
    return '';
  }
  
  return labels.map(label => label.name || label.label).join(', ');
}

ngOnDestroy(): void {
  if (this.searchDebounceTimer) {
    clearTimeout(this.searchDebounceTimer);
  }
}

applySelectedWorkItemHighlight() {
  if (!this.preservedSelectedWorkItemId || !this.response) return;

  const found = this.response.find((it: any) => it && it.id === this.preservedSelectedWorkItemId);
  if (found) {
    this.clearSelectionFlags();
    found.isSelected = true;
    this.selectedWorkItem = found;

    const subStateId = found.state?.id;
    if (subStateId && Array.isArray(this.secondTabResponse)) {
      const grp = this.secondTabResponse.find((g: any) => g.id === subStateId);
      if (grp) {
        grp.isOpened = true;
      }
    }

    setTimeout(() => {
      try {
        const el = document.querySelector(`[data-workitem-id="${this.preservedSelectedWorkItemId}"]`) as HTMLElement;
        if (el && typeof el.scrollIntoView === 'function') {
          el.scrollIntoView({ behavior: 'auto', block: 'center' });
        } else {
          window.scrollTo({ top: this.preservedWindowScroll || 0, behavior: 'auto' });
          const mainEl = document.querySelector('.main_container') as HTMLElement;
          if (mainEl) mainEl.scrollTop = this.preservedMainScroll || 0;
          const tableEl = document.querySelector('.table-wrapper') as HTMLElement;
          if (tableEl) tableEl.scrollTop = this.preservedTableScroll || 0;
          if (this.kanbanContainer && this.kanbanContainer.nativeElement) {
            this.kanbanContainer.nativeElement.scrollLeft = this.preservedKanbanScroll || 0;
          }
        }
      } catch (e) {
      }
    }, 120);
  }

}

clearSelectionFlags() {
  if (Array.isArray(this.response)) {
    this.response.forEach((it: any) => { if (it) it.isSelected = false; });
  }
  if (Array.isArray(this.secondTabResponse)) {
    this.secondTabResponse.forEach((g: any) => {
      if (Array.isArray(g.items)) g.items.forEach((it: any) => { if (it) it.isSelected = false; });
    });
  }
}

restoreScrollState() {
  const maxAttempts = 8;
  const attemptDelay = 120; 
  let attempts = 0;

  const tryScroll = () => {
    attempts++;
    try {
      if (this.preservedSelectedWorkItemId) {
        const el = document.querySelector(`[data-workitem-id="${this.preservedSelectedWorkItemId}"]`) as HTMLElement;
        if (el) {
          try {
            el.scrollIntoView({ behavior: 'auto', block: 'center' });
          } catch (e) {
            if (typeof window.scrollTo === 'function') {
              window.scrollTo({ top: this.preservedWindowScroll || 0, behavior: 'auto' });
            }
            const mainEl = document.querySelector('.main_container') as HTMLElement;
            if (mainEl) mainEl.scrollTop = this.preservedMainScroll || 0;
            const tableEl = document.querySelector('.table-wrapper') as HTMLElement;
            if (tableEl) tableEl.scrollTop = this.preservedTableScroll || 0;
            if (this.kanbanContainer && this.kanbanContainer.nativeElement) {
              this.kanbanContainer.nativeElement.scrollLeft = this.preservedKanbanScroll || 0;
            }
          }

          this.preservedSelectedWorkItemId = null;
          this.preservedWindowScroll = 0;
          this.preservedMainScroll = 0;
          this.preservedTableScroll = 0;
          this.preservedKanbanScroll = 0;
          return;
        }
      }

      if (attempts < maxAttempts) {
        setTimeout(tryScroll, attemptDelay);
      } else {
        try {
          if (typeof window.scrollTo === 'function') {
            window.scrollTo({ top: this.preservedWindowScroll || 0, behavior: 'auto' });
          }
          const mainEl = document.querySelector('.main_container') as HTMLElement;
          if (mainEl) mainEl.scrollTop = this.preservedMainScroll || 0;
          const tableEl = document.querySelector('.table-wrapper') as HTMLElement;
          if (tableEl) tableEl.scrollTop = this.preservedTableScroll || 0;
          if (this.kanbanContainer && this.kanbanContainer.nativeElement) {
            this.kanbanContainer.nativeElement.scrollLeft = this.preservedKanbanScroll || 0;
          }
        } catch (e) {
        }
        this.preservedSelectedWorkItemId = null;
        this.preservedWindowScroll = 0;
        this.preservedMainScroll = 0;
        this.preservedTableScroll = 0;
        this.preservedKanbanScroll = 0;
      }
    } catch (err) {
      if (attempts < maxAttempts) {
        setTimeout(tryScroll, attemptDelay);
      } else {
        this.preservedSelectedWorkItemId = null;
      }
    }
  };

  setTimeout(tryScroll, attemptDelay);
}

mergeUpdatedItem(updatedItem: any) {
  if (!updatedItem) return;
  try {
    const updateInArray = (arr: any[]) => {
      if (!Array.isArray(arr)) return;
      const idx = arr.findIndex((it: any) => it && it.id === updatedItem.id);
      if (idx > -1) {
        arr[idx] = { ...arr[idx], ...updatedItem };
      }
    };

    updateInArray(this.originalResponse);
    updateInArray(this.response);

    if (Array.isArray(this.secondTabResponse)) {
      this.secondTabResponse.forEach((g: any) => {
        if (Array.isArray(g.items)) {
          const idx = g.items.findIndex((it: any) => it && it.id === updatedItem.id);
          if (idx > -1) {
            g.items[idx] = { ...g.items[idx], ...updatedItem };
          }
        }
      });
    }
  } catch (e) {
    console.error('Error merging updated item:', e);
  }
}

// workitemId: any;
// updateWorkitemFields(){

//   let payload: any = {
//     state: {
//       id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
//       name: "string"
//     },
//     assignee: [
//       {
//         id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
//         name: "string"
//       }
//     ],
//     priority: "HIGH",
//     startDate: "2025-08-21T11:08:45.577Z",
//     endDate: "2025-08-21T11:08:45.577Z",
//     modules: {
//       id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
//       name: "string"
//     },
//     cycle: {
//       id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
//       name: "string"
//     },
//     label: [
//       {
//         id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
//         name: "string",
//         color: "string"
//       }
//   ]

//   }
//   this.projectService.updateWorkitemFields(this.workitemId, payload).subscribe((res: any) => {
//     this.projectService.openSnack("Workitem updated successfully", "Ok");
//   }, (error: any) => {
//     console.error('Error updating workitem:', error);
//   });
// }

onStateEdit(event: MouseEvent, item: any) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    data: { status: 'STATUS', states: this.subStateList, selectedState: item.state }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      item.state = result;
      this.updateWorkItemField(item.id, 'state', result);
    }
  });
}

onPriorityEdit(event: MouseEvent, item: any) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    data: { status: 'PRIORITY', selectedPriority: { name: item.priority } }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      item.priority = result.name;
      this.updateWorkItemField(item.id, 'priority', result.name);
    }
  });
}

onLabelEdit(event: MouseEvent, item: any) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    disableClose: false,
    hasBackdrop: true,
    backdropClass: 'transparent-backdrop',
    data: { status: 'LABEL', label: this.labelsList, selectedLabels: item.label }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result && result.finalSelection) {
      item.label = result.labels;
      this.updateWorkItemField(item.id, 'label', item.label);
    }
  });
}

onStartDateEdit(event: MouseEvent, item: any) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '19%',
    height: '43%',
    position: { top: position.top, right: position.right },
    data: { status: 'START_DATE' }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      item.startDate = result;
      this.updateWorkItemField(item.id, 'startDate', result);
    }
  });
}

onEndDateEdit(event: MouseEvent, item: any) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '19%',
    height: '43%',
    position: { top: position.top, right: position.right },
    data: { status: 'DUE_DATE' }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      item.endDate = result;
      this.updateWorkItemField(item.id, 'endDate', result);
    }
  });
}

onModuleEdit(event: MouseEvent, item: any) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    data: { status: 'MODULE', module: this.moduleList, selectedModule: item.modules }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result !== undefined) {
      // result can be null (unselect) or an object (select)
      item.modules = result;
      this.updateWorkItemField(item.id, 'modules', result);
    }
  });
}

onCycleEdit(event: MouseEvent, item: any) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    data: { status: 'CYCLE', cycle: this.cycleList, selectedCycle: item.cycle }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result !== undefined) {
      item.cycle = result;
      this.updateWorkItemField(item.id, 'cycle', result);
    }
  });
}

onAssigneeEdit(event: MouseEvent, item: any) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    disableClose: false,
    hasBackdrop: true,
    backdropClass: 'transparent-backdrop',
    data: { status: 'ASSIGNEE', members: this.membersList, selectedAssignees: item.assignee }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result && result.finalSelection) {
      item.assignee = result.assignees;
      this.updateWorkItemField(item.id, 'assignee', item.assignee);
    }
  });
}

// Button position utility function already exists above

// API calls to get data for popups
getallModules() {
  let payload = { projectId: this.projectId };
  this.projectService.getAllModules(payload).subscribe({
    next: (res: any) => {
      if (res && res.data) {
        this.moduleList = res.data;
        console.log('Modules loaded:', this.moduleList);
      }
    },
    error: (error: any) => {
      console.error('Error fetching modules:', error);
    }
  });
}

getAllCycles() {
    let businessId = localStorage.getItem('businessId');
    let projectId = this.projectId;
    this.projectService.getCycleById(businessId,projectId).subscribe({
      next: (response: any) => {
        const data = response?.data || {};

      this.cycleList = [
      ...(data.UPCOMING || []),
      ...(data.ACTIVE || []),
      ...(data.COMPLETED || [])
    ];
      },
      error: (error) => {
        console.error('Error fetching cycles:', error);
      }
    });
  }

getProjectMembers() {
    let projectId = this.projectId;
  this.projectService.getAllMembers(projectId).subscribe(
    (res: any) => {
        this.membersList = res?.data;
    },
    (error: any) => {
      console.error('Error fetching project members:', error);
    }
  );
}

getAllLabels() {
  let projectId = this.projectId;
  this.projectService.getAllLabels(projectId).subscribe(
    (res: any) => {
        this.labelsList = res?.data;
    },
    (error: any) => {
      console.error('Error fetching labels:', error);
    }
  );
}

updateWorkItemField(workItemId: string, field: string, value: any) {
  const staffId = localStorage.getItem('staffId');
  const staffName = localStorage.getItem('staffName');
  let payload: any = {};
  payload[field] = value;
  payload.user= {
    id: staffId,
    name: staffName
  }
  
  this.projectService.updateWorkitemFields(workItemId, payload).subscribe(
    (res: any) => {
      this.projectService.openSnack(`${field} updated successfully`, "Ok");
    },
    (error: any) => {
      console.error(`Error updating ${field}:`, error);
      this.refreshDataBasedOnContext();
    }
  );
}

addworkitemThroughDefaultState(newItem: any) {
  const dialogConfig = {
      width: this.screenWidth > 992 ? '50%' : '55%',
      height: 'fit-content',
      maxWidth: '100vw',
      position: { top: '10vh' },
      data: { mode: 'WORK_ITEM', projectData: this.projectSettingsData , selectedId: this.selectedId, selectedName: this.selectedName, feature: this.selectedFeature , state: {id: newItem?.id, name: newItem?.name}  },
    };

    const dialog = this.matDialog.open(CreateWorkitemComponent, dialogConfig);
    dialog.afterClosed().subscribe(result => {
      if (result) {
        this.refreshDataBasedOnContext();
      }
    });
}


savedLayout:any;
getProjectMemberDetails(){
 let staffId = localStorage.getItem('staffId');
  this.projectService.getProjectMemberDetails(this.projectId,staffId).subscribe((res:any)=>{
    this.savedLayout = res?.data?.savedLayout || 'KANBAN';
    this.selectTab= this.savedLayout;
  }, (error:any)=>{
    console.error('Error fetching project members details:', error);
  });
}

saveLayout(savedLayout:any){
  let staffId = localStorage.getItem('staffId');
  let projectId = this.projectId;

  this.projectService.saveLayout(projectId, staffId, savedLayout).subscribe((res:any)=>{
    console.log('Layout saved successfully:', res);
  }, (error:any)=>{
    console.error('Error saving layout:', error);
  });
}

getReleaseDate(item:null){
  return item === null ? true : false;
}

}