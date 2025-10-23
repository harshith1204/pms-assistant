import { Component, EventEmitter, HostListener, Inject, Input, OnInit, Output, ViewChild } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialog } from '@angular/material/dialog';
import { ActivatedRoute, Router } from '@angular/router';
import { CreateModuleComponent } from '../create-module/create-module.component';
import { WorkManagementService } from '../../../work-management.service';
import { CreateWorkitemComponent } from '../../work-item-pms/create-workitem/create-workitem.component';
import { MatSnackBar } from '@angular/material/snack-bar';
import { StaffServiceService } from 'src/app/master-config-components/micro-apps/staff/service/staff-service.service';
import { EventEmmiterService } from '../../../../../../services/event-emmiter.service';
import { MatDateRangePicker } from '@angular/material/datepicker';
import { PopupPmsComponent } from '../../popup-pms/popup-pms.component';

interface Module {
  id: string;
  name: string;
  progress: number;
  startDate?: Date;
  endDate?: Date;
  hasBacklog: boolean;
  assignee?: {
    name: string;
    avatar: string;
  };
  isStarred: boolean;
}

@Component({
  selector: 'app-list-modules',
  templateUrl: './list-modules.component.html',
  styleUrls: ['./list-modules.component.scss']
})
export class ListModulesComponent implements OnInit {
  
  @ViewChild('dateRangePicker') dateRangePicker!: MatDateRangePicker<Date>;
  
  type:any;
  moduleId:any;
  moduleName:any;
  favList: any[] = [];
  screenWidth: any;
  pageLoader: boolean = false;
  selectedModule: any = null;
  moduleToDelete: any = null;
  tempStartDate: Date | null = null;
  tempEndDate: Date | null = null;
  @HostListener('window:resize', ['$event'])
  getScreenSize(event?: any) {
    this.screenWidth = window.innerWidth;
  }
  @Output() changeTab = new EventEmitter<{ tab: string, data?: any , feature?: string }>();
  @Input() data: any;

  constructor(private matDialog: MatDialog,
    private projectService: WorkManagementService,
    private snackBar: MatSnackBar,  
    private favEvents: StaffServiceService,
    private eventEmitter: EventEmmiterService,
    private route: ActivatedRoute,
    
      
    private router: Router) { }

  ngOnInit(): void {
    
    this.getallModules();
    this.getAllSubStatesList();
  this.getFavDataByMemberId();

    this.route.queryParams.subscribe(params => {
    this.moduleId = params['moduleId']
    this.type = params['type'];
    this.moduleName = params['moduleName'];
  });
    if(this.type === 'MODULE') {
    this.favModuleList();
  }

  this.eventEmitter.favListUpdate.subscribe(() => {
      this.getFavDataByMemberId();
    });
  }

  module = { completionPercentage: 20 }; // example

  get pctString(): string {
    const raw = Number(this.module?.completionPercentage ?? 0);
    const clamped = Math.max(0, Math.min(100, isNaN(raw) ? 0 : raw));
    return clamped + '%';
  }
  


  createModule(): void {
    const dialogConfig = {
      width: this.screenWidth > 992 ? '50%' : '45%',
      height: 'fit-content',
      maxWidth: '100vw',
      position: { top: '10vh' },
      panelClass: 'create-project-dialog',
      data: { data: this.data }
    };

    const dialog = this.matDialog.open(CreateModuleComponent, dialogConfig);
    dialog.afterClosed().subscribe(result => {
      this.getallModules();
    });
  }

  editModule(module: Module): void {
    const dialogConfig = {
      width: this.screenWidth > 992 ? '50%' : '45%',
      height: 'fit-content',
      maxWidth: '100vw',
      position: { top: '10vh' },
      panelClass: 'create-project-dialog',
      data: { data: this.data , module: module ,edit: true}
    };

    const dialog = this.matDialog.open(CreateModuleComponent, dialogConfig);
    dialog.afterClosed().subscribe(result => {
      this.getallModules();
    });
  }

  toggleStar(module: Module): void {
    module.isStarred = !module.isStarred;
  }

  // formatDateRange(startDate?: Date, endDate?: Date): string {
  //   if (!startDate || !endDate) return 'Start date → End date';

  //   // Validate dates
  //   if (!this.isValidDate(startDate) || !this.isValidDate(endDate)) {
  //     return 'Start date → End date';
  //   }

  //   return `${this.formatDate(startDate)} - ${this.formatDate(endDate)}`;
  // }

  // private formatDate(date: Date): string {
  //   // Additional validation
  //   if (!date || !this.isValidDate(date)) {
  //     return 'Invalid date';
  //   }

  //   try {
  //     return new Intl.DateTimeFormat('en-US', {
  //       month: 'short',
  //       day: 'numeric',
  //       year: 'numeric'
  //     }).format(date);
  //   } catch (error) {
  //     console.error('Date formatting error:', error);
  //     return 'Invalid date';
  //   }
  // }

  // private isValidDate(date: any): boolean {
  //   if (!date) return false;

  //   // Convert string to date if needed
  //   if (typeof date === 'string') {
  //     date = new Date(date);
  //   }

  //   return date instanceof Date && !isNaN(date.getTime());
  // }

  openDatePicker(module: Module): void {
    this.selectedModule = module;
    this.tempStartDate = module.startDate ? new Date(module.startDate) : null;
    this.tempEndDate = module.endDate ? new Date(module.endDate) : null;
    this.dateRangePicker.open();
  }

  openDatePickerWithPosition(module: Module, event: MouseEvent): void {
    this.selectedModule = module;
    this.tempStartDate = module.startDate ? new Date(module.startDate) : null;
    this.tempEndDate = module.endDate ? new Date(module.endDate) : null;
    this.dateRangePicker.open();
  }

  onDateChange(): void {
    if (this.selectedModule && this.tempStartDate && this.tempEndDate && 
        this.isValidDate(this.tempStartDate) && this.isValidDate(this.tempEndDate)) {
      // Update the module's dates
      this.selectedModule.startDate = this.tempStartDate;
      this.selectedModule.endDate = this.tempEndDate;
      this.moduleUpdateData = this.selectedModule;
      this.updateModule();
      // this.updateModuleDates(this.selectedModule.id, this.tempStartDate, this.tempEndDate);
    }
  }

  private isValidDate(date: any): boolean {
    if (!date) return false;
    
    if (typeof date === 'string') {
      date = new Date(date);
    }
    
    return date instanceof Date && !isNaN(date.getTime());
  }

  

  moduleUpdateData:any
  showPopUp: boolean = false;
  
  openStatePopUp(module: any, event?: MouseEvent): void {
    this.moduleUpdateData = module;
    const position = event ? this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25) : { top: '10vh', right: '5vw' };
    
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      data: { status: 'STATUS', states: this.subStateList }
    });
    
    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.moduleUpdateData.state = result;
        this.updateModule();
      }
    });
  }

  getButtonPosition(event: MouseEvent, dialogWidth: number = 200, dialogHeight: number = 200): { top: string, right: string } {
    const button = event.currentTarget as HTMLElement;
    const buttonRect = button.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    const viewportWidth = window.innerWidth;
    const margin = 10;

    const spaceBelow = viewportHeight - buttonRect.bottom - margin;
    const spaceAbove = buttonRect.top - margin;
    const spaceRight = viewportWidth - buttonRect.right - margin;
    const spaceLeft = buttonRect.left - margin;

    if (viewportWidth < 768) {
      return {
        top: '50%',
        right: '50%'
      };
    }

    let top: number;
    if (spaceBelow >= dialogHeight || (spaceBelow < dialogHeight && spaceAbove < dialogHeight)) {
      top = buttonRect.bottom + window.scrollY;
    } else {
      top = buttonRect.top + window.scrollY - dialogHeight;
    }

    let right: number;
    if (spaceRight >= dialogWidth || (spaceRight < dialogWidth && spaceLeft < dialogWidth)) {
      right = window.innerWidth - buttonRect.right + window.scrollX;
    } else {
      right = window.innerWidth - buttonRect.left + window.scrollX;
    }

    right = right / 2;

    top = Math.max(margin, Math.min(top, viewportHeight - dialogHeight - margin + window.scrollY));
    right = Math.max(margin, Math.min(right, viewportWidth - dialogWidth - margin + window.scrollX));

    return {
      top: top + 'px',
      right: right + 'px'
    };
  }
  
  updateModule() {
    let payload = {
      id: this.moduleUpdateData.id,
      business: { id: this.moduleUpdateData.business.id, name: this.moduleUpdateData.business.name },
      completionPercentage: this.moduleUpdateData.completionPercentage,
      description: this.moduleUpdateData.description,
      endDate: this.moduleUpdateData.endDate,
      favourite: this.moduleUpdateData.favourite,
      lead: this.moduleUpdateData.lead,
      project: {
        id: this.moduleUpdateData.project.id,
        name: this.moduleUpdateData.project.name
      },
      startDate: this.moduleUpdateData.startDate,
      state: this.moduleUpdateData.state,
      title: this.moduleUpdateData.title
    };

    this.projectService.createModule(payload).subscribe({
      next: (response) => {
        this.snackBar.open("Module updated successfully", "Close");
        this.getallModules(); // Refresh the module list
      },
      error: (error) => {
        console.error('Error updating module:', error);
        this.snackBar.open("Error updating module", "Close");
      }
    });
  }

  openMoreOptions(module: Module): void {
  }


  activeDropdownIndex: number | null = null;

  toggleMoreOptions(event: MouseEvent, index: number): void {
    event.stopPropagation();
    this.activeDropdownIndex = this.activeDropdownIndex === index ? null : index;
  }

  // editModule(module: any): void {
  //   module.showDropdown = false;
  //   // Add your edit logic here
  //   
  //   // You can open an edit dialog or navigate to edit page
  // }


  // @HostListener('document:click', ['$event'])
  // onDocumentClick(event: any): void {
  //   // Close all dropdowns when clicking outside
  //   if (this.moduleListing) {
  //     this.moduleListing.forEach((module: any) => {
  //       module.showDropdown = false;
  //     });
  //   }
  // }

  moduleListing: any;
  getallModules() {
    this.pageLoader = true;
    let payload = {
      projectId: this.data.projectId,
      businessId: localStorage.getItem('businessId')
    }
    this.projectService.getAllModules(payload).subscribe({
      next: (response: any) => {
        this.moduleListing = response.data;
        this.pageLoader = false;
      },
      error: (error) => {
        console.error('Error fetching modules:', error);
        this.pageLoader = false;
      }
    });
  }

  moduleSelected: boolean = false;
  moduleData: any;
  projectWholeData: any;
  openModuleWorkitem(module: Module) {
    this.moduleSelected = true;
    this.moduleData = module;
    this.projectWholeData = this.data;
  }

  navigateToWorkItems(module:any){
    this.changeTab.emit({ tab: 'WORKITEM_TAB', data: module , feature: 'MODULE' });
  }

  //  createWorkItem() {
  //     const dialogConfig = {
  //       width: '50%',
  //       height: '66vh',
  //       maxWidth: '100vw',
  //       position: { top: '10vh' },
  //       data: {status: 'MODULE'}
  //     };

  //     const dialog = this.matDialog.open(CreateWorkitemComponent, dialogConfig);
  //     dialog.afterClosed().subscribe(result => {
  //     });

  //   }
  closeWorkitemsModule() {
    this.moduleSelected = false;
  }

  setModuleToDelete(module: any) {
    this.moduleToDelete = module;
  }

  deleteModule(module: any) {
    this.projectService.deleteModule(module).subscribe({
      next: (response) => {
        
        this.snackBar.open("Module deleted successfully", "Close",);
        this.getallModules(); // Refresh the module list
      },
      error: (error) => {
        console.error('Error deleting module:', error);
        this.snackBar.open("Error deleting module", "Close",);
      }
    });
  }

    updateModuleFavStatus(module: any, type: 'favourite' | 'archived') {
    const isFavourite = type === 'favourite' ? !module.favourite : undefined;
    const isArchived = type === 'archived' ? !module.archived : undefined;

    this.projectService.markModuleFavourite(module.id, isFavourite, isArchived).subscribe(
      (res: any) => {
        const msg =
          type === 'favourite'
            ? (isFavourite ? 'Module marked as favourite' : 'Module removed from favourites')
            : (isArchived ? 'Module archived' : 'Module unarchived');

        this.projectService.openSnack(msg, 'Ok');
        this.getallModules();
        this.favEvents.notifyFavUpdated();
      },
      (error: any) => {
        console.error('Error while updating project status:', error);
        this.projectService.openSnack('Error while updating Module', 'Ok');
      }
    );
  }
  getInitial(name: string): string {
    return name?.charAt(0).toUpperCase() || '';
  }

  getAssigneeNames(assignees: any[]): string {
    return assignees?.map(user => user?.name).filter(name => name).join(', ') || '';
  }

  getDateRangeText(module: any): string {
    if (module.startDate && module.endDate) {
      try {
        const startDate = new Date(module.startDate);
        const endDate = new Date(module.endDate);
        
        if (this.isValidDate(startDate) && this.isValidDate(endDate)) {
          const startStr = startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
          const endStr = endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
          return `${startStr} → ${endStr}`;
        }
      } catch (error) {
        console.error('Date formatting error:', error);
      }
    }
    return 'Start date → End date';
  }

  favModuleList(){
    this.moduleSelected = true;
    const favData = { data: this.moduleId, projectData: this.data , moduleName:this.moduleName  };
    console.log('Emitting FavRedirect with data:', favData);
    this.eventEmitter.FavRedirect.emit(favData);
    this.eventEmitter.FavRedirect$.next(favData);
  }

  getFavDataByMemberId() {
    const memberId = localStorage.getItem('staffId');
    if (!memberId) return;
    this.projectService.getFavByMemberId(memberId).subscribe((res: any) => {
      this.favList = res?.data || [];
    }, (err: any) => {
      console.error('Error fetching favourite list:', err);
    });
  }
  favUpdate() {
    this.eventEmitter.favListUpdate.emit({
      view: true
    })
  }

  isFavourite(itemId: any): boolean {
    if (!this.favList || !itemId) return false;
    return this.favList.some((fav: any) => String(fav.itemId) === String(itemId) && fav.type === 'MODULE');
  }

  changeFav(module: any) {
    if (!module) return;
    const favItem = this.favList.find((fav: any) => String(fav.itemId) === String(module.id) && fav.type === 'MODULE');
    if (favItem && favItem.id) {
      this.removeFavouriteById(favItem.id);
    } else {
      this.addFavourite(module);
    }
  }

  removeFavouriteById(favId: any) {
    if (!favId) return;
    this.projectService.removeFavProject(favId).subscribe((res: any) => {
      this.projectService.openSnack('Removed from favourite', 'Ok');
      this.getFavDataByMemberId();
      this.favUpdate();
    }, (error: any) => {
      console.error('Error removing favourite by id:', error);
      this.projectService.openSnack('Error removing favourite', 'Ok');
    });
  }

  searchTerm: string = '';
  onSearch(){}
  stateList: any[] = [];
  subStateList: any[] = [];
  getAllSubStatesList(){
    let projectId = this.data.projectId;
    this.projectService.getAllSubStatesList(projectId).subscribe({
      next: (response: any) => {
        this.stateList = response.data;
        this.subStateList = this.stateList.flatMap((state: any) =>
        state.subStates.map((subState: any) => ({
          ...subState,
          stateName: state.name,
          stateId: state.id
        }))
      );
        
      },
      error: (error) => {
        console.error('Error fetching sub-states:', error);
      }
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

  addFavourite(module:any){
    const memberId = localStorage.getItem('staffId');
    const businessId = localStorage.getItem('businessId');
    let payload = {
      memberId: memberId,
      projectId: module.project.id,
      businessId: businessId,
      itemId: module.id,
      name: module.title,
      type: 'MODULE'
    }
    this.projectService.addFavProject(payload).subscribe((res: any) => {
      this.projectService.openSnack("Added to favourite successfully", "Ok");
      this.getFavDataByMemberId();
      this.favUpdate();
    }, (error: any) => {
      console.error('Error adding to favourite:', error);
      this.projectService.openSnack("Error adding to favourite", "Ok");
    });
  }
}
