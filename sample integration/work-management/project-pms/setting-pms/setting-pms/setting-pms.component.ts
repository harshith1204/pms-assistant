import { Component, HostListener, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AddEstimationComponent } from '../add-estimation/add-estimation.component';
import { MatDialog } from '@angular/material/dialog';
import { WorkManagementService } from '../../../work-management.service';
import { HttpClient } from '@angular/common/http';
import { environment } from 'src/environments/environment';
import { ImageUploadService } from 'src/app/master-config-components/master/screens/locations/image-upload.service';
import { Modal } from 'bootstrap';
import { EventEmmiterService } from '../../../../../../services/event-emmiter.service';
import { Subscription } from 'rxjs';
import { PopupPmsComponent } from '../../popup-pms/popup-pms.component';
import { state } from '@angular/animations';
import { error } from 'console';
import { StorageKeys } from 'src/app/shared-module-files/simpo.constant';
import { bool } from 'aws-sdk/clients/signer';
import { MastersService } from 'src/app/master-config-components/master/screens/master.service';
import { CustomDeleteComponent } from 'src/app/master-config-components/micro-apps/crm/custom-delete/custom-delete.component';

interface StateItem {
  id: string;
  name: string;
  icon: string;
  color: string;
  subStates: SubStateItem[];
  isOpened?: boolean;
  
}

export interface PropertyBox {
  title: string;
  description: string;
  type: string;
  typeSubOption:string,
  typeOption:string,
  mandatory: boolean;
  active: boolean;
  typeSubOptions: string[];
}

interface SubStateItem {
  id: string;
  color: string;
  name: string;
  default: boolean;
  isOpened?: boolean;
  description?: string;
}
interface SettingItem {
  title: string;
  description: string;
  enabled: boolean;
  hasToggle: boolean;
  subItems?: SubSettingItem[];
}

interface SubSettingItem {
  name: string;
  description?: string;
}

interface LabelItem {
  labelId: any;
  label: string;
  color: string;
}

@Component({
  selector: 'app-setting-pms',
  templateUrl: './setting-pms.component.html',
  styleUrls: ['./setting-pms.component.scss']
})
export class SettingPmsComponent implements OnInit, OnDestroy {
  newProperty = {
    title: '',
    description: '',
    type: '',
    mandatory: false,
    active: false,
    numberDefault: undefined as number | undefined,
    dropdownMulti: false,
    dropdownOptions: ['', ''],
    dropdownDefault: null as string | null
  };

  propertyDrafts: Array<{
    title: string;
    description: string;
    type: string;
    mandatory: boolean;
    active: boolean;
    numberDefault: number | undefined;
    dropdownMulti: boolean;
    dropdownOptions: string[];
    dropdownDefault: string | null;
  }> = [];

  private createEmptyDraft() {
    return {
      title: '',
      description: '',
      type: '',
      mandatory: false,
      active: false,
      numberDefault: undefined as number | undefined,
      dropdownMulti: false,
      dropdownOptions: [''],
      dropdownDefault: null as string | null
    };
  }

  propertyTypes = [
    { value: 'text', label: 'Text' },
    { value: 'number', label: 'Number' },
    { value: 'date', label: 'Date' },
    { value: 'boolean', label: 'Boolean' }
  ];

  typeIcon(type: string): string {
    if (!type) return '';
    switch (type) {
      case 'number':
        return '#';
      case 'dropdown':
        return '◯';
      case 'boolean':
        return '⟲';
      case 'text':
      default:
        return '≡';
    }
  }

  screenWidth: any;
  @HostListener('window:resize', ['$event'])
  getScreenSize(event?: any) {
    this.screenWidth = window.innerWidth;
  } settingsPayload: any;
  projectId: any;
  projectData: any;
  projectName: any;
  projectDescription: string = '';
  projectDisplayId: string = '';
  accessType: string = '';
  projectTimezone: string = '';
  selectedInviteeRole: any;
  selectedInvitee: any;
  membersList: any;
  originalMembersList: any;
  projectLead: any
  projectDefaulteAssignee: any;
  projectStatus: any;
  projectIcon: any;
  projectStatusOptions = [
    { value: 'NOT_STARTED', label: 'Not Started' },
    { value: 'STARTED', label: 'Started' },
    { value: 'COMPLETED', label: 'Completed' },
    { value: 'OVERDUE', label: 'Overdue' }
  ];
  inviteList: Array<{ coWorker: any; role: any }> = [];





  availableMembers: any;
  businessMembers: any;

  isAddingLabel = false;
  newLabelTitle: string | null = null;
  selectedLabelColor = '';
  showColorPicker = false;
  editingLabelIndex = -1;
  editLabelTitle = '';
  editLabelColor = '';
  labelId: any;
  labelToDelete: any = null;

  isAddingMembers = false;
  isUpdatingSubState = false;
  isAddingSubState = false;
  isUpdatingProject = false;
  isCreatingLabel = false;
  isUpdatingLabel = false;
  placeholderText = 'Select Member';
  modalInstance: any;

  labelColors = [
    '#FF6B9D', '#9B59B6', '#3498DB', '#2ECC71',
    '#F39C12', '#E74C3C', '#95A5A6', '#34495E'
  ];

  showSubStateColorPicker = false;
  showEditSubStateColorPicker = false;
  editingSubStateId: string | null = null; 


  onSaveSettings() {
    throw new Error('Method not implemented.');
  }
  onInput() { }

  onMemberSearch(text: string) {
    if (text && text.trim() !== '') {
      const lowerText = text.toLowerCase();
      this.membersList = this.originalMembersList.filter(member =>
        member.name.toLowerCase().includes(lowerText)
      );
    } else {
      this.membersList = [...this.originalMembersList];
    }
  }
  organizationName: any;
  timezone: any;
  language: any;
  currency: any;
  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private matDialog: MatDialog,
    private imageUploadService: ImageUploadService,
    private projectService: WorkManagementService,
    private http: HttpClient,
    private eventService: EventEmmiterService,
    private eventEmitter: EventEmmiterService,
       private masterService : MastersService,

  ) {
    this.selectedTab = 'GENERAL';

  }
  selectedTab: any;
  staffListresp: any;
  businessId: any;
  businessName: any;

  onTabChange(txt: any) {
    this.selectedTab = txt;
    if(txt === 'EPIC'){
      this.getAllEpicProperties();
    }
  }
  ngOnInit(): void {
    this.businessId = localStorage.getItem("businessId");
    this.businessName = localStorage.getItem("businessName");
    this.inviteList = [
      {
        coWorker: null,

        role: 'Member'
      }
    ];
    this.staffListresp = JSON.parse(String(localStorage.getItem('staffList')));

    this.availableMembers = this.staffListresp;
    this.businessMembers = this.staffListresp;

    this.route.queryParams.subscribe(params => {
      this.projectId = params['projectId'];


    });

    this. getProjectMemberDetails();
    this.getProjectSettingsData();
    this.projectDetailData();
    this.getAllStates();
    this.getAllLabels();
    this.getEstimation();

  }

  compareMembers = (a: any, b: any): boolean => {
    return a && b && a.id === b.id;
  }

  getAvailableMembers(currentInvite: any): any[] {
    if (!this.businessMembers || !Array.isArray(this.businessMembers)) {
      return [];
    }

    return this.businessMembers.filter(member =>
      !(this.inviteList || []).some(invite =>
        invite !== currentInvite && invite.coWorker?.id === member.id
      )
      &&
      !(this.membersList || []).some(existing => existing.memberId === member.id)
    );
  }

  // getProjectLead(){
  //   if(this.membersList!=null && this.membersList.length>0){
  //     for(let i=0; i< this.membersList.length;i++){
  //       let member = this.membersList[i];
  //       if(member.lead!=null && member.lead.id!=null){
  //         this.projectLead = member;
  //         break;
  //       }
  //     }
  //   }
  // }
  // getProjectAssignee(){
  //   if(this.projectData.members!=null && this.projectData.members.length>0){
  //     for(let i=0; i< this.projectData.members.length;i++){
  //       let member = this.projectData.members[i];
  //       if(member.defaultAssignee!=null && member.defaultAssignee.id!=null){
  //         this.projectDefaulteAssignee = member;
  //         break;
  //       }
  //     }
  //   }
  // }

  selectedLead = 'tarungarg';
  leads = ['tarungarg', 'shiva', 'abhilesh', 'anand'];
  searchText = '';
  selectedProjectLead: any;
  selectedDefaultAssignee: any;
  membersSearchText: any;

  displayedColumns: string[] = ['fullName', 'displayName', 'accountType', 'joiningDate', 'action'];

  members: any[] = [];

  get filteredMembers() {
    return this.members.filter(member =>
      member.fullName.toLowerCase().includes(this.searchText.toLowerCase())
    );
  }


  createPayload: any = {
    fullName: '',
    gender: '',
    number: '',
    email: '',
    dob: '',
    father_name: '',
    blood_group: '',
    disability_type: '',


  }
  states: StateItem[] = [];

  settings: SettingItem[] = [
    {
      title: 'Cycles',
      description: 'Timebox work as you see fit per project and change frequency from one period to the next.',
      enabled: true,
      hasToggle: true
    },
    {
      title: 'Modules',
      description: 'Group work into sub-project-like set-ups with their own leads and assignees.',
      enabled: true,
      hasToggle: true
    },
    {
      title: 'Views',
      description: 'Save sorts, filters, and display options for later or share them.',
      enabled: false,
      hasToggle: true
    },
    {
      title: 'Pages',
      description: 'Write anything like you write anything.',
      enabled: true,
      hasToggle: true
    },
    {
      title: 'Epic',
      description: 'For larger bodies of work that span several cycles and can live across modules',
      enabled: false,
      hasToggle: true
    },

  ];

  isTrackingEnabled: boolean = true;
  isIntakeEnabled: boolean = true;
  isPageEnabled: boolean = true;
  isViewEnabled: boolean = true;
  isModuleEnabled: boolean = true;
  isCycleEnabled: boolean = true;
  isEpicEnabled:boolean = true;

  toggleSetting(setting: SettingItem): void {
    if (setting.hasToggle) {
      const newValue = !setting.enabled;

      const featureMap: { [key: string]: string } = {
        'Cycles': 'CYCLE',
        'Modules': 'MODULE',
        'Views': 'VIEW',
        'Pages': 'PAGE',
        'Intake': 'INTAKE',
        'Epic':'EPIC'
      };

      const featureName = featureMap[setting.title];
      if (featureName) {
        this.updateFeature(featureName, newValue, setting);
      }
    }
  }
  toggleTimeTracking(event: any): void {
    const newValue = (event && event.target && typeof event.target.checked === 'boolean')
      ? event.target.checked
      : !!(event && event.checked);
    this.updateFeature('TRACKING', newValue);
  }

  openStateCard(res: any) {
    res.isOpened = !res.isOpened
  }

  onEdit(res: any) {
    res.isOpened = true;
    this.closeAllColorPickers();
  }
  onCancel(res: any) {
    res.isOpened = false;
    this.closeAllColorPickers();
  }

  newStateName: string = '';
  editingDescription: { [key: string]: string } = {};
  showDescriptionField: string | null = null;
  timeTracking: boolean = true;

  toggleState(state: any): void {
    state.isOpened = !state.isOpened;
  }

  newMember = {
    name: '',
    email: ''
  };


  addNewBusinessMember() {
    // Add to your businessMembers list
    const newEntry = { ...this.newMember, id: Date.now().toString(), avatar: '', initial: this.newMember.name[0] };
    this.businessMembers.push(newEntry);

    // Reset and close
    this.newMember = { name: '', email: '' };

  }
  businessDetails: any;
  openNewMembeDialog() {
    const modalEl = document.getElementById('exampleModalCenter');
    if (modalEl) {
      modalEl.classList.remove('show');
      modalEl.style.display = 'none';
      document.body.classList.remove('modal-open');
    }

    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '22%',
      height: 'fit-content',
      position: { top: '200px', right: '500px' },
      data: { status: 'NEW_MEMBER' }
    });

    dialogRef.afterClosed().subscribe(result => {
      let businessId = localStorage.getItem("businessId");
      if (result) {
        let payload = {
          project: { id: this.projectId, name: this.projectName },
          business: { id: this.businessId, name: this.businessName },
          members: [
            {
              name: result.name,
              email: result.email,
              displayName: result.name,
              role: 'GUEST',
              project: { id: this.projectId, name: this.projectName },


            }
          ]
        }
        this.projectService.createMember(payload).subscribe((res: any) => {
          this.projectService.openSnack("New member added successfully", "Ok");
          this.getProjectSettingsData();


        }, (error: any) => {
          this.projectService.openSnack("Error adding members", "Ok");
        })
      }
    });
  }








  updateDescription(state: any): void {
    this.showDescriptionField = null;
  }

  cancelEdit(): void {
    this.showDescriptionField = null;
    this.editingDescription = {};
  }

  labelsList: any = [];

  emptycontent :boolean = false;
  isEstimatesEnabled: boolean = true;
  estimatePoints: number[] = [1, 2];

  toggleEstimates(event: any) {
    const checked = (event && event.target && typeof event.target.checked === 'boolean')
      ? event.target.checked
      : !!(event && event.checked);
    this.isEstimatesEnabled = checked;
    this.updateFeature('estimation', checked);
  }

  editPoints() {
    // this.addEstimation();
     const dialogConfig = {
      width: this.screenWidth > 992 ? '50%' : '45%',
      height: 'fit-content',
      maxWidth: '100vw',
      position: { top: '10vh' },
      panelClass: 'create-project-dialog',
      data: { projectId: this.projectId , mode:'EDIT', estimate: this.estimateList }
    };

    const dialog = this.matDialog.open(AddEstimationComponent, dialogConfig);

    dialog.afterClosed().subscribe((result: any) => {
      this.getEstimation();      
    });
  }
  addEstimation() {
    const dialogConfig = {
      width: this.screenWidth > 992 ? '50%' : '45%',
      height: 'fit-content',
      maxWidth: '100vw',
      position: { top: '10vh' },
      panelClass: 'create-project-dialog',
      data: { projectId: this.projectId}
    };

    const dialog = this.matDialog.open(AddEstimationComponent, dialogConfig);

    dialog.afterClosed().subscribe((result: any) => {
      this.getEstimation();
    });
  }




  addMoreInvite() {
    this.inviteList.push({
      coWorker: null,
      role: 'Member'
    });
  }

  removeInvite(index: number) {
    if (this.inviteList.length > 1) {
      this.inviteList.splice(index, 1);
    }
  }

  sendInvites() {


  }


  toggleAddLabel(): void {
    this.isAddingLabel = !this.isAddingLabel;
    this.cancelEditLabel();
    if (this.isAddingLabel) {
      this.newLabelTitle = null;
      this.selectedLabelColor = '#FF6B9D';
      this.showColorPicker = false;
    }
  }

  toggleColorPicker(): void {
    this.showColorPicker = !this.showColorPicker;
  }

  selectColor(color: string): void {
    this.selectedLabelColor = color;
    this.showColorPicker = false;
  }

  // addNewLabel(): void {
  //   // if (this.newLabelTitle.trim()) {
  //   //   this.labelsList.push({
  //   //     name: this.newLabelTitle.trim(),
  //   //     color: this.selectedLabelColor
  //   //   });
  //   //   this.cancelAddLabel();
  //   // }

  //   this.createLabelAPI();
  // }

  cancelAddLabel(): void {
    this.isAddingLabel = false;
    this.newLabelTitle = null;
    this.showColorPicker = false;
  }

  editLabel(index: number): void {
    this.cancelAddLabel();
    this.editingLabelIndex = index;
    this.editLabelTitle = this.labelsList[index].label;
    this.editLabelColor = this.labelsList[index].color;
    this.labelId = this.labelsList[index].id;
    this.showColorPicker = false;
  }

  // updateLabel(): void {
  //   if (this.editLabelTitle.trim() && this.editingLabelIndex >= 0) {
  //     this.labelsList[this.editingLabelIndex] = {
  //       name: this.editLabelTitle.trim(),
  //       color: this.editLabelColor
  //     };
  //     this.cancelEditLabel();
  //   }
  // }
  updateLabel() {
    if (!this.editLabelTitle.trim()) {
      this.projectService.openSnack("Label title is required", "Ok");
      return;
    }

    this.isUpdatingLabel = true;

    let payload = {
      id: this.labelId,
      project: { id: this.projectId, name: this.projectName },
      label: this.editLabelTitle.trim(),
      color: this.editLabelColor
    }

    this.projectService.CreateLabels(payload).subscribe(
      (res: any) => {
        this.projectService.openSnack("Label updated successfully", "Ok");
        this.getAllLabels();
        this.cancelEditLabel();
        this.isUpdatingLabel = false;
      },
      (error: any) => {
        console.error('Error updating label:', error);
        this.projectService.openSnack("Failed to update label", "Ok");
        this.isUpdatingLabel = false;
      }
    );
  }

  cancelEditLabel(): void {
    this.editingLabelIndex = -1;
    this.editLabelTitle = '';
    this.editLabelColor = '';
    this.showColorPicker = false;
  }

  selectColorForEdit(color: string): void {
    if (this.editingLabelIndex >= 0) {
      this.editLabelColor = color;
    } else {
      this.selectedLabelColor = color;
    }
    this.showColorPicker = false;
  }

  toggleSubStateColorPicker(): void {
    this.showSubStateColorPicker = !this.showSubStateColorPicker;
    this.showEditSubStateColorPicker = false;
    this.editingSubStateId = null;
  }

  selectSubStateColor(color: string): void {
    this.newSubStateColor = color;
    this.showSubStateColorPicker = false;
  }

  toggleEditSubStateColorPicker(subStateId?: string): void {
    if (this.editingSubStateId === subStateId && this.showEditSubStateColorPicker) {
      this.showEditSubStateColorPicker = false;
      this.editingSubStateId = null;
    } else {
      this.showEditSubStateColorPicker = true;
      this.editingSubStateId = subStateId || null;
    }
    this.showSubStateColorPicker = false;
  }

  selectEditSubStateColor(color: string, subState: any): void {
    subState.color = color;
    this.showEditSubStateColorPicker = false;
    this.editingSubStateId = null;
  }

  // Utility method to close all color pickers
  closeAllColorPickers(): void {
    this.showSubStateColorPicker = false;
    this.showEditSubStateColorPicker = false;
    this.showColorPicker = false; // Also close label color picker
    this.editingSubStateId = null;
  }

  deleteLabel(): void {
    this.projectService.deleteLabel(this.labelToDelete).subscribe(
      (res: any) => {
        this.projectService.openSnack("Label deleted successfully", "Ok");
        this.getAllLabels();
      },
      (error: any) => {
        this.projectService.openSnack("Failed to delete label", "Ok");
      }
    );

  }

  selectLabelForDelete(label: any): void {
    this.labelToDelete = label.id;
  }

  selectedSubStateForDelete(state: any, subState: any): void {
    this.stateId = state;
    this.subStateId = subState;
  }

  updateFeatures(res: any) {
    this.settings = this.settings.map(setting => {

      const key = setting.title.toLowerCase().replace(/s$/, '');
      const enabledValue = res[key];

      return {
        ...setting,
        enabled: typeof enabledValue === 'boolean' ? enabledValue : setting.enabled
      };
    });
  }

  getProjectSettingsData() {
    let businessId = localStorage.getItem("businessId");
    this.projectService.getProjectSettingsData(this.projectId, businessId).subscribe(
      (res: any) => {
        this.projectData = res.data[0];

        // this.getProjectLead();
        // this.getProjectAssignee();
        this.membersList = this.getProjectMembers(this.projectId);

        // this.membersList = this.projectData.members;
        // this.labelsList = this.projectData.label || [];
        this.projectName = this.projectData.name;
        this.projectDescription = this.projectData.projectDescription || '';
        this.projectDisplayId = this.projectData?.projectDisplayId || '';
        this.accessType = this.projectData.access || '';
        this.projectStatus = this.projectData.status || '';
        this.updateFeatures(this.projectData.features);
        this.projectIcon = this.projectData.icon;
        this.selectedEmoji = this.projectData.icon || '😊';
        this.projectName = this.projectData.projectName || '';
        this.accessType = this.projectData.accessType || '';
        this.projectDefaulteAssignee = this.projectData?.defaultAssignee;
        this.projectLead = this.projectData?.lead;
        this.imagePreview = this.projectData?.imageUrl || this.defaultImage;

        this.initializeFeatureToggles();
      }
    )
  }

  getProjectMembers(projectId: any) {
    this.projectService.getAllMembers(projectId).subscribe(
      (res: any) => {
        this.membersList = res.data || [];
        this.originalMembersList = [...this.membersList]; // Store backup for search functionality
      
      },
      (error: any) => {
        console.error('Error fetching members:', error);
      }
    );
  }

  getAllStates() {
    let projectId = this.projectId;
    this.projectService.getAllStates(projectId).subscribe(
      (res: any) => {
        this.states = res.data || [];
        this.states.forEach((state: any) => {
          // Set default color if not provided
          state.color = state.color || '#3498DB';
          state.isOpened = state.isOpened || true;
          state.subStates = (state.subStates || []).map((subState: any) => ({
            ...subState,
            isOpened: subState.isOpened || false,
            description: subState.description || ''
          }));
        });

      },
      (error: any) => {
        console.error('Error fetching states:', error);
      }
    );
  }

  getAllLabels() {
    let projectId = this.projectId;
    this.projectService.getAllLabels(projectId).subscribe(
      (res: any) => {
        this.labelsList = res.data || [];

      },
      (error: any) => {

      }
    );
  }

  file: any;
  imgLoader: boolean = false;
  imgUrl: any;

  defaultImage: string = 'https://d2yx15pncgmu63.cloudfront.net/prod-images/524681c1750191737292Website-Design-Background-Feb-09-2022-03-13-55-73-AM.webp';
  imagePreview: string | ArrayBuffer | null = null;


  async updatePostImage(ev: Event) {
    const input = ev.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      this.file = file;
      this.imgLoader = true;

      try {
        this.imgUrl = await this.imageUploadService.uploadSEOimages(file, 'Blogs')
        this.imgUrl = this.imgUrl.Location;
        this.imagePreview = this.imgUrl;
      } catch (error) {

      }

      this.imgLoader = false;
    }
  }


  initializeFeatureToggles() {
    if (this.projectData && this.projectData.features) {
      this.isCycleEnabled = this.projectData.features.cycles || false;
      this.isModuleEnabled = this.projectData.features.modules || false;
      this.isViewEnabled = this.projectData.features.view || false;
      this.isPageEnabled = this.projectData.features.pages || false;
      this.isIntakeEnabled = this.projectData.features.intake || false;
      this.isTrackingEnabled = this.projectData.features.timeTracking || false;
      this.isEstimatesEnabled = this.projectData.features.estimations || false;
      this.isEpicEnabled = this.projectData.features.epic || false;


      this.settings.forEach(setting => {
        switch (setting.title) {
          case 'Cycles':
            setting.enabled = this.isCycleEnabled;
            break;
          case 'Modules':
            setting.enabled = this.isModuleEnabled;
            break;
          case 'Views':
            setting.enabled = this.isViewEnabled;
            break;
          case 'Pages':
            setting.enabled = this.isPageEnabled;
            break;
          case 'Intake':
            setting.enabled = this.isIntakeEnabled;
            break;
          case 'Epic':
            setting.enabled = this.isEpicEnabled;
            break;
        }
      });
    }
  }

  updateFeature(feature: any, isActive: boolean, setting?: SettingItem) {
    this.projectService.updateProjectFeature(this.projectId, isActive, feature).subscribe(
      (res: any) => {
        this.projectService.openSnack("Feature updated successfully", "Ok");

        if (this.projectData.features) {
          this.projectData.features[feature] = isActive;
        }

        if (setting) {
          setting.enabled = isActive;
        }

        this.updateFeatureFlags(feature, isActive);
      },
      (error: any) => {
        console.error('Error updating feature:', error);
        this.projectService.openSnack("Error updating feature", "Ok");
      }
    )
  }
  updateProject() {
    
    let businessId = localStorage.getItem("businessId");
    let businessName = localStorage.getItem("businessName");

    this.isUpdatingProject = true;

    let payload = {
      business: { id: businessId, name: businessName },
      id: this.projectId,
      name: this.projectName,
      description: this.projectDescription,
      access: this.accessType,
      status: this.projectStatus || 'STARTED',
      imageUrl: this.imagePreview !== null ? this.imagePreview : this.projectData?.imageUrl,
      projectDisplayId: this.projectDisplayId,
      icon: this.selectedEmoji || '😊',
      lead: { id: this.projectData?.lead.id, name: this.projectData?.lead.name},
    }
  

    this.projectService.updateProject(payload).subscribe((res: any) => {
      this.projectService.openSnack("Project updated successfully", "Ok");
      this. updateProjectList();
      this.isUpdatingProject = false;
    }, (error: any) => {
      console.error('Error updating project:', error);
      this.projectService.openSnack("Error updating project", "Ok");
      this.isUpdatingProject = false;
    })

  }

 updateProjectList() {
    this.eventEmitter.projectListupdate.emit({
      view: true
    });

    //  this.eventEmitter.favListUpdate.emit({
    //   view: true
    // })
  }

  // updateProjectLead(res:any){
  //    let businessId = localStorage.getItem("businessId");
  //      let businessName = localStorage.getItem("businessName");
  //   let payload = {
  //     projectId: this.projectId,
  //     business: { id: businessId, name: businessName },
  //     name: this.projectName,
  //     description: this.projectDescription,
  //     access: this.accessType,
  //     imageUrl: this.imagePreview !== null ? this.imagePreview : this.projectData.imageUrl,
  //     members:this.projectData.members,
  //     projectDisplayId: this.projectDisplayId,
  //     defaultAsignee:this.projectData.defaultAssignee,
  //     lead: {id:res.memberId,name:res.name},
  //   }
  //   this.projectService.addmembersToProject(payload).subscribe((res:any)=>{
  //    this.projectService.openSnack("Project lead updated successfully", "Ok");
  //   })
  // }

  // updateDefaultAssignee(res:any){
  //    let businessId = localStorage.getItem("businessId");
  //     let businessName = localStorage.getItem("businessName");

  //   let payload = {
  //     projectId: this.projectId,
  //     business: { id: businessId, name: businessName },
  //     name: this.projectName,
  //     description: this.projectDescription, access: this.accessType,
  //     imageUrl: this.imagePreview !== null ? this.imagePreview : this.projectData.imageUrl,
  //     members:this.projectData.members,
  //     projectDisplayId: this.projectDisplayId,
  //     lead: this.projectLead.lead,
  //     defaultAsignee:{id:res.memberId,name:res.name},}

  //   this.projectService.addmembersToProject(payload).subscribe((res:any)=>{
  //    this.projectService.openSnack("Project default assignee updated successfully", "Ok");
  //   })
  // }
  updateProjectLead(res: any) {
    let payload = {
      id: res.memberId,
      name: res.name,
    }

    this.projectService.updateLead(this.projectId, payload).subscribe((res: any) => {
      this.projectService.openSnack("Project lead updated successfully", "Ok");
    }, (error: any) => {
      console.error('Error updating project lead:', error);
      this.projectService.openSnack("Error updating project lead", "Ok");
    });
  }

  updateDefaultAssignee(res: any) {

    let payload = {
      id: res.memberId,
      name: res.name,
    }

    this.projectService.updateDefaultAssignee(this.projectId, payload).subscribe((res: any) => {
      this.projectService.openSnack("Project default assignee updated successfully", "Ok");
    }, (error: any) => {
      console.error('Error updating default assignee:', error);
      this.projectService.openSnack("Error updating default assignee", "Ok");
    });
  }




  openModal() {
    const modalElement = document.getElementById('exampleModalCenter');
    if (modalElement) {
      this.modalInstance = new Modal(modalElement);
      this.modalInstance.show();
    }
  }


  closeModal() {
    if (this.modalInstance) {
      this.modalInstance.hide();
    }
  }

  canAddMore(): boolean {
    const lastInvite = this.inviteList[this.inviteList.length - 1];

    const isLastInviteValid = lastInvite && lastInvite.coWorker && lastInvite.role;

    const assignedMemberIds = this.inviteList
      .filter(invite => invite.coWorker)
      .map(invite => invite.coWorker.id);

    if (this.businessMembers) {
      const availableMembers = this.businessMembers.filter(
        member => !assignedMemberIds.includes(member.id)
      );
      return isLastInviteValid && availableMembers.length > 0;

    }
    return false;

    // const availableMembers = this.businessMembers.filter(
    //   member => !assignedMemberIds.includes(member.id)
    // );

    // return isLastInviteValid && availableMembers.length > 0;
  }


  addmembers() {

    const validInvites = this.inviteList.filter(invite => invite.coWorker && invite.role);

    if (validInvites.length === 0) {
      this.projectService.openSnack("Please select at least one member to invite", "Ok");
      return;
    }

    this.isAddingMembers = true;

    let payload = {
      project: { id: this.projectId, name: this.projectName },
      business: { id: this.businessId, name: this.businessName },
      members: validInvites.map(invite => ({
        memberId: invite.coWorker.id,
        name: invite.coWorker.name,
        displayName: invite.coWorker.name,
        email: invite.coWorker.contact.email,
        role: invite.role.toUpperCase(),
        project: { id: this.projectId, name: this.projectName },
        staff: { id: invite.coWorker.id, name: invite.coWorker.name }

      }))
    }

    this.projectService.createMember(payload).subscribe((res: any) => {
      this.projectService.openSnack("Members added successfully", "Ok");

      this.closeModal();
      this.getProjectSettingsData();
      this.inviteList = [{
        coWorker: null,
        role: 'Member'
      }];
      this.isAddingMembers = false;
    }, (error: any) => {
      console.error('Error adding members:', error);
      this.projectService.openSnack("Error adding members", "Ok");
      this.isAddingMembers = false;
    })
  }

  createLabelAPI() {
    let payload = {
      project: { id: this.projectId, name: this.projectName },
      color: this.selectedLabelColor,
      label: this.newLabelTitle
    }

    this.isCreatingLabel = true;

    this.projectService.CreateLabels(payload).subscribe((res: any) => {

      this.getAllLabels();
      this.cancelAddLabel();
      this.isCreatingLabel = false;

    }, (error: any) => {
      console.error('Error creating label:', error);
      this.projectService.openSnack("Error creating label", "Ok");
      this.isCreatingLabel = false;
    })

  }

  updateFeatureFlags(feature: string, isActive: boolean) {
    switch (feature) {
      case 'cycles':
      case 'CYCLES':
        this.isCycleEnabled = isActive;
        break;
      case 'modules':
      case 'MODULES':
        this.isModuleEnabled = isActive;
        break;
      case 'view':
      case 'VIEW':
        this.isViewEnabled = isActive;
        break;
      case 'pages':
      case 'PAGES':
        this.isPageEnabled = isActive;
        break;
      case 'intake':
      case 'INTAKE':
        this.isIntakeEnabled = isActive;
        break;
      case 'tracking':
      case 'TRACKING':
        this.isTrackingEnabled = isActive;
        break;
      case 'epic':
      case 'EPIC':
        this.isEpicEnabled = isActive;
        break;
    }
  }

  newSubStateName: string = '';
  newSubStateColor: string = '#3498DB'; // Set default color
  newSubStateDescription: string = '';
  showingNewSubStateForm: string | null = null;

  openCreateSubStateForm(state: any) {

    state.isOpened = true;
    this.showingNewSubStateForm = state.id;
    this.newSubStateName = '';
    this.newSubStateDescription = '';
    this.newSubStateColor = '#3498DB';
    this.showSubStateColorPicker = false;
  }

  cancelCreateSubState() {
    this.showingNewSubStateForm = null;
    this.newSubStateName = '';
    this.newSubStateDescription = '';
    this.newSubStateColor = '#3498DB';
    this.closeAllColorPickers();
  }

  addSubState(stateId: string) {
    this.isAddingSubState = true;

    let payload = {
      projectStateId: stateId,
      newSubStateName: this.newSubStateName.trim(),
      newSubStateDesc: this.newSubStateDescription.trim(),
      newSubStateColor: this.newSubStateColor.trim() || '#3498DB'
    }
    this.projectService.addSubState(payload).subscribe((res: any) => {

      this.getAllStates();
      this.cancelCreateSubState();
      this.projectService.openSnack("Substate added successfully", "Ok");
      this.isAddingSubState = false;
    }, (error: any) => {
      console.error('Error adding substate:', error);
      this.projectService.openSnack("Error adding substate", "Ok");
      this.isAddingSubState = false;
    });
  }

  stateId: any;
  subStateId: any;

  deleteSubState() {
    this.projectService.deleteSubState(this.stateId, this.subStateId).subscribe((res: any) => {

      this.getProjectSettingsData();
      this.getAllStates();
      this.projectService.openSnack("Substate deleted successfully", "Ok");
    }, (error: any) => {
      console.error('Error deleting substate:', error);
      this.projectService.openSnack("Error deleting substate", "Ok");
    });
  }

  onEditSubState(subState: SubStateItem) {
    subState.isOpened = true;
    this.showEditSubStateColorPicker = false;
  }

  onCancelSubState(subState: SubStateItem) {
    subState.isOpened = false;
    this.showEditSubStateColorPicker = false; // Reset color picker
  }

  onUpdateSubState(subState: SubStateItem) {
    if (!subState.name || subState.name.trim() === '') {
      console.error('Substate name is required');
      return;
    }

    this.isUpdatingSubState = true;

    const parentState = this.states.find(state =>
      state.subStates.some(sub => sub.id === subState.id)
    );

    if (parentState) {
      this.updateSubState(parentState.id, subState.id, subState.name, subState.description, subState.color);
    } else {
      console.error('Parent state not found for this substate');
      this.isUpdatingSubState = false;
    }

    subState.isOpened = false;
  }

  updateSubState(stateId: string, subStateId: string, name: string, description?: string, color?: string) {
    let payload: any = {
      stateId: stateId,
      subStateId: subStateId,
      name: name.trim(),
      color: color?.trim() || '',
      description: description?.trim(),
    };

    this.projectService.updateSubState(payload).subscribe((res: any) => {

      this.projectService.openSnack("Substate updated successfully", "Ok");
      this.isUpdatingSubState = false;
    }, (error: any) => {
      this.projectService.openSnack("Error updating substate", "Ok");
      this.isUpdatingSubState = false;
    });
  }
  projectDetail: any;
  projectDetailSubscription!: Subscription;

  projectDetailData() {
    this.projectDetailSubscription = this.eventService.projectDetails.subscribe((data: any) => {
      this.projectDetail = data.data;

      this.projectStatus = this.projectDetail.status || '';
    });
  }

  onStatusChange(event: any) {
    this.projectStatus = event.value;

  }

  createProperty(): void {
    if (!this.newProperty.title) {
      return;
    }

  
    
    const modal = document.getElementById('addPropertyModal');
    if (modal) {
      const bootstrapModal = Modal.getInstance(modal);
      if (bootstrapModal) {
        bootstrapModal.hide();
      }
    }

    this.newProperty = {
      title: '',
      description: '',
      type: '',
      mandatory: false,
      active: false,
      numberDefault: undefined,
      dropdownMulti: false,
      dropdownOptions: ['', ''],
      dropdownDefault: null
    };
  }

  addNewProperty(){
    this.propertyDrafts.push(this.createEmptyDraft());
  }

  ngOnDestroy(): void {
    if (this.projectDetailSubscription) {
      this.projectDetailSubscription.unsubscribe();
    }
  }

  markDefault(res: any) {
    this.subStateId = res.id;
    if (res.default) {
      return;
    }
    else {
      this.markDefaultStatus(this.subStateId);
    }

  }
  markDefaultStatus(subStateId: any) {

    this.projectService.markDefaultState(this.projectId, subStateId).subscribe((res: any) => {
      this.getAllStates();
      this.projectService.openSnack("Substate marked as default successfully", "Ok");
    }, (error: any) => {
      console.error('Error marking substate as default:', error);
      this.projectService.openSnack("Error marking substate as default", "Ok");
    });
  }
  removeMember(res): void {
     let staffId = localStorage.getItem(StorageKeys.STAFF_ID);
     if(this.isStaffAdmin){
      if(res.memberId === staffId){
          this.projectService.openSnack("You can't remove youself, as you are the only admin of the project ", "Ok");
      }else{
        this.projectService.removeMember(res.id).subscribe(
      (res: any) => {
        this.projectService.openSnack("Member removed  successfully", "Ok");
        this.getProjectSettingsData();
      },
      (error: any) => {
        this.projectService.openSnack("Failed to remove", "Ok");
      }
    );}
     }else{
  
       this.projectService.openSnack("Only ADMIN can remove the members ", "Ok");
     }
  
  }


isStaffAdmin: boolean = false;

getProjectMemberDetails() {
  let staffId = localStorage.getItem(StorageKeys.STAFF_ID);
  this.projectService.getProjectMemberDetails(this.projectId, staffId).subscribe(
    (res: any) => {
      const response = res?.data;
      if (response && response.id) {
        this.isStaffAdmin = res.data.role === 'ADMIN';
      } else {
        this.isStaffAdmin = false;
      }
    },
    (error: any) => {
      console.error('Error fetching project members details:', error);
      this.isStaffAdmin = false;
    }
  );
}



  showEmojiPicker = false;
  selectedEmoji: string = '';

  toggleEmojiPicker() {
    this.showEmojiPicker = !this.showEmojiPicker;
  }

  addEmoji(event: any) {
    this.selectedEmoji = event.emoji.native;
    this.showEmojiPicker = false;

  }
  
  enableWorkitemType:boolean=false;
  addWorkItemType(){}
  addTemplate(){}
  enableWorkitem(){
    this.enableWorkitemType = true;
  }
  openAddPropertySection:boolean=false;
  addProperty(){
    this.openAddPropertySection = true;
    if (this.propertyDrafts.length === 0) {
      this.propertyDrafts.push(this.createEmptyDraft());
    }
  }

  removeDraft(index: number) {
    this.propertyDrafts.splice(index, 1);
  }

  addDraftOption(draftIndex: number) {
    const draft = this.propertyDrafts[draftIndex];
    if (draft) draft.dropdownOptions.push('');
  }

  removeDraftOption(draftIndex: number, optIndex: number) {
    const draft = this.propertyDrafts[draftIndex];
    if (draft) draft.dropdownOptions.splice(optIndex, 1);
  }

  createDraftProperty(draftIndex: number) {
    const draft = this.propertyDrafts[draftIndex];
    if (!draft || !draft.title) return;

    this.propertyDrafts.splice(draftIndex, 1);
  }

  estimateList:any;
  getEstimation(){
    this.projectService.getEstimation(this.projectId).subscribe((res:any)=>{
      this.estimateList = res?.data[0];
    },error=>{
      console.error('Error fetching estimation points:', error);
    });
  }

  formatEstimates() {
  if (!this.estimateList) return '';

  if (this.estimateList.estimateSystem === 'POINTS' || this.estimateList.estimateSystem === 'CATEGORY') {
    return this.estimateList.custom.join(', ');
  }

  if (this.estimateList.estimateSystem === 'TIME') {
    return this.estimateList.custom
      .map(c => {
        if (c.min === '00') {
          return `${c.hr}hr`;
        }else if (c.hr === '00') {
          return `${c.min}min`;
        }
        return `${c.hr}hr ${c.min}min`;
      })
      .join(', ');
  }

  return '';
}

//EPICS
property = {
  title: '',
  description: '',
  type: '',
  mandatory: false,
  active: true,
  dropDownOption:'',
  typeSubOption:'',
  typeOption:''
};

newPropertyObj = {
  title: '',
  description: '',
  type: '',
  mandatory: false,
  active: true,
  propertyTypeOptions : {
    attribute:{type:'',value:'',option:{list:[],default:''}},
    text:'',
  }

}




  customProperties: PropertyBox[] = [];

  onEpicCreate() {
    this.customProperties.push({
      title: '',
      description: '',
      type: 'Select Type',
      typeOption: 'singleselect',
      typeSubOption:'',
      mandatory: false,
      active: false,
      typeSubOptions: ['']
    });
  }

     createEpicAPI(index:any,res:any){
       let payload = {
         projectId: this.projectId,
         title: res.title,
         description: res.description,
         active: res.active,
         mandatory: res.mandatory,
         propertyType: {
           value: res.type,
           attributeType: res.typeOption,
           attributeValue: res.typeSubOption,
           attributeOptions: res.typeSubOptions
         }
       }
    this.projectService.createEPicProperty(payload).subscribe((res:any)=>{
      this.customProperties.splice(index, 1);
      this.getAllEpicProperties();
    },error=>{
      console.error('Error fetching estimation points:', error);
    });
  }
 
   updateEpicAPI(index:any,res:any){
    delete res.isEdit;
      this.projectService.createEPicProperty(res).subscribe((res:any)=>{
    
      this.getAllEpicProperties();
    },error=>{
      console.error('Error fetching estimation points:', error);
    });

  }

  onEpicCancel(index: number) {
    this.customProperties.splice(index, 1);
  }
   onEditEpicCancel(res:any) {
    res.isEdit = false;
  }





   epicPropertyTypes = [
    { label: 'Text', value: 'text', icon: 'subject' },
    { label: 'Number', value: 'number', icon: 'tag' },
    // { label: 'Dropdown', value: 'dropdown', icon: 'arrow_drop_down_circle' },
    // { label: 'Boolean', value: 'boolean', icon: 'toggle_on' },
    // { label: 'Date', value: 'date', icon: 'calendar_today' },
    // { label: 'Member picker', value: 'member', icon: 'person' }
  ];




  addNewEPicProperty() {
    console.log('Add new property clicked');
  }


trackByIndex(index: number, item: any): number {
  return index;
}

optionFields:any = [''];

addOptionField(i: number) {
  if (i === this.optionFields.length - 1) {
    this.optionFields.push('');
  }
}

  getProprtyIcons(condition:any){
    switch (condition) {
      case 'Text':
        return 'subject';
      case 'number':
        return 'tag';
      case 'dropdown':
        return 'arrow_drop_down_circle';
     case 'boolean':
        return 'toggle_on';
      case 'date':
        return 'calendar_today';
     case 'member':
        return 'person';
      default:
        return '';
    }
  }

properties = [
  {
    icon: 'format_align_left',
    label: 'title',
    help: true,
    badges: [{text: 'Read only', type: 'readonly'}, {text: 'Default', type: 'default'}],
    status: 'Active'
  },
  {
    icon: 'person',
    label: 'member',
    badges: [{text: 'Multi select', type: 'multi'}, {text: 'Default', type: 'default'}],
    status: 'Active'
  },
  {
    icon: 'format_align_left',
    label: 'hello',
    help: true,
    badges: [{text: 'Paragraph', type: 'paragraph'}],
    status: 'Active'
  },
  {
    icon: 'expand_more',
    label: 'dropdown',
    help: true,
    badges: [{text: 'Single select', type: 'single'}, {text: 'Default', type: 'default'}],
    status: 'Active'
  },
  {
    icon: 'expand_more',
    label: 'multi select',
    help: true,
    badges: [{text: 'Multi select', type: 'multi'}, {text: 'Default', type: 'default'}],
    status: 'Active'
  }
];


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

  selectedModeType:any;
   editDialog(event: MouseEvent,res:any) {
    this.selectedModeType = '';
    const position = this.getButtonPosition(event, window.innerWidth * 0.10, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '13%',
      height: 'fit-content',
      position: { top: position.top, right: position.right },
      data: { status: 'EPIC_EDIT', selectedMoreType: this.selectedModeType }
    });
    
    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        console.log('selected opt::',result.value);
        if(result.value === 'EDIT'){
          res.isEdit = true;
        }else{
          this.deleteEpicProperty(res);
        }
      }
    });
  }
  customPropertiesList:any[] = [];
    getAllEpicProperties(){
    this.projectService.getAllEpicProperties(this.projectId).subscribe((res:any)=>{
  this.customPropertiesList = res.data.map((item: any) => ({
  ...item,
  isEdit: false // add your new field here
}));

    },error=>{
      console.error('Error fetching estimation points:', error);
    });
  }


  

  deleteEpicProperty(res: any) {
    console.log('response recived', res);
    let dialog = this.masterService.openDeleteDialog(
      CustomDeleteComponent,
      'auto',
      'auto',
      {
        heading: "Delete Custom Property",
        subText: "Are you sure you want to delete this item?",
        secondaryButton: "Cancel", primaryButton: "Delete"
      },
      '80vw',

    );
    dialog.afterClosed().subscribe((data) => {
      console.log('deleted::', data);
      if (data.response === "success") {
        this.projectService.deleteEpicProperty(res.id).subscribe((res: any) => {
          this.getAllEpicProperties();
        }, error => {
          console.error('Error fetching estimation points:', error);
        });
      }
    });
  }




}