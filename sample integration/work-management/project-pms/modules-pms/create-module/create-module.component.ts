import { Component, Inject, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialog, MatDialogRef } from '@angular/material/dialog';
import { WorkManagementService } from '../../../work-management.service';
import { PopupPmsComponent } from '../../popup-pms/popup-pms.component';


@Component({
  selector: 'app-create-module',
  templateUrl: './create-module.component.html',
  styleUrls: ['./create-module.component.scss']
})
export class CreateModuleComponent implements OnInit {
  moduleForm: FormGroup = this.fb.group({
    title: ['', Validators.required],
    description: [''],
    dateRange: [null],
    backlog: [false],
    lead: [null],
    members: [[]]
  });

  selectedBacklogState: any = null;
  selectedLead: any = null;
  selectedMembers: any[] = [];
  projectSettingsData: any;
  startDate: Date | null = null;
  endDate: Date | null = null;
  isLoading: boolean = false;

  constructor(private fb: FormBuilder,
    private dialogRef: MatDialogRef<CreateModuleComponent>,
    private projectService: WorkManagementService,
    private matDialog: MatDialog,
    @Inject(MAT_DIALOG_DATA) public data: any,
  ) {}

  ngOnInit() {
    
    
    
    this.projectSettingsData = this.data;
    if (this.projectSettingsData?.data?.states && this.projectSettingsData.data.states.length > 0) {
      this.selectedBacklogState = this.projectSettingsData.data.states[0];
      this.moduleForm.patchValue({ backlog: true }); 
    }
    if(this.data?.module){
      this.moduleForm.patchValue({ title: this.data.module.title });
      this.moduleForm.patchValue({ description: this.data.module.description });
      this.selectedLead = this.data?.module?.lead;
      this.moduleForm.patchValue({ lead: this.selectedLead });
      this.selectedMembers = this.data.module.assignee?.name || [];
      this.moduleForm.patchValue({ members: this.selectedMembers });
      this.startDate = this.data.module.startDate ? new Date(this.data.module.startDate) : null;
      this.endDate = this.data.module.endDate ? new Date(this.data.module.endDate) : null;
      this.moduleForm.patchValue({ dateRange: { start: this.startDate, end: this.endDate } });
      this.moduleForm.patchValue({ backlog: this.data.module.state ? true : false });
      this.selectedBacklogState = this.data.module.state || null;
  }
    this.getProjectMembers();
    this.getAllSubStateList();
  }

  openDatePicker() {
  }

  changeData() {
    if (this.startDate && this.endDate && this.isValidDate(this.startDate) && this.isValidDate(this.endDate)) {
      this.moduleForm.patchValue({ 
        dateRange: { 
          start: this.startDate, 
          end: this.endDate 
        } 
      });
    }
  }

  private isValidDate(date: any): boolean {
    if (!date) return false;
    
    if (typeof date === 'string') {
      date = new Date(date);
    }
    
    return date instanceof Date && !isNaN(date.getTime());
  }

  getDateRangeText(): string {
    if (this.startDate && this.endDate) {
      try {
        const startStr = this.startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        const endStr = this.endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        return `${startStr} → ${endStr}`;
      } catch (error) {
        console.error('Date formatting error:', error);
        return 'Start date → End date';
      }
    }
    return 'Start date → End date';
  }

  clearDateRange(event: Event) {
    event.stopPropagation();
    this.startDate = null;
    this.endDate = null;
    this.moduleForm.patchValue({ dateRange: null });
  }

  toggleBacklog(event?: MouseEvent) {
    const currentValue = this.moduleForm.get('backlog')?.value;
    
    // If backlog is currently enabled, disable it and clear state
    if (currentValue) {
      this.moduleForm.patchValue({ backlog: false });
      this.selectedBacklogState = null;
    } else {
      // If backlog is disabled, enable it and show state selection popup
      this.moduleForm.patchValue({ backlog: true });
      if (event) {
        this.openBacklogStatePopup(event);
      } else {
        // Set default state if no event (should not happen in normal flow)
        this.selectedBacklogState = this.projectSettingsData?.data?.states?.[0] || null;
      }
    }
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
      top = buttonRect.bottom + margin;
    } else {
      top = buttonRect.top - dialogHeight - margin;
    }

    let right: number;
    if (spaceRight >= dialogWidth || (spaceRight < dialogWidth && spaceLeft < dialogWidth)) {
      right = viewportWidth - buttonRect.right;
    } else {
      right = viewportWidth - buttonRect.left - dialogWidth;
    }

    top = Math.max(margin, Math.min(top, viewportHeight - dialogHeight - margin + window.scrollY));
    right = Math.max(margin, Math.min(right, viewportWidth - dialogWidth - margin + window.scrollX));

    return {
      top: top + 'px',
      right: right + 'px'
    };
  }

  openBacklogStatePopup(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      data: { status: 'STATUS', states: this.subStateList  }
    });
    
    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.selectedBacklogState = result;
      }
    });
  }

  selectLead(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      disableClose: false,
      hasBackdrop: true,
      backdropClass: 'transparent-backdrop',
      data: { status: 'ASSIGNEE', members: this.membersList, selectedAssignees: this.selectedLead ? [this.selectedLead] : [] }
    });
    
    dialogRef.afterClosed().subscribe(result => {
      if (result && result.finalSelection) {
        if (result.assignees && result.assignees.length > 0) {
          this.selectedLead = result.assignees[0];
          this.moduleForm.patchValue({ lead: this.selectedLead });
        } else {
          this.selectedLead = null;
          this.moduleForm.patchValue({ lead: null });
        }
      }
    });
  }

  selectMembers(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      disableClose: false,
      hasBackdrop: true,
      backdropClass: 'transparent-backdrop',
      data: { status: 'ASSIGNEE', members: this.membersList, selectedAssignees: this.selectedMembers }
    });
    
    dialogRef.afterClosed().subscribe(result => {
      if (result && result.finalSelection) {
        this.selectedMembers = result.assignees;
        this.moduleForm.patchValue({ members: this.selectedMembers });
      }
    });
  }

  removeMember(member: any) {
    this.selectedMembers = this.selectedMembers.filter(m => m.id !== member.id);
    this.moduleForm.patchValue({ members: this.selectedMembers });
  }

  clearAllMembers() {
    this.selectedMembers = [];
    this.moduleForm.patchValue({ members: [] });
  }

  getMembersText(): string {
    if (this.selectedMembers.length === 0) return 'Members';
    if (this.selectedMembers.length === 1) return this.selectedMembers[0].name;
    return `${this.selectedMembers.length} members`;
  }

  getInitials(name: string): string {
    console.log('member name:: ',name)
    if (!name) return '';
    return name.split(' ').map(word => word.charAt(0)).join('').toUpperCase().slice(0, 2);
  }

  getAvatarColor(index: number): string {
    const colors = ['#4285f4', '#34a853', '#ea4335', '#fbbc05', '#9c27b0', '#ff9800', '#795548', '#607d8b'];
    return colors[index % colors.length];
  }

  getLeadText(): string {
    return this.selectedLead ? this.selectedLead?.name : 'Lead';
  }

  getBacklogStateText(): string {
    if (this.moduleForm.get('backlog')?.value && this.selectedBacklogState) {
      return this.selectedBacklogState.name;
    }
    return 'Backlog';
  }

  onSubmit() {
    if (this.moduleForm.valid) {
      
    }
  }

  onCancel(){
    this.dialogRef.close();
  }

  createModule() {
    if (this.isLoading) return;
    
    this.isLoading = true;

    let payload: any = {
      title: this.moduleForm.value.title,
      description: this.moduleForm.value.description,
      state: this.moduleForm.get('backlog')?.value ? this.selectedBacklogState : null,
      lead: {id:this.selectedLead?.id,name:this.selectedLead?.name},
      assignee: this.selectedMembers,
      startDate: this.startDate,
      endDate: this.endDate,
      business: {
        id: localStorage.getItem('businessId')
      },
      project: {
        id: this.data?.data?.projectId,
      },
    };

    if(this.data.edit=true){
      payload.id = this.data?.module?.id;
    }

    this.projectService.createModule(payload).subscribe({
      next: (res: any) => {
        
        this.isLoading = false;
        this.dialogRef.close(res);
      },
      error: (error: any) => {
        console.error('Error creating module:', error);
        this.isLoading = false;
      }
    });
  }

  membersList:any;
getProjectMembers() {
  let projectId = this.data?.data?.projectId
  this.projectService.getAllMembers(projectId).subscribe(
    (res: any) => {
      this.membersList = res.data || [];
      console.log('Fetched members:', this.membersList);
    },
    (error: any) => {
      console.error('Error fetching members:', error);
    }
  );
}

subStateList:any[] = [];
  stateList:any;
  getAllSubStateList(){
    const projectId = this.data?.data?.projectId;
    this.projectService.getAllSubStatesList(projectId).subscribe({
      next: (response: any) => {
        this.stateList = response.data;
        this.subStateList = this.stateList.flatMap((state: any) => 
        state.subStates.map((subState: any) => ({
          ...subState,
          stateName: state.name,  // Add parent state name for reference
          stateId: state.id       // Add parent state ID for reference
        }))
      );
        console.log('Sub-states fetched:', this.subStateList);
      },
      error: (error) => {
        console.error('Error fetching sub-states:', error);
      }
    });
  }
}
