import { Component, EventEmitter, HostListener, Input, OnInit, Output } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { CreateProjectviewComponent } from '../create-projectview/create-projectview.component';
import { WorkManagementService } from '../../../work-management.service';
import { StaffServiceService } from 'src/app/master-config-components/micro-apps/staff/service/staff-service.service';
import { EventEmmiterService } from '../../../../../../services/event-emmiter.service';
interface View {
  id: number;
  name: string;
  filterCount?: number;
  isStarred: boolean;
  isShared: boolean;
}

@Component({
  selector: 'app-list-projectview',
  templateUrl: './list-projectview.component.html',
  styleUrls: ['./list-projectview.component.scss']
})
export class ListProjectviewComponent implements OnInit {

  screenWidth: any;
  constructor(
    private favEvents: StaffServiceService,  
    private matDialog: MatDialog,
    private projectService: WorkManagementService,
    private eventEmitter: EventEmmiterService,
    
    ) {
  }
  @HostListener('window:resize', ['$event'])
      getScreenSize(event?: any) {
        this.screenWidth = window.innerWidth;
      }
       @Output() tabChange = new EventEmitter<{ tabIndex: string, data?: any }>();
    @Input() data: any;
  views: View[] = [];
  viewsList:any;
  pageLoader: boolean = false;
  favList: any[] = [];


  
  
  ngOnInit(): void {
    
        
    this.views = [
      { id: 1, name: 'tarun', isStarred: false, isShared: true },
      { id: 2, name: '31st', isStarred: false, isShared: true },
      { id: 3, name: 'wpsss', filterCount: 0, isStarred: false, isShared: true }
    ];

    this.getAllViewsAPI();
    this.getFavDataByMemberId();
    this.eventEmitter.favListUpdate.subscribe(() => {
      this.getFavDataByMemberId();
    });
  }
  
createView() {
    const dialogConfig = {
      width: this.screenWidth > 992 ? '55%' : '50%',
      height: '55vh',
      maxWidth: '100vw',
      position: { top: '10vh'},
      panelClass: 'create-project-dialog',
      data: { data: this.data }
    };

    const dialog = this.matDialog.open(CreateProjectviewComponent, dialogConfig);

    dialog.afterClosed().subscribe((result: any) => {
        this.getAllViewsAPI();
    });
  }

  getAllViewsAPI(){
    this.pageLoader = true;
  const businessId = localStorage.getItem('businessId');
  const projectId = this.data?.projectId;
  this.projectService.getAllViews(businessId,projectId).subscribe(
    (response: any) => {
      this.viewsList = response.data;
    this.pageLoader = false;

    },
    (error: any) => {
      console.error('Error creating project view:', error);
    this.pageLoader = false;
    }
  );
  }

  deleteViewAPI(){
    this.projectService.deleteViewById(this.viewId).subscribe(
      (response: any) => {
        this.projectService.openSnack("View deleted successfully", "Ok");
        this.getAllViewsAPI();
  
    },
    (error: any) => {
      console.error('Error creating project view:', error);
    }
  );
  }
  
  toggleStar(view: View): void {
    view.isStarred = !view.isStarred;
  }
  
  searchViews(query: string): void {
  }

  navigateToWorkItems(res:any) {
  this.tabChange.emit({ tabIndex: 'WORKITEM_TAB', data: res });
}
updateVieFavStatus(view: any, type: 'favourite' | 'archived') {
  const updatedStatus: any = {
    favourite: view.favourite,
    archived: view.archived
  };

  if (type === 'favourite') {
    updatedStatus.favourite = !view.favourite;
  } else {
    updatedStatus.archived = !view.archived;
  }

  const viewId = view?.id || view?.view?.id;

  this.projectService.markViewFavourite(viewId, updatedStatus.favourite, updatedStatus.archived).subscribe(
    (res: any) => {
      const msg =
        type === 'favourite'
          ? (updatedStatus.favourite ? 'View marked as favourite' : 'View removed from favourites')
          : (updatedStatus.archived ? 'View archived' : 'View unarchived');

      this.projectService.openSnack(msg, 'Ok');
        this.favEvents.notifyFavUpdated();

      // ✅ Update local state to reflect in UI
      if (type === 'favourite') {
        view.favourite = updatedStatus.favourite;
      } else {
        view.archived = updatedStatus.archived;
      }
    },
    (error: any) => {
      console.error('Error while updating View status:', error);
      this.projectService.openSnack('Error while updating View', 'Ok');
    }
  );
}

  activeDropdownIndex: number | null = null;
  toggleMoreOptions(event: MouseEvent, index: number): void {
    event.stopPropagation();
    this.activeDropdownIndex = this.activeDropdownIndex === index ? null : index;
  }

  viewId: any;
  confirmdelete(viewId:any){
    this.viewId = viewId;
  }

  editView(view: any): void {
      const dialogConfig = {
        width: this.screenWidth > 992 ? '50%' : '45%',
        height: 'fit-content',
        maxWidth: '100vw',
        position: { top: '10vh' },
        panelClass: 'create-project-dialog',
        data: { data: this.data , view: view ,edit: true}
      };

      const dialog = this.matDialog.open(CreateProjectviewComponent, dialogConfig);
      dialog.afterClosed().subscribe(result => {
        this.getAllViewsAPI();
      });
    }

    addFavourite(view:any){
    const memberId = localStorage.getItem('staffId');
    const businessId = localStorage.getItem('businessId');
    const itemId = view?.id || view?.view?.id;
    const projectId = view?.project?.id || view?.view?.project?.id;
    const name = view?.title || view?.view?.title || '';
    let payload = {
      memberId: memberId,
      projectId: projectId,
      businessId: businessId,
      itemId: itemId,
      name: name,
      type: 'VIEW'
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
      return this.favList.some((fav: any) => String(fav.itemId) === String(itemId) && fav.type === 'VIEW');
    }

    changeFav(view: any) {
      if (!view) return;
      const itemId = view?.id || view?.view?.id;
      const favItem = this.favList.find((fav: any) => String(fav.itemId) === String(itemId) && fav.type === 'VIEW');
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
        this.addFavourite(view);
      }
    }
}
