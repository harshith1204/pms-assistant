import { Component, Input, HostListener, OnInit, OnDestroy } from '@angular/core';
import { Router } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { WorkManagementService } from '../../../work-management.service';
import { StaffServiceService } from 'src/app/master-config-components/micro-apps/staff/service/staff-service.service';
import { MatDialog } from '@angular/material/dialog';
import { FilterPmsComponent } from '../../filter-pms/filter-pms.component';
import { EventEmmiterService } from '../../../../../../services/event-emmiter.service';

declare var $: any;

@Component({
  selector: 'app-list-pages',
  templateUrl: './list-pages.component.html',
  styleUrls: ['./list-pages.component.scss']
})
export class ListPagesComponent implements OnInit, OnDestroy {
  activeTab: string = 'PUBLIC';
  tabs: string[] = ['PUBLIC', 'PRIVATE', 'ARCHIVED'];
  @Input() data: any;
  allFiles: any[] = [];
  files: any[] = [];
  favList: any[] = [];
  projectName: any;
  showDeleteConfirmationModal: boolean = false;
  selectedPageForDeletion: any = null;
  pageLoader: boolean = false;

  constructor(
    private router: Router,
    private projectService: WorkManagementService,
    private snackBar: MatSnackBar,
    private favEvents: StaffServiceService,
    private matDialog: MatDialog,
    private eventEmitter: EventEmmiterService,
    
     
  ) {}

  screenWidth: any;

  @HostListener('window:resize', ['$event'])
  getScreenSize(event?: any) {
    this.screenWidth = window.innerWidth;
  }

  ngOnInit() {
    this.projectName = this.data?.projectName;
    this.getScreenSize();
    this.loadFiles();
  this.getFavDataByMemberId();

    if (typeof $ !== 'undefined') {
      $('#deleteConfirmationModal').on('hidden.bs.modal', () => {
        this.selectedPageForDeletion = null;
      });
    }
    this.eventEmitter.favListUpdate.subscribe(() => {
      this.getFavDataByMemberId();
    });
  }

  ngOnDestroy(): void {
    if (typeof $ !== 'undefined') {
      $('#deleteConfirmationModal').off('hidden.bs.modal');
    }
  }

  selectedmodule: any;
  selectedcycle: any;
  selectedpage: any;
  selectedcreatedby: any;
  selectedmember: any;
  listPages:any;

  loadFiles() {
    this.pageLoader = true;
    const pId = this.data.projectId;
    let payload = {
      moduleId: this.selectedmodule,
      cycleId: this.selectedcycle,
      pageId: this.selectedpage,
      createdBy: this.selectedcreatedby,
      memberIds: this.selectedmember
    };
    if (this.filterPayloadWorkitem) {
      payload = this.filterPayloadWorkitem;
    }
    if (pId) {
      this.projectService.getAllPages(pId,payload).subscribe(
        (response: any) => {
          this.listPages = response.data;
          this.allFiles = response.data.map((page: any) => ({
            business:{id: page.business.id, name: page.business.name},
            content: page.content,
            id: page.id,
            name: page.title,
            createdby: page.createdBy,
            createdOn: new Date(page.createdAt),
            lastModified: new Date(page.updatedAt),
            visibility: page.visibility,
            favourite: page.favourite,
            locked: page.locked,
            linkedMembers: page.linkedMembers,
            linkedModule: page.linkedModule,
            linkedCycle: page.linkedCycle,
            linkedPages: page.linkedPages
          }));
          this.filterFiles();
          this.pageLoader = false;
        },
        () => {
          this.snackBar.open('Failed to load pages.', 'Close', { duration: 1500 });
          this.pageLoader = false;
        }
      );
    }
  }

  formatCreatedAt(date: string | Date): string {
    const d = new Date(date);
    const options: Intl.DateTimeFormatOptions = {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: false,
      timeZone: 'Asia/Kolkata'
    };
    return `Created on ${d.toLocaleString('en-US', options)}`.replace(',', ' at');
  }

  getVisibilityClass(visibility: string): string {
    switch (visibility) {
      case 'public':
        return 'visibility-public';
      case 'private':
        return 'visibility-private';
      case 'archived':
        return 'visibility-archived';
      default:
        return '';
    }
  }

  getVisibilityTooltip(visibility: string): string {
    switch (visibility) {
      case 'PUBLIC':
        return 'Public - Anyone can view';
      case 'PRIVATE':
        return 'Private - Only team members can view';
      case 'ARCHIVED':
        return 'Archived - No longer active';
      default:
        return 'Unknown visibility';
    }
  }

  // switchTab(tab: string): void {
  //   this.activeTab = tab;
  //   this.filterFiles();
  // }

  filterFiles(): void {
    const staffId = localStorage.getItem('staffId');
    
    if (this.activeTab === 'PUBLIC') {
      this.files = this.listPages.filter(file => file.visibility === 'PUBLIC');
    } else if (this.activeTab === 'PRIVATE') {
      this.files = this.listPages.filter(file => {
        if (file.visibility !== 'PRIVATE') return false;
        
        if (file.linkedMembers && file.linkedMembers.length > 0) {
          return file.linkedMembers.some((member: any) => 
            member.id === staffId || member.memberId === staffId
          );
        }
        return false;
      });
    } else if (this.activeTab === 'ARCHIVED') {
      this.files = this.listPages.filter(file => file.visibility === 'ARCHIVED');
    } else {
      this.files = [...this.listPages];
    }
  }

  createPages() {
    localStorage.setItem('projectDetails', JSON.stringify(this.data));
    this.router.navigate(['admin/work-management/create-page'], {
      state: { projectDetails: this.data }
    });
  }

  openDeleteConfirmation(page: any): void {
    this.selectedPageForDeletion = page;
    this.showDeleteConfirmationModal = true;
    $('#deleteConfirmationModal').modal('show');
  }

  closeDeleteConfirmation(): void {
    this.showDeleteConfirmationModal = false;
    $('#deleteConfirmationModal').modal('hide');
    this.selectedPageForDeletion = null;
  }

  confirmDelete(): void {
    if (this.selectedPageForDeletion) {
      this.projectService.deletePage(this.selectedPageForDeletion.id).subscribe(
        () => {
          this.snackBar.open('Page deleted successfully!', 'Close', { duration: 3000 });
          this.loadFiles();
          this.closeDeleteConfirmation();
        },
        () => {
          this.snackBar.open('Failed to delete page.', 'Close', { duration: 3000 });
          this.closeDeleteConfirmation();
        }
      );
    }
  }


   openInNewTab(page: any): void {
    const url = `/admin/work-management/page-detail/${page.id}`;
    window.open(url, '_blank');
  }

  copyLink(page: any): void {
    const pageLink = `${window.location.origin}/admin/work-management/page-detail/${page.id}`;
    navigator.clipboard.writeText(pageLink).then(() => {
      this.snackBar.open('Link copied to clipboard!', 'Close', { duration: 3000 });
    }).catch(() => {
      this.snackBar.open('Failed to copy link.', 'Close', { duration: 3000 });
    });
  }

  makeCopy(page: any): void {
    const copiedPage = { ...page, id: undefined, name: page.name + ' (Copy)' };
    this.projectService.createPage(copiedPage).subscribe((newPage: any) => {
      this.snackBar.open('Page copied successfully!', 'Close', { duration: 3000 });
      // Reload or update UI here
    });
  }



  // makePrivate(page: any): void {
  //   this.projectService.updatePage(page.id, { isPrivate: true }).subscribe(() => {
  //     this.snackBar.open('Page made private.', 'Close', { duration: 3000 });
  //   });
  // }

  // archivePage(page: any): void {
  //   this.projectService.updatePage(page.id, { status: 'archived' }).subscribe(() => {
  //     this.snackBar.open('Page archived successfully.', 'Close', { duration: 3000 });
  //   });
  // }



  toggleFavourite(page: any): void {
    const newFavStatus = !page.favourite;
    const actionText = newFavStatus ? 'mark as favorite' : 'unmark as favorite';
    this.projectService.markFavPage(page.id, newFavStatus).subscribe(
      () => {
        this.snackBar.open(`Page ${actionText} successfully!`, 'Close', { duration: 3000 });
        page.favourite = newFavStatus;
       this.favEvents.notifyFavUpdated();
       this.getFavDataByMemberId();

      },
      () => {
        this.snackBar.open(`Failed to ${actionText} page.`, 'Close', { duration: 3000 });
      }
    );
  }

  toggleLock(page: any): void {
    const newLockStatus = !page.locked;
    const actionText = newLockStatus ? 'lock' : 'unlock';
    this.projectService.lockUnlockPage(page.id, newLockStatus).subscribe(
      () => {
        this.snackBar.open(`Page ${actionText}ed successfully!`, 'Close', { duration: 3000 });
        page.locked = newLockStatus;
      },
      () => {
        this.snackBar.open(`Failed to ${actionText} page.`, 'Close', { duration: 3000 });
      }
    );
  }

  toggleVisibility(file: any): void {
    const newVisibility = file.visibility === 'PUBLIC' ? 'PRIVATE' : 'PUBLIC';
    this.setVisibility(file, newVisibility);
  }

  setVisibility(file: any, visibility: 'PUBLIC' | 'PRIVATE' | 'ARCHIVED'): void {
    const updateData = { ...file, visibility: visibility };
    this.projectService.createPage(updateData).subscribe(
      () => {
        file.visibility = visibility;
        this.snackBar.open(
          `Page visibility set to ${visibility.toLowerCase()}!`,
          'Close',
          { duration: 3000 }
        );
        this.loadFiles();
      },
      () => {
        this.snackBar.open('Failed to update page visibility.', 'Close', { duration: 3000 });
      }
    );
  }

  restoreVisibility(file: any): void {
    this.setVisibility(file, 'PUBLIC');
  }

  // editViewPageDetails(page: any): void {
  //   this.router.navigate(['admin/work-management/view-page'], {
  //     state: {
  //       pageId: page,
  //       projectDetails: this.data
  //     }
  //   });
  // }

  // viewPageDetails(page: any): void {
  //   this.router.navigate(['admin/work-management/pages/view-page'], {
  //     state: {
  //       pageId: page,
  //       projectDetails: this.data
  //     }
  //   });
  
  // }
  viewPageDetails(page: any): void {
    if (page.visibility === 'PRIVATE') {
      const staffId = localStorage.getItem('staffId');
      const hasAccess = page.linkedMembers?.some(
        (member: any) => member.id === staffId
      );
      if (hasAccess) {
        localStorage.setItem('projectDetails', JSON.stringify(this.data));
        this.router.navigate(['admin/work-management/pages/view-page'], {
          queryParams: { pageId: page.id }
        });
      } else {
        this.snackBar.open('You don’t have view access', 'Close', {
          duration: 1500
        });
      }
    } else {
      localStorage.setItem('projectDetails', JSON.stringify(this.data));
      this.router.navigate(['admin/work-management/pages/view-page'], {
        queryParams: { pageId: page.id }
      });
    }
}

  // projectDetails: any;
  // pageId: any;
  // selectedPage:boolean = false;
  // openViewPage(page: any){
  //   this.selectedPage = true;
  //   this.pageId = page;
  //   this.projectDetails = this.data;

  // }
  // closeViewPage() {
  //   this.selectedPage = false;
  // }

  getFirstLetter(name: string | undefined | null): string {
    if (name && typeof name === 'string' && name.length > 0) {
      return name.charAt(0).toUpperCase();
    }
    return '';
  }

  stopPropagation(event: Event): void {
    event.stopPropagation();
  }

  searchText: string = '';
  searchDebounceTimer: any;

onSearchChange(): void {
  if (this.searchDebounceTimer) {
    clearTimeout(this.searchDebounceTimer);
  }

  this.searchDebounceTimer = setTimeout(() => {
    const trimmedText = this.searchText.trim();
    this.searchPagesLocally(trimmedText);
  }, 300);
}

searchPagesLocally(searchText: string): void {
  if (!searchText) {
    this.filterFiles();
    return;
  }
  const staffId = localStorage.getItem('staffId');
  let tabFilteredFiles: any[] = [];
  
  if (this.activeTab === 'PUBLIC') {
    tabFilteredFiles = this.listPages.filter(file => file.visibility === 'PUBLIC');
  } else if (this.activeTab === 'PRIVATE') {
    tabFilteredFiles = this.listPages.filter(file => {
      if (file.visibility !== 'PRIVATE') return false;
      
      // Check if user has access to private files through linkedMembers
      if (file.linkedMembers && file.linkedMembers.length > 0) {
        return file.linkedMembers.some((member: any) => 
          member.id === staffId || member.memberId === staffId
        );
      }
      
      // If no linkedMembers defined, deny access for private files
      return false;
    });
  } else if (this.activeTab === 'ARCHIVED') {
    tabFilteredFiles = this.listPages.filter(file => file.visibility === 'ARCHIVED');
  } else {
    tabFilteredFiles = [...this.listPages];
  }

  const filteredItems = tabFilteredFiles.filter(item => {
    const searchLower = searchText.toLowerCase();
    return (
      item.name?.toLowerCase().includes(searchLower) ||
      item.createdby?.name?.toLowerCase().includes(searchLower)
    );
  });

  this.files = filteredItems;
}

  getLinkedModuleName(module: any[]): string {
    return module.map(m => m.name).join(', ');
  }
  getLinkedCycleName(cycle: any[]): string {
    return cycle.map(c => c.name).join(', ');
  }
  getLinkedPageName(pages: any[]): string {
    return pages.map(p => p.name).join(', ');
  }
openFilterMenu(){
  const transformedFilters = this.transformFiltersForDialog();
      
      const dialogRef = this.matDialog.open(FilterPmsComponent, {
        width: '20%',
        height: '67%',
        data: { screen: 'PAGE_FILTER', projectData: this.data ,selectedFilters: transformedFilters, status: 'PAGE_FILTER' },
        position: { top: '23vh', right: '19vh'},
      });
  
      dialogRef.componentInstance.dataChanged.subscribe((cleanedPayload: any) => {
        //  window.localStorage.setItem('PAGE_FILTER', JSON.stringify(cleanedPayload));
      
       this.getAppliedFilters(cleanedPayload);
       this.activeTab = cleanedPayload?.access;
       this.filterFiles();
   
      });
}

filterPayloadWorkitem:any;
getAppliedFilters(cleanedPayload:any){     
      this.updateFiltersFromPayload(cleanedPayload);
      this.filterPayloadWorkitem={
      cycleId: cleanedPayload?.cycleId?.map(s => s.id),
      moduleId: cleanedPayload?.moduleId?.map(s => s.id),
      pageId: cleanedPayload?.pageId?.map(s => s.id),
      createdBy:  cleanedPayload?.createdBy?.map(s => s.id),
      memberIds: cleanedPayload?.memberIds?.map(s => s.id),
      };
    this.loadFiles();
  }
  filters: { [key: string]: any[] } = {};
  
  updateFiltersFromPayload(cleanedPayload: any): void {
    this.filters = {};
    
    if (cleanedPayload?.memberIds?.length) {
      this.filters['assignee'] = cleanedPayload.memberIds;
    }
    
    if (cleanedPayload?.moduleId?.length) {
      this.filters['modules'] = cleanedPayload.moduleId;
    }
    
    if (cleanedPayload?.cycleId?.length) {
      this.filters['cycle'] = cleanedPayload.cycleId;
    }
    
    if (cleanedPayload?.pageId?.length) {
      this.filters['pages'] = cleanedPayload.pageId;
    }
    
    if (cleanedPayload?.createdBy?.length) {
      this.filters['createdBy'] = cleanedPayload.createdBy;
    }
    
    console.log('Updated filters from payload:', this.filters);
  }
    
  transformFiltersForDialog(): any {
    const transformedFilters: any = {};
    
    if (this.filters['assignee']?.length) {
      transformedFilters['Assignees'] = this.filters['assignee'].map((a: any) => ({
        name: a.name,
        memberId: a.id || a.memberId || '',
        avatar: a.avatar || this.getInitials(a.name)
      }));
    }

    if (this.filters['modules']?.length) {
      transformedFilters['Modules'] = this.filters['modules'].map((m: any) => ({
        name: m.name || m,
        id: m.id || ''
      }));
    }

    if (this.filters['cycle']?.length) {
      transformedFilters['Cycles'] = this.filters['cycle'].map((c: any) => ({
        name: c.name || c,
        id: c.id || ''
      }));
    }
    
    if (this.filters['pages']?.length) {
      transformedFilters['Pages'] = this.filters['pages'].map((p: any) => ({
        name: p.name || p,
        id: p.id || ''
      }));
    }

    if (this.filters['createdBy']?.length) {
      transformedFilters['CreatedBy'] = this.filters['createdBy'].map((c: any) => ({
        name: c.name || c,
        memberId: c.id || c.memberId || ''
      }));
    }

    // Include access filter to maintain current selection
    if (this.activeTab && this.activeTab !== '') {
      transformedFilters['Access'] = this.activeTab;
    }

    console.log('Transformed filters for dialog:', transformedFilters);
    return transformedFilters;
  }

   getInitials(name: string): string {
  return name?.trim().charAt(0).toUpperCase() || '';
}

addFavourite(pages:any){
    const memberId = localStorage.getItem('staffId');
    const businessId = localStorage.getItem('businessId');
    let payload = {
      memberId: memberId,
      projectId: pages.project.id,
      businessId: businessId,
      itemId: pages.id,
      name: pages.title,
      type: 'PAGE'
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
    return this.favList.some((fav: any) => String(fav.itemId) === String(itemId) && fav.type === 'PAGE');
  }

  changeFav(page: any) {
    if (!page) return;
    const favItem = this.favList.find((fav: any) => String(fav.itemId) === String(page.id) && fav.type === 'PAGE');
    if (favItem && favItem.id) {
      this.projectService.removeFavProject(favItem.id).subscribe((res: any) => {
        this.projectService.openSnack('Removed from favourite', 'Ok');
        this.getFavDataByMemberId();
        this.favUpdate();
      }, (error: any) => {
        console.error('Error removing favourite:', error);
        this.projectService.openSnack('Error removing favourite', 'Ok');
      });
    } else {
      this.addFavourite(page);
    }
  }
}
