import { Component, HostListener, OnInit } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { CreateProjectComponent } from '../create-project/create-project.component';
import { Router } from '@angular/router';
import { ProjectSettingsComponent } from '../project-settings/project-settings.component';
import { CreatePagesComponent } from '../pages-pms/create-pages/create-pages.component';
import { ListPagesComponent } from '../pages-pms/list-pages/list-pages.component';
import { ListProjectviewComponent } from '../project-views-pms/list-projectview/list-projectview.component';
import { WorkManagementService } from '../../work-management.service';
import { FilterPmsComponent } from '../filter-pms/filter-pms.component';
import { PopupPmsComponent } from '../popup-pms/popup-pms.component';
import { EventEmmiterService } from '../../../../../services/event-emmiter.service';
import { error } from 'console';
import { StorageKeys } from 'src/app/shared-module-files/simpo.constant';
declare var bootstrap: any;
@Component({
  selector: 'app-project-pms',
  templateUrl: './project-pms.component.html',
  styleUrls: ['./project-pms.component.scss']
})
export class ProjectPmsComponent implements OnInit {
  screenWidth: any;
  staffList: any;
  projectsList: any;
  searchList: any;
  favList: any = [];
  totalProjects: number = 0;
  activeProjects: number = 0;
  overDueProjects: number = 0;
  completedProjects: number = 0;
  selectedViewType: any = 'manual';
  ascendingType: any = 'DESC';
  searchText = '';
  businessId:any;
  businessName:any;

  defaultImage: string = 'https://d2yx15pncgmu63.cloudfront.net/prod-images/524681c1750191737292Website-Design-Background-Feb-09-2022-03-13-55-73-AM.webp';
  deleteTarget: any;
  pageLoader: boolean = false;

  filters: { [key: string]: any[] } = {};
  filterGroups: { key: string, value: any[] }[] = [];
  filtersPayload: any;
  
  selectedLeads: any[] = [];
  selectedMembers: any[] = [];
  selectedAccess: string[] = [];
  customStartDate: any;
  customEndDate: any;


  constructor(
    private matDialog: MatDialog,
    private router: Router,
    private projectService: WorkManagementService,
    private eventEmitter: EventEmmiterService,


  ) {

  }
  ngOnInit() {
    this.getStaffList();
    this.getProjectsList();
    this.getFavDataByMemberId();
    this.eventEmitter.favListUpdate.subscribe(() => {
      this.getFavDataByMemberId();
    });
    document.body.classList.add('no-scroll');
    document.documentElement.classList.add('no-scroll');
    this.businessId = localStorage.getItem("businessId");
    this.businessName = localStorage.getItem("businessName");

  }

  searchFilter(text: string) {
    if (text && text.trim() !== '') {
      const lowerText = text.toLowerCase();
      this.searchList = this.projectsList.filter(project =>
        project.name.toLowerCase().includes(lowerText) ||
        project.projectDisplayId.toLowerCase().includes(lowerText)
      );
    } else {
      this.searchList = [...this.projectsList];
    }
  }


  @HostListener('window:resize', ['$event'])
  getScreenSize(event?: any) {
    this.screenWidth = window.innerWidth;
  }

  createProject() {
    const dialogConfig = {
      width: this.screenWidth > 992 ? '50%' : '45%',
      height: '80vh',
      maxWidth: '100vw',
      position: { top: '10vh' },
      panelClass: 'create-project-dialog',
      data: this.staffList
    };

    const dialog = this.matDialog.open(CreateProjectComponent, dialogConfig);

    dialog.afterClosed().subscribe((result: any) => {
      this.getProjectsList();
    });
  }

  // projectSetting(){
  //   this.matDialog.open(ProjectSettingsComponent, {
  //     width: '650px', 
  //     maxHeight: '90vh',
  //     panelClass: 'project-settings-dialog'
  //   });
  // }

  goToSettings(res: any) {
    this.router.navigate(['admin/work-management/settings-pms'], {
      queryParams: { projectId: res.id }
    });

  }
  projectdata(data: any) {
    this.eventEmitter.projectDetails.emit({ data: data })
  }
  openPages(res: any) {
    this.router.navigate(['admin/work-management/pages']
      // ,{   queryParams: { projectId:res,}}
    );
    // const dialogConfig = {
    //   width: this.screenWidth > 992 ? '50%' : '100%',
    //   height: '100vh',
    //   maxWidth: '100vw',
    //   position: { top: '0vh' },
    //   panelClass: 'create-project-dialog'
    // };

    // const dialog = this.matDialog.open(ListPagesComponent, dialogConfig);
  }

  copyURLToClipboard(): void {
    const currentUrl = window.location.href;
    navigator.clipboard.writeText(currentUrl)
      .then(() => {
        this.projectService.openSnack("URL copied to clipboard", "Ok");

      })
      .catch(err => {
        console.error('Failed to copy: ', err);
      });
  }


  openWorkItems(res: any) {
    this.router.navigate(['admin/work-management/workItems'], {
      queryParams: { projectId: res, }
    });
    // const dialogConfig = {
    //   width: this.screenWidth > 992 ? '50%' : '100%',
    //   height: '100vh',
    //   maxWidth: '100vw',
    //   position: { top: '0vh' },
    //   panelClass: 'create-project-dialog'
    // };

    // const dialog = this.matDialog.open(ListPagesComponent, dialogConfig);
  }

  openviews(res: any) {
    this.router.navigate(['/admin/work-management/projectViews']
      // ,{queryParams: { projectId:res,}}
    );
    // const dialogConfig = {
    //   width: this.screenWidth > 992 ? '50%' : '100%',
    //   height: '100vh',
    //   maxWidth: '100vw',
    //   position: { top: '0vh' },
    //   panelClass: 'create-project-dialog'
    // };

    // const dialog = this.matDialog.open(ListProjectviewComponent, dialogConfig);
  }
  goToIntake(res: any) {
    this.router.navigate(['admin/work-management/intake'], {
      queryParams: { projectId: res, }
    });
  }
  goToModules(res: any) {
    this.router.navigate(['admin/work-management/modules']
      // ,{queryParams: { projectId:res,}}
    );
  }
  goToCycle(res: any) {
    this.router.navigate(['admin/work-management/cycles']
      // ,{queryParams: { projectId:res,}}
    );
  }
  goToWorkItem(res: any) {
    if (this.isProjectMember(res)) {
      this.router.navigate(['admin/work-management/work-item'], {
        queryParams: { projectId: res.id, }
      });
      localStorage.setItem(StorageKeys.PROJECT_ID, res.id);
    } else {
      //      this.router.navigate(['admin/work-management/work-item'],{
      //    queryParams: { projectId:res.id,}
      // });
      this.projectService.openSnack("Please join the project to see details", "Ok");
    }
  }

  openFilterMenu() {
    const transformedFilters = this.transformFiltersForDialog();
    console.log('Opening filter menu with transformed filters:', transformedFilters);
    
    const dialogRef = this.matDialog.open(FilterPmsComponent, {
      width: '20%',
      height: '67%',
      position: { top: '30vh', right: '65vh' },
      data: { 
        screen: 'PROJECT', 
        projectData: { projectId: null, members: this.staffList }, // Pass staff list for members/leads selection
        selectedFilters: transformedFilters,
        status: 'PROJECT_FILTER'
      }
    });

    dialogRef.componentInstance.dataChanged.subscribe((cleanedPayload: any) => {
      console.log('Received cleanedPayload from project filter:', cleanedPayload);
      this.updateFiltersFromPayload(cleanedPayload);
      this.generateFilterPayload(cleanedPayload);
      this.applyProjectFilters();
    });
  } 

  isProjectMember(project: any): boolean {
    const staffId = localStorage.getItem('staffId');
    const bool = project.members?.some((member: any) => member.id === staffId) || false;
    return bool;
  }

  joinProject(project: any) {
    const staffId = localStorage.getItem('staffId');
    const staffName = window.localStorage.getItem('staffName')
    const StaffEmail = window.localStorage.getItem('staffEmail')

    let payload = {
      project: { id: project.id, name: project.name, },
      business: { id: this.businessId, name: this.businessName },
      members: [{ memberId: staffId,
         name: staffName,
         displayName: staffName, 
         role: 'GUEST', 
         email: StaffEmail,
         project: { id: project.id, name: project.name, },
       }],
    }
    this.projectService.createMember(payload).subscribe((res: any) => {
      this.projectService.openSnack("Joined project successfully", "Ok");
      this.getProjectsList();
      this.updateProjectList();

    }, (error: any) => {
      console.error('Error adding members:', error);
      this.projectService.openSnack("Error adding members", "Ok");
    })
  }

  updateProjectStatus(project: any, type: 'favourite' | 'archived') {
    const isFavourite = type === 'favourite' ? !project.favourite : undefined;
    const isArchived = type === 'archived' ? !project.archived : undefined;

    this.projectService.markAsFavourite(project.id, isFavourite, isArchived).subscribe(
      (res: any) => {
        const msg =
          type === 'favourite'
            ? (isFavourite ? 'Project marked as favourite' : 'Project removed from favourites')
            : (isArchived ? 'Project archived' : 'Project unarchived');

        this.projectService.openSnack(msg, 'Ok');
        this.getProjectsList();
        this.favUpdate();
      },
      (error: any) => {
        console.error('Error while updating project status:', error);
        this.projectService.openSnack('Error while updating project', 'Ok');
      }
    );
  }

  getFavDataByMemberId() {
    const memberId = localStorage.getItem("staffId");
    this.projectService.getFavByMemberId(memberId).subscribe(
      (res: any) => {
        this.favList = res.data || [];
        console.log("Fav data fetched successfully:", this.favList);
      }, (err: any) => {
        console.error("Error fetching fav data:", err);
      }
    );
  }

  changeFav(project: any) {
    const isFav = this.isFavourite(project.id);
    if (isFav) {
      this.removeFavourite(project);
    } else {
      this.addFavourite(project);
    }
  }

  addFavourite(project:any){
    const memberId = localStorage.getItem('staffId');
    const businessId = localStorage.getItem('businessId');
    let payload = {
      memberId: memberId,
      projectId: project.id,
      businessId: businessId,
      itemId: project.id,
      name: project.name,
      type: 'PROJECT'
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

  removeFavourite(project: any) {
    const favItem = this.favList.find((fav: any) => String(fav.itemId) === String(project.id) && fav.type === 'PROJECT');
    if (!favItem || !favItem.id) {
      this.projectService.openSnack("No favourite found to remove", "Ok");
      this.getFavDataByMemberId();
      return;
    }

    this.projectService.removeFavProject(favItem.id).subscribe((res: any) => {
      this.projectService.openSnack("Removed from favourite successfully", "Ok");
      this.getFavDataByMemberId();
      this.favUpdate();
    }, (error: any) => {
      console.error('Error removing from favourite:', error);
      this.projectService.openSnack("Error removing from favourite", "Ok");
    });
  }

favUpdate() {
    this.eventEmitter.favListUpdate.emit({
      view: true
    })
  }



  //  deleteProject(project: any){
  //     this.projectService.deleteProject( project.id).subscribe((res:any)=>{
  //       this.projectService.openSnack("Project deleted successfully", "Ok");
  //       this.getProjectsList();

  //     }, (error: any) => {
  //       console.error('Error while deleting:', error);
  //       this.projectService.openSnack("Error while deleting", "Ok");
  //     })
  // }

   updateProjectList() {
    this.eventEmitter.projectListupdate.emit({
      view: true
    })
  }

  openDeleteModal(project: any): void {
    this.deleteTarget = project;
    const modalElement = document.getElementById('deleteConfirmModal');
    const modal = new bootstrap.Modal(modalElement);
    modal.show();
  }

  confirmDelete(): void {
    if (!this.deleteTarget) return;
    this.pageLoader = true;
    this.projectService.deleteProject(this.deleteTarget.id).subscribe({
      next: () => {
        this.pageLoader = false;
        this.projectService.openSnack("Project deleted successfully", "Ok");
        this.getProjectsList();
        this.updateProjectList();
        this.favUpdate();
        this.closeModal();
      },
      error: (err) => {
        this.pageLoader = false;
        console.error('Error deleting project:', err);
        this.projectService.openSnack("Error while deleting", "Ok");
        this.closeModal();
      }
    });
  }

  closeModal(): void {
    const modalElement = document.getElementById('deleteConfirmModal');
    const modal = bootstrap.Modal.getInstance(modalElement);
    modal.hide();
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


  onPriority(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '28%',
      position: { top: position.top, right: position.right },
      data: { status: 'PROJECT_VIEW', values: { selectedViewType: this.selectedViewType, ascendingType: this.ascendingType } }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.selectedViewType = result.selectedViewType;
        this.ascendingType = result.ascendingType;
        this.getProjectsList();
      }
    });
  }

  getProjectsList() {
    const staffId = localStorage.getItem('staffId');
    this.pageLoader = true;
    let businessId = localStorage.getItem("businessId");
    let data = {
      businessId: businessId,
      searchText: "",
      sortField: this.selectedViewType === 'manual' ? '' : this.selectedViewType,
      sortDirection: this.ascendingType,
      staffId: staffId

    };
    this.projectService.getAllProjects(data).subscribe(
      (res: any) => {
        console.log('Projects fetched:', res);
        const notArchivedProjects = res.data?.filter((project: any) => !project.archived) || [];

        this.projectsList = notArchivedProjects;
        this.searchList = notArchivedProjects;
        this.totalProjects = notArchivedProjects.length;
        this.activeProjects = notArchivedProjects.filter((project: any) => project.active === true).length || 0;
        this.overDueProjects = notArchivedProjects.filter((project: any) => project.status === 'OVERDUE').length || 0;
        this.completedProjects = notArchivedProjects.filter((project: any) => project.status === 'COMPLETED').length || 0;
        this.pageLoader = false;
      },
      error => {
        console.error('Error fetching projects:', error);
        this.projectService.openSnack("Error fetching projects", "Ok");
        this.pageLoader = false;
      }
    );
  }

  transformFiltersForDialog(): any {
    return {
      'Lead': this.selectedLeads || [],
      'Members': this.selectedMembers || [], 
      'Access': this.selectedAccess || [],
      'StartDate': this.customStartDate,
      'EndDate': this.customEndDate
    };
  }

  updateFiltersFromPayload(payload: any): void {
    this.selectedLeads = payload?.lead || [];
    this.selectedMembers = payload?.members || [];
    this.selectedAccess = payload?.access || [];
    this.customStartDate = payload?.startDate;
    this.customEndDate = payload?.endDate;
    
    this.updateFilterGroups();
  }

  generateFilterPayload(cleanedPayload: any): void {
    this.filtersPayload = {
      businessId: localStorage.getItem("businessId"),
      access: cleanedPayload?.access || [],
      lead: cleanedPayload?.lead?.map((l: any) => l.id) || [],
      members: cleanedPayload?.members?.map((m: any) => m.id) || [],
      startDate: cleanedPayload?.startDate || this.customStartDate,
      endDate: cleanedPayload?.endDate || this.customEndDate
    };
    
    console.log('Generated project filter payload:', this.filtersPayload);
  }

  applyProjectFilters(): void {
    if (this.filtersPayload) {
      this.pageLoader = true;
      this.projectService.projectFilter(this.filtersPayload).subscribe(
        (res: any) => {
          console.log('Filter API response:', res);
          if (res?.data) {
            const notArchivedProjects = res.data?.filter((project: any) => !project.archived) || [];
            this.projectsList = notArchivedProjects;
            this.searchList = notArchivedProjects;
            this.updateProjectCounts();
          }
          this.pageLoader = false;
        },
        error => {
          console.error('Error applying filters:', error);
          this.projectService.openSnack("Error applying filters", "Ok");
          this.pageLoader = false;
        }
      );
    }
  }

  updateProjectCounts(): void {
    this.totalProjects = this.projectsList.length;
    this.activeProjects = this.projectsList.filter((project: any) => project.active === true).length || 0;
    this.overDueProjects = this.projectsList.filter((project: any) => project.status === 'OVERDUE').length || 0;
    this.completedProjects = this.projectsList.filter((project: any) => project.status === 'COMPLETED').length || 0;
  }

  updateFilterGroups(): void {
    this.filters = {};
    this.filterGroups = [];

    if (this.selectedLeads?.length > 0) {
      this.filters['Lead'] = this.selectedLeads;
      this.filterGroups.push({ key: 'Lead', value: this.selectedLeads });
    }
    
    if (this.selectedMembers?.length > 0) {
      this.filters['Members'] = this.selectedMembers;
      this.filterGroups.push({ key: 'Members', value: this.selectedMembers });
    }
    
    if (this.selectedAccess?.length > 0) {
      this.filters['Access'] = this.selectedAccess;
      this.filterGroups.push({ key: 'Access', value: this.selectedAccess.map(a => ({ name: a })) });
    }
    
    if (this.customStartDate) {
      this.filters['StartDate'] = [this.customStartDate];
      this.filterGroups.push({ key: 'StartDate', value: [{ name: new Date(this.customStartDate).toLocaleDateString() }] });
    }
    
    if (this.customEndDate) {
      this.filters['EndDate'] = [this.customEndDate];
      this.filterGroups.push({ key: 'EndDate', value: [{ name: new Date(this.customEndDate).toLocaleDateString() }] });
    }
  }

  removeFilter(key: string, item: any): void {
    switch (key) {
      case 'Lead':
        this.selectedLeads = this.selectedLeads.filter(l => l.id !== item.id);
        break;
      case 'Members':
        this.selectedMembers = this.selectedMembers.filter(m => m.id !== item.id);
        break;
      case 'Access':
        this.selectedAccess = this.selectedAccess.filter(a => a !== item.name);
        break;
      case 'StartDate':
        this.customStartDate = null;
        break;
      case 'EndDate':
        this.customEndDate = null;
        break;
    }
    
    this.updateFilterGroups();
    this.regenerateFilterPayload();
    this.applyProjectFilters();
  }

  regenerateFilterPayload(): void {
    const payload = {
      lead: this.selectedLeads,
      members: this.selectedMembers,
      access: this.selectedAccess,
      startDate: this.customStartDate,
      endDate: this.customEndDate
    };
    this.generateFilterPayload(payload);
  }

  clearAllFilters(): void {
    this.selectedLeads = [];
    this.selectedMembers = [];
    this.selectedAccess = [];
    this.customStartDate = null;
    this.customEndDate = null;
    this.filters = {};
    this.filterGroups = [];
    this.filtersPayload = null;
    this.getProjectsList();
  }


  getStaffList() {
    let businessId = localStorage.getItem("businessId");
    this.projectService.getStaff(businessId).subscribe(
      (res: any) => {
        this.staffList = res.data.data;
        localStorage.setItem('staffList', JSON.stringify(this.staffList));

        //let staffListresp = JSON.parse(String(localStorage.getItem('staffList')));

      }
    )
  }

  getInitials(name: string): string {
    if (!name) return '';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  }

  isFavourite(projectId: string): boolean {
  if (!this.favList || !projectId) return false;
  return this.favList.some((fav: any) => String(fav.itemId) === String(projectId));
}

}
