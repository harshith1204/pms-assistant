import { Component, EventEmitter, HostListener, Input, Output } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { CreateCycleComponent } from '../create-cycle/create-cycle.component';
import { WorkManagementService } from '../../../work-management.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { StaffServiceService } from 'src/app/master-config-components/micro-apps/staff/service/staff-service.service';
import { ActivatedRoute } from '@angular/router';
import { BehaviorSubject } from 'rxjs';
import { EventEmmiterService } from '../../../../../../services/event-emmiter.service';

@Component({
  selector: 'app-list-cycles',
  templateUrl: './list-cycles.component.html',
  styleUrls: ['./list-cycles.component.scss']
})
export class ListCyclesComponent {
  private cycleSelectedSource = new BehaviorSubject<any>(null);   // 🔥 BehaviorSubject
  cycleSelected$ = this.cycleSelectedSource.asObservable();

  selectCycle(cycle: any) {
    this.cycleSelectedSource.next(cycle);
  }
  @Output() changeTab = new EventEmitter<{ tab: string, data?: any , feature?: string }>();
  @Input() data: any;
  constructor(private matDialog: MatDialog,
    private snackBar: MatSnackBar,
    private projectService: WorkManagementService,
    private favEvents: StaffServiceService,
    private route: ActivatedRoute,
    private eventEmitter: EventEmmiterService,
    
  ) { }

  screenWidth: any;
  @HostListener('window:resize', ['$event'])
  getScreenSize(event?: any) {
    this.screenWidth = window.innerWidth;
  }

  projectId: any;
  businessId: any;
  allCycles: any[] = [];
  listCycles: any[] = [];
  favList: any[] = [];
  cycleId:any;
  type:any;
  cycleName:any;
  ngOnInit() {
    console.log('List Cycles data:', this.data);
    this.projectId = this.data?.projectId;
    this.businessId = localStorage.getItem('businessId');
    this.getAllCycles();
    this.getFavDataByMemberId();
  console.log('ListCyclesComponent INIT');

  const bId = localStorage.getItem('businessId');
  this.route.queryParams.subscribe(params => {
    this.cycleId = params['cycleId']
    this.type = params['type'];
    this.cycleName = params['cycleName'];
  });

  if(this.type === 'CYCLE') {
    this.favCycleList();
  }

  this.projectService.getHomeProjects(bId, true, true, true).subscribe((res: any) => {
    const allCycles = res?.data || [];
    console.log('ALL CYCLES:', allCycles);

    this.favEvents.cycleSelected.subscribe(favCycle => {
      console.log('EVENT RECEIVED:', favCycle);
      if (favCycle) {
        let fullCycle : any ;
        allCycles.forEach((c) => {
          if(c.id === favCycle.c.id){
             fullCycle=favCycle.fav.id
          }
        })
        console.log('FOUND FULL CYCLE:', fullCycle);
        if (fullCycle) {
          this.openCycleWorkitem(fullCycle);
        }
      }
    });
  });

  this.eventEmitter.favListUpdate.subscribe(() => {
      this.getFavDataByMemberId();
    });
  }

  createCycle() {
      const dialogConfig = {
        width: this.screenWidth > 992 ? '50%' : '45%',
        height: 'fit-content',
        maxWidth: '100vw',
        position: { top: '10vh' },
        panelClass: 'create-project-dialog',
        data : { data: { projectId: this.projectId, businessId: this.businessId } } 
      };
  
      const dialog = this.matDialog.open(CreateCycleComponent, dialogConfig);
      dialog.afterClosed().subscribe(result => {
        // this.getDefaultCycles();
        this.getAllCycles();
    });

  }

  isActiveExpanded = false;
  isUpcomingExpanded = false;
  isCompletedExpanded = false;

  toggleSection(section: string) {
    switch (section) {
      case 'active':
        this.isActiveExpanded = !this.isActiveExpanded;
        break;
      case 'upcoming':
        this.isUpcomingExpanded = !this.isUpcomingExpanded;
        break;
      case 'completed':
        this.isCompletedExpanded = !this.isCompletedExpanded;
        break;
    }
  }

  get activeCycles() {
    return this.listCycles?.filter(cycle => cycle.status === 'ACTIVE') || [];
  }

  get upcomingCycles() {
    return this.listCycles?.filter(cycle => cycle.status === 'UPCOMING') || [];
  }

  get completedCycles() {
    return this.listCycles?.filter(cycle => cycle.status === 'COMPLETED') || [];
  }

  // getDefaultCycles() {
  //   this.projectService.getDefaultCycle().subscribe((res: any) => {
  //     this.allCycles = res?.data || [];
  //     this.getAllCycles();
  //   });
  // }

  getAllCycles() {
    this.projectService.getProjectCycles(this.businessId, this.projectId).subscribe((res: any) => {
      const data = res?.data || {};

      this.listCycles = [
        ...(data.UPCOMING || []),
        ...(data.ACTIVE || []),
        ...(data.COMPLETED || [])
      ];
      console.log("List of cycles:", this.listCycles);
    });
    // this.activeCycleAnalytics();
  }

  editModule(cycle: any) {
    const dialogConfig = {
          width: this.screenWidth > 992 ? '50%' : '45%',
          height: 'fit-content',
          maxWidth: '100vw',
          position: { top: '10vh' },
          panelClass: 'create-project-dialog',
          data: { data: this.data , cycle: cycle ,edit: true}
        };

    const dialog = this.matDialog.open(CreateCycleComponent, dialogConfig);
    dialog.afterClosed().subscribe(result => {
      // this.getDefaultCycles();
      this.getAllCycles();
    });
  }
  deleteModule(cycleId: any) {
    this.projectService.deleteCycle(cycleId).subscribe((res: any) => {
      this.snackBar.open("Cycle deleted successfully", "Close",);
      // this.getDefaultCycles();
      this.getAllCycles();
    }, (error: any) => {
      console.error('Error deleting cycle:', error);
    });
  }

  cycleSelected: boolean = false;
  cycleData: any;
  projectWholeData: any;
  openCycleWorkitem(cycle: any) {
    console.log('OPEN CYCLE CALLED:', cycle); 
    this.cycleSelected = true;
    this.cycleData = cycle;
    this.projectWholeData = this.data;
  }

  navigateToWorkItems(cycle:any){
    this.changeTab.emit({ tab: 'WORKITEM_TAB', data: cycle , feature: 'CYCLE' });
  }

  closeWorkitemsModule() {
    this.cycleSelected = false;
  }

  activeCycleAnalytics() {
    this.projectService.activeCycleAnalytics(this.projectId).subscribe((res: any) => {
      
      
    }, (error: any) => {
      console.error('Error fetching active cycle analytics:', error);
    });
  }

  updateCycleFavStatus(cycle: any, type: 'favourite' | 'archived') {
    const isFavourite = type === 'favourite' ? !cycle.favourite : undefined;
    const isArchived = type === 'archived' ? !cycle.archived : undefined;

    this.projectService.markCycleFavourite(cycle.id, isFavourite, isArchived).subscribe(
      (res: any) => {
        const msg =
          type === 'favourite'
            ? (isFavourite ? 'Cycle marked as favourite' : 'Cycle removed from favourites')
            : (isArchived ? 'Cycle archived' : 'Cycle unarchived');

        this.projectService.openSnack(msg, 'Ok');
        this.getAllCycles();
        this.favEvents.notifyFavUpdated();

      },
      (error: any) => {
        console.error('Error while updating Cycle status:', error);
        this.projectService.openSnack('Error while updating Cycle', 'Ok');
      }
    );
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

  isFavourite(itemId: any): boolean {
    if (!this.favList || !itemId) return false;
    return this.favList.some((fav: any) => String(fav.itemId) === String(itemId) && fav.type === 'CYCLE');
  }

  changeFav(cycle: any) {
    if (!cycle) return;
    const favItem = this.favList.find((fav: any) => String(fav.itemId) === String(cycle.id) && fav.type === 'CYCLE');
    if (favItem && favItem.id) {
      this.removeFavouriteById(favItem.id);
    } else {
      this.addFavourite(cycle);
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

  favCycleList(){
    this.cycleSelected = true;
    const favData = { data: this.cycleId, projectData: this.data , cycleName:this.cycleName  };
    console.log('Emitting FavRedirect with data:', favData);
    this.eventEmitter.FavRedirect.emit(favData);
    this.eventEmitter.FavRedirect$.next(favData);
  }

  addFavourite(cycle:any){
    const memberId = localStorage.getItem('staffId');
    const businessId = localStorage.getItem('businessId');
    let payload = {
      memberId: memberId,
      projectId: cycle.project.id,
      businessId: businessId,
      itemId: cycle.id,
      name: cycle.title,
      type: 'CYCLE'
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

  favUpdate() {
    this.eventEmitter.favListUpdate.emit({
      view: true
    })
  }
}
