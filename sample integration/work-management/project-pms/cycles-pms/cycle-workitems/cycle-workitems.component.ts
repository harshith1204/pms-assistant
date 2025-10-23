import { Component, Input, OnInit, OnDestroy } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { WorkManagementService } from '../../../work-management.service';
import { CreateWorkitemComponent } from '../../work-item-pms/create-workitem/create-workitem.component';
import { DetailWorkitemComponent } from '../../work-item-pms/detail-workitem/detail-workitem.component';
import { ActivatedRoute } from '@angular/router';
import { EventEmmiterService } from '../../../../../../services/event-emmiter.service';
import { FilterPmsComponent } from '../../filter-pms/filter-pms.component';

@Component({
  selector: 'app-cycle-workitems',
  templateUrl: './cycle-workitems.component.html',
  styleUrls: ['./cycle-workitems.component.scss']
})
export class CycleWorkitemsComponent implements OnInit, OnDestroy {

  @Input() data: any;
  @Input() projectData: any;
  pageLoader: boolean = false;

  constructor(
    private matDialog: MatDialog,
    private route: ActivatedRoute,
    private projectService: WorkManagementService,
    private eventEmitter: EventEmmiterService,
    
  ) { 
    console.log('CycleWorkitemsComponent constructor called');
  }
  cycleId: string = '';
  cycleName: any;
  showWorkItemButton: any;
  searchText: string = '';
  searchDebounceTimer: any;
  originalCycleWorkitems: any[] = []; // Store original data for local filtering
  filterPayloadWorkitem: any;
  filters: any = {};
  
  ngOnInit(): void {
    // Subscribe to route parameters to get cycle data from URL
    this.route.queryParams.subscribe(params => {
      if (params['cycleId']) {
        this.cycleId = params['cycleId'];
        this.cycleName = params['cycleName'];
        console.log('Cycle data from route params:', { cycleId: this.cycleId, cycleName: this.cycleName });
      }
    });

    this.favCycle();
    console.log('Cycle workitem data:', this.data);
    console.log('Project data:', this.projectData);
    
    // Use cycle ID from route params if available, otherwise from data
    if (!this.cycleId && this.data?.id) {
      this.cycleId = this.data.id;
    }
    
    console.log('Final Cycle ID:', this.cycleId);
    
    if (!this.cycleName && this.data?.title) {
      this.cycleName = this.data.title;
    }
    
    if (this.cycleId) {
      this.getAllWorkItemsByCycle();
    }
  }

  cycleWorkitems: any;
  
  onSearchChange(): void {
    if (this.searchDebounceTimer) {
      clearTimeout(this.searchDebounceTimer);
    }

    this.searchDebounceTimer = setTimeout(() => {
      const trimmedText = this.searchText.trim();
      this.filterCycleWorkitemsLocally(trimmedText);
    }, 300);
  }

  filterCycleWorkitemsLocally(searchText: string): void {
    if (!searchText) {
      this.cycleWorkitems = [...this.originalCycleWorkitems];
      return;
    }

    const filteredItems = this.originalCycleWorkitems.filter(item => {
      const searchLower = searchText.toLowerCase();
      return (
        item.title?.toLowerCase().includes(searchLower) ||
        item.displayBugNo?.toLowerCase().includes(searchLower)
      );
    });

    this.cycleWorkitems = filteredItems;
  }

  getAllWorkItemsByCycle() {
    this.pageLoader = true;
    const businessId = localStorage.getItem("businessId");

    const payload: any = {
      projectId: this.projectData.projectId,
      businessId: businessId,
      cycleId: Array.isArray(this.cycleId) ? this.cycleId : [this.cycleId]
    };

    if (this.filterPayloadWorkitem && Object.keys(this.filterPayloadWorkitem).length > 0) {
      Object.assign(payload, this.filterPayloadWorkitem);
    }

    this.projectService.getAllWorkItems(payload).subscribe({
      next: (res: any) => {
        this.originalCycleWorkitems = res.data || []; // Store original data
        this.cycleWorkitems = [...this.originalCycleWorkitems]; // Set current display data
        // Apply any current search filter
        if (this.searchText.trim()) {
          this.filterCycleWorkitemsLocally(this.searchText.trim());
        }
        this.pageLoader = false;
        console.log('Fetched work items:', this.cycleWorkitems);
      },
      error: () => {
        this.pageLoader = false;
      } 
    });
  }

  getWorkitemByCycle() {
    this.pageLoader = true;
    this.projectService.getWorkitemByCycle(this.cycleId).subscribe({
      next: (res: any) => {
        this.cycleWorkitems = res.data;
        console.log("hahahaha", this.cycleWorkitems)
        this.pageLoader = false;
      },
      error: (error) => {
        console.error('Error fetching modules:', error);
        this.pageLoader = false;
      }
    });
  }

  // showButton(){
  //   this.eventEmitter.showButton.next({data: 'MODULE', moduleId: this.moduleId, moduleName: this.moduleName});
  // }
  getInitial(name: string): string {
    return name?.charAt(0).toUpperCase() || '';
  }

  createWorkItem() {
    const dialogConfig = {
      width: '50%',
      height: 'fit-content',
      maxWidth: '100vw',
      position: { top: '10vh' },
      data: { status: 'CYCLE', projectData: this.projectData, cycleId: this.cycleId, cycleName: this.cycleName }
    };

    const dialog = this.matDialog.open(CreateWorkitemComponent, dialogConfig);
    dialog.afterClosed().subscribe(result => {
      this.getAllWorkItemsByCycle();
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
        return 'https://d2z9497xp8xb12.cloudfront.net/prod-images/873930c1752326764416fi_11741047.svg';
    }
  }
  detailWorkitem(item: any) {
    if (item) {
      const dialogRef = this.matDialog.open(DetailWorkitemComponent, {
        width: '45%',
        height: '100%',
        panelClass: 'custom-dialog',
        position: { top: '0', right: '0' },
        data: { item, projectData: this.projectData }
      });
      dialogRef.afterClosed().subscribe(res => {
        this.getAllWorkItemsByCycle();

      });
    } else {
      console.warn('Tried to open dialog with undefined item');
    }
  }

  FavRedirect: any;
  FavRedirectBehavior: any;
  
  favCycle(){
    console.log('Setting up FavRedirect subscriptions...');
    
    // Subscribe to EventEmitter
    this.FavRedirect = this.eventEmitter.FavRedirect.subscribe(
      (res: any) => {
        console.log('FAV CYCLE EVENT (EventEmitter):', res);
        if (res && res.data) {
          this.handleFavCycleRedirect(res);
        }
      }
    );

    // Subscribe to BehaviorSubject to get the latest value even if emitted before subscription
    this.FavRedirectBehavior = this.eventEmitter.FavRedirect$.subscribe(
      (res: any) => {
        console.log('FAV CYCLE EVENT (BehaviorSubject):', res);
        if (res && res.data) {
          this.handleFavCycleRedirect(res);
        }
      }
    );
    
    console.log('FavRedirect subscriptions set up completed');
  }

  handleFavCycleRedirect(data: any) {
    console.log('Handling fav cycle redirect:', data);
    // You can add specific logic here to handle the redirect data
    // For example, if you need to load specific cycle data
    if (data.data && data.projectData) {
      this.cycleId = data.data;
      this.projectData = data.projectData;
      this.cycleName = data.cycleName;
      this.getAllWorkItemsByCycle();
    }
  }

  ngOnDestroy(): void {
    // Clean up the search debounce timer to prevent memory leaks
    if (this.searchDebounceTimer) {
      clearTimeout(this.searchDebounceTimer);
    }
    
    if (this.FavRedirect) {
      this.FavRedirect.unsubscribe();
    }
    if (this.FavRedirectBehavior) {
      this.FavRedirectBehavior.unsubscribe();
    }
  }
  refreshWorkItems(): void {
    this.searchText = ''; // Clear search text
    this.filters = {};
    this.filterPayloadWorkitem = {};   
    this.getAllWorkItemsByCycle();
  }

  openFilterMenu() {
    const transformedFilters = this.transformFiltersForDialog();
    
    const dialogRef = this.matDialog.open(FilterPmsComponent, {
      width: '20%',
      height: '67%',
      data: { screen: 'WORK_ITEM', projectData: this.projectData ,selectedFilters: transformedFilters, status: 'WORK_ITEM_FILTER',filter: 'CYCLE_FILTER' },
      position: { top: '26vh', right: '24vh'},
    });

    dialogRef.componentInstance.dataChanged.subscribe((cleanedPayload: any) => {
      console.log('Received cleanedPayload from filter:', cleanedPayload);
      this.updateFiltersFromPayload(cleanedPayload);
      this.filterPayloadWorkitem={
      //   startDate: this.customStartDate,
      // endDate: this.customDueDate,
      stateId: cleanedPayload?.state?.map(s => s.id),
      leadId: cleanedPayload?.lead?.map(s => s.id),
      priority: cleanedPayload?.priority,
      assigneeId: cleanedPayload?.assignee?.map(s => s.id),
      labelId: cleanedPayload?.label?.map(s => s.id),
      moduleId: cleanedPayload?.modules?.map(s => s.id),
      createdById: cleanedPayload?.createdBy?.map(s => s.id)
      };
      console.log('Generated filterPayloadWorkitem:', this.filterPayloadWorkitem);
    //  this.filterPayloadWorkitem = cleanedPayload;    
     this.getAllWorkItemsByCycle();
    });
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
        avatar: a.avatar || this.getInitial(a.name)
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

  updateFiltersFromPayload(payload: any) {
    this.filters = {}; // Clear previous selections

    if (payload.state) {
      this.filters['state'] = payload.state.map((s: any) => ({
        id: s.id,
        name: s.name
      }));
    }

    if (payload.priority) {
      this.filters['priority'] = payload.priority;
    }

    if (payload.assignee) {
      this.filters['assignee'] = payload.assignee.map((s: any) => ({
        id: s.id,
        name: s.name,
        memberId: s.id, // Store the ID as memberId for consistency
        avatar: this.getInitial(s.name)
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

    // this.updateFilterGroups();
  }
}

