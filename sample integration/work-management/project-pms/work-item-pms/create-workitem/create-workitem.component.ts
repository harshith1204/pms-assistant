import { Component, ElementRef, HostListener, Inject, OnDestroy, OnInit, Optional, ViewChild } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialog, MatDialogRef } from '@angular/material/dialog';
import { WorkManagementService } from '../../../work-management.service';
import { PopupPmsComponent } from '../../popup-pms/popup-pms.component';
import { EventEmmiterService } from '../../../../../../services/event-emmiter.service';
import { filter } from 'rxjs/operators';
import { StorageKeys } from 'src/app/shared-module-files/simpo.constant';
import { QuillModule } from 'ngx-quill';
import { ComponentImageUploadService } from 'src/app/services/component-image-upload.service';

interface AiGeneratedPayload {
  title?: string;
  name?: string;
  description?: string;
  content?: string;
  [key: string]: any;
}

@Component({
  selector: 'app-create-workitem',
  templateUrl: './create-workitem.component.html',
  styleUrls: ['./create-workitem.component.scss']
})
export class CreateWorkitemComponent implements OnInit, OnDestroy {

  screenWidth: any;
  bDetails: any;
  businessName: any;
  businessId: any;
  projectId:any;
  projectName:any;
  response: any;
  isCreateMore: boolean = false;
  isSaving: boolean = false;
  work_title:any;
  work_description:any;
  templateData: any = null;
  userPrompt: string = '';
  showTemplatePreview: boolean = false;
  isTemplatesMode: boolean = false;
  selectedTemplate: any = null;
  searchTerm: string = '';
  filteredTemplates: any[] = [];
@ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;
selectedAttachment: File | null = null;
selectedAttachmentName: string | null = null;
selectedAttachmentPreview: string | null = null;
isAttachmentAdded:boolean = false;
  property: any;
  customPropertiesList: any[] = [];  @HostListener('window:resize', ['$event'])
  getScreenSize(event?: any) {
    this.screenWidth = window.innerWidth;
  }
     selectedStates: any = null;
  selectedPriority: any = { name: 'None', class: 'none' };
  selectedEstimatedTime: any = null;
  selectedAssignees: any = [];
  selectedLabels: any = [];
  selectedCycle: any = null;
  selectedModule: any = null;
  selectedParent: any = null;
  selectedStartDate: Date | string | null = null;
  selectedDueDate: Date | string | null = null;
  projectSettingsData:any;
  workitemLabel: any = {};

    constructor(
      private dialogRef: MatDialogRef<CreateWorkitemComponent>,
      private projectService:WorkManagementService,
      private eventEmitter: EventEmmiterService,
          private _imageUpload: ComponentImageUploadService,
      
        @Optional() @Inject(MAT_DIALOG_DATA) public data: any,
        private matDialog: MatDialog,
    ) {}

  status: any;
  selectedId: any;
  selectedFeature:any;
  feature: any;
  mode:any;
selectedDefaultState: any;


// formFields = [
//   {
//     icon: 'drag_indicator',
//     label: 'testing1',
//     required: true,
//     tooltip: 'Info about testing1',
//     type: 'text',
//     placeholder: 'Add text',
//   },
//   {
//     icon: 'tag',
//     label: 'testing2',
//     required: true,
//     tooltip: 'Info about testing2',
//     type: 'number',
//     placeholder: 'Add number',
//   },
//   {
//     icon: 'check_circle',
//     label: 'testing3',
//     required: true,
//     tooltip: 'Info about testing3',
//     type: 'select',
//     placeholder: 'Select an option',
//     options: [
//       { value: 'option1', label: 'Option 1' },
//       { value: 'option2', label: 'Option 2' },
//     ],
//   },
//   {
//     icon: 'toggle_off',
//     label: 'testing4',
//     required: false,
//     tooltip: 'Info about testing4',
//     type: 'toggle',
//   },
//   {
//     icon: 'calendar_today',
//     label: 'testing5',
//     required: true,
//     tooltip: 'Info about testing5',
//     type: 'date',
//     placeholder: 'Choose date',
//   },
//   {
//     icon: 'group',
//     label: 'testing6',
//     required: true,
//     tooltip: 'Info about testing6',
//     type: 'select',
//     placeholder: 'Select a member',
//     options: [
//       { value: 'member1', label: 'Member 1' },
//       { value: 'member2', label: 'Member 2' },
//     ],
//   },
//   {
//     icon: 'drag_indicator',
//     label: 'testing1',
//     required: true,
//     tooltip: 'Info about testing1',
//     type: 'textarea',
//     placeholder: 'Description',
//   },
//   {
//     icon: 'drag_indicator',
//     label: 'testing1',
//     required: true,
//     tooltip: 'Info about testing1',
//     type: 'static-text',
//     value: 'Sample Text',
//   },
//   {
//     icon: 'check_circle',
//     label: 'testing3',
//     required: true,
//     tooltip: 'Info about testing3',
//     type: 'multi-select',
//     placeholder: 'Select options',
//     options: [
//       { value: 'option1', label: 'Option 1' },
//       { value: 'option2', label: 'Option 2' },
//       { value: 'option3', label: 'Option 3' },
//     ],
//   },
//   {
//     icon: 'group',
//     label: 'testing6',
//     required: true,
//     tooltip: 'Info about testing6',
//     type: 'multi-select',
//     placeholder: 'Select a member',
//     options: [
//       { value: 'member1', label: 'Member 1' },
//       { value: 'member2', label: 'Member 2' },
//     ],
//   }
// ];


  ngOnInit(): void {

     this.projectId = this.data?.projectData?.projectId;
     this.projectName = this.data?.projectData?.projectName;
     this.projectSettingsData = this.data?.projectData;
     this.selectedId = this.data?.selectedId || null;
     this.selectedFeature = this.data?.feature || null;
     this.feature = this.data?.projectData?.features || null;
     console.log("ffsfrff", this.feature)
     this.mode = this.data?.mode;

    // Check if this is templates mode
    this.isTemplatesMode = this.data?.mode === 'TEMPLATES';

    this.selectedStates = this.data?.state

    // Handle template data if provided
    if (this.data?.template) {
      this.templateData = this.data.template;
      this.userPrompt = this.data.prompt || '';
      this.showTemplatePreview = true;
      this.initializeFromTemplate();
    }

    if (this.isTemplatesMode) {
      this.loadTemplates();
    }

    //  this.selectedStatus = this.projectSettingsData.states[0];
    this.getallModules();
    this.status= this.data?.status;
    if(this.data?.feature === 'MODULE'){
      this.selectedModule = {
        id: this.data?.selectedId || null,
        name: this.data?.selectedName || null
      };
    }
    if(this.data?.feature === 'CYCLE'){
      this.selectedCycle = {
        id: this.data?.selectedId || null,
        name: this.data?.selectedName || null
      };
    }
    if(this.data?.status=='PARENT'){
      this.selectedParent = {
        id: this.data?.item?.id || null,
        name: this.data?.item?.title || null
      }
      this.selectedCycle = {
        id: this.data?.item?.cycle?.id || null,
        name: this.data?.item?.cycle?.name || null
      }
      this.selectedModule = {
        id: this.data?.item?.modules?.id || null,
        name: this.data?.item?.modules?.name || null
      };
      this.selectedStates = {
        id: this.data?.item?.state?.id || null,
        name: this.data?.item?.state?.name || null
      }
      this.selectedAssignees = this.data?.item?.assignee?.map((assignee: any) => ({
        id: assignee?.id || null,
        name: assignee?.name || null
      })) || [];
      this.selectedLabels = this.data?.item?.label?.map((label: any) => ({
        id: label?.id || null,
        name: label?.name || null
      })) || [];
      this.selectedStartDate = this.data?.item?.startDate || null;
      this.selectedDueDate = this.data?.item?.endDate || null;
      // this.selectedPriority = this.data?.item?.priority || null;
    }
    // this.moduleIdAndName();
    this.businessId = localStorage.getItem('businessId');
    this.getAllCycles();
    this.getAllSubStateList();
    this.getAllLabels();
    this.getProjectMembers();
    this.getWorkItemList();
    this.getEstimation();
this.getAllEpicProperties();
  }



  initializeFromTemplate(): void {
    if (this.templateData) {
      // Pre-fill form with template data
      this.work_title = this.templateData.title || '';
      this.work_description = this.normalizeIncomingDescription(this.templateData.content || '');

      // Priority from templates removed per UI changes

      // Set estimated time if provided
      if (this.templateData.estimatedTime) {
        this.selectedEstimatedTime = { value: this.templateData.estimatedTime };
      }

      // Set labels if provided
      if (this.templateData.labels) {
        this.selectedLabels = this.templateData.labels.map((labelName: string) => ({
          name: labelName,
          id: this.generateLabelId(labelName)
        }));
      }

      // Set state if provided
      if (this.templateData.state) {
        this.selectedStates = { name: this.templateData.state };
      }

      console.log('Template data initialized:', this.templateData);
    }
  }

  private normalizeIncomingDescription(raw: any): string {
    if (raw === null || raw === undefined) {
      return '';
    }

    let text: string;

    if (typeof raw === 'string') {
      text = raw;
    } else if (typeof raw === 'object') {
      try {
        text = JSON.stringify(raw);
      } catch {
        text = String(raw);
      }
    } else {
      text = String(raw);
    }

    if (!text) {
      return '';
    }

    // Handle fenced blocks like ```json ... ```
    const fenceMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
    const inside = fenceMatch ? fenceMatch[1] : text;

    // Try to extract JSON object and use its description
    try {
      const start = inside.indexOf('{');
      const end = inside.lastIndexOf('}');
      if (start !== -1 && end !== -1 && end > start) {
        const jsonSlice = inside.substring(start, end + 1);
        const parsed = JSON.parse(jsonSlice);
        if (parsed && typeof parsed === 'object' && parsed.description) {
          return String(parsed.description);
        }
      }
    } catch {
      // ignore parsing errors and fall back to raw text
    }

    // If JSON not found, but inside a fence, use the inner text without the fences
      return this.removeMarkdownHeadings(inside);
  }

  private removeMarkdownHeadings(text: string): string {
  return text.replace(/^#{1,6}\s+(.+)$/gm, '$1');
}

  generateLabelId(labelName: string): string {
    // Generate a simple ID based on label name
    return labelName.toLowerCase().replace(/\s+/g, '-');
  }

  onCancel(){
    this.dialogRef.close();
     this.projectId = this.data;
  }

  onSave(){
    if(this.data?.mode === 'EPIC'){
      this.CreateEpic();
    }else{
    this.createWorkItemAPI();
    }
  }

  onAssignee(event: MouseEvent) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    data: { status: 'ASSIGNEE',members:this.membersList, selectedAssignees: this.selectedAssignees }
  });
  
  dialogRef.afterClosed().subscribe(result => {
    if (result && result.finalSelection && Array.isArray(result.assignees)) {
      this.selectedAssignees = result.assignees;
      return;
    }

    if (!result) return;
    const item = (result as any).item ?? result;
    if (item && typeof item === 'object' && 'id' in item) {
      if ((result as any).isAlreadySelected) {
        this.selectedAssignees = this.selectedAssignees.filter(a => a.id !== item.id);
      } else {
        if (!this.selectedAssignees.find(a => a.id === item.id)) {
          this.selectedAssignees.push(item);
        }
      }
    }
  });
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
    height: '25%',
    position: { top: position.top, right: position.right },
    data: { status: 'PRIORITY', selectedPriority: this.selectedPriority }
  });
  
  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      this.selectedPriority = result;
    }
  });
}

 onEstimateTime(event: MouseEvent) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    data: { status: 'ESTIMATE_TIME', estimatedList:this.estimatedList,estimatedSystem:this.estimateSystem, selectedEstimatedTime: this.selectedEstimatedTime }
  });
  
  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      this.selectedEstimatedTime = result;
    }
  });
}

onStatus(event: MouseEvent) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    data: { status: 'STATUS', states: this.subStateList, selectedState: this.selectedStates }
  });
  
  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      this.selectedStates = result;
    }
  });
}

        
 onLables(event: MouseEvent) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    data: { status: 'LABEL', label: this.labelsList, selectedLabels: this.selectedLabels }
  });
  
  dialogRef.afterClosed().subscribe(result => {
    if (result && result.finalSelection && Array.isArray((result as any).labels)) {
      this.selectedLabels = (result as any).labels;
      return;
    }

    if (!result) return;
    const item = (result as any).item ?? result;
    if (item && typeof item === 'object' && 'id' in item) {
      if ((result as any).isAlreadySelected) {
        // Remove from selection if it was already selected
        this.selectedLabels = this.selectedLabels.filter(l => l.id !== item.id);
      } else {
        // Add to selection if it wasn't selected
        if (!this.selectedLabels.find(l => l.id === item.id)) {
          this.selectedLabels.push(item);
        }
      }
    }
  });
}
  onCycle(event: MouseEvent) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    data: { status: 'CYCLE', cycle: this.cycleList, selectedCycle: this.selectedCycle }
  });
  
  dialogRef.afterClosed().subscribe(result => {
    if (result !== undefined) {
      this.selectedCycle = result;
    }
  });
}

 onModule(event: MouseEvent) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    data: { status: 'MODULE', module: this.moduleList, selectedModule: this.selectedModule }
  });
  
  dialogRef.afterClosed().subscribe(result => {
    if (result !== undefined) {
      // result can be null (unselect) or an object (select)
      this.selectedModule = result;
    }
  });
}

onAddParent(event: MouseEvent) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.7, window.innerHeight * 0.44);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '50%',
    height: '44%',
    position: { top: position.top, right: position.right },
    data: { status: 'PARENT', parent: this.workItemList }
  });
  
  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      this.selectedParent = result;
    }
  });
}


onAddAttachment(event: MouseEvent) {
  this.fileInput.nativeElement.click();
}


removeAttachment(event: MouseEvent) {
  event.stopPropagation();
  this.selectedAttachment = null;
  this.selectedAttachmentName = null;
  this.selectedAttachmentPreview = null;
}

onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files.length > 0) {
    const file = input.files[0];
    this.selectedAttachment = file;
    this.selectedAttachmentName = file.name;
    this.isAttachmentAdded = true;
  }
}

 onStartDate(event: MouseEvent) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.5, window.innerHeight * 0.44);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '22%',
    height: 'fit-content',
    position: { top: position.top, right: position.right },
    data: { status: 'START_DATE' }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      this.selectedStartDate = result;
      console.log('this.selectedStartDate ',this.selectedStartDate );
    }
  });
}
onDueDate(event: MouseEvent) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.5, window.innerHeight * 0.44);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '22%',
    height: 'fit-content',
    position: { top: position.top, right: position.right },
    data: { status: 'DUE_DATE' }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      const startDate = this.selectedStartDate ? new Date(this.selectedStartDate) : null;
      const dueDate = new Date(result);

      if (startDate && dueDate < startDate) {
        // alert('Due date cannot be earlier than start date.');
         this.projectService.openSnack('Due date cannot be earlier than start date.', 'Ok');
        return;
      }

      this.selectedDueDate = result;
      console.log('this.selectedDueDate', this.selectedDueDate);
    }
  });
}


  formatDate(date: Date | string | null, type: 'start' | 'due'): string {
    if (!date) {
      return type === 'start' ? 'Start date' : 'Due date';
    }
    
    // Handle both Date objects and date strings
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    return dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  getAssigneesText(): string {
    if (this.selectedAssignees.length === 0) return 'Assignees';
    if (this.selectedAssignees.length === 1) return this.selectedAssignees[0]?.name ?? 'Assignee';
    return `${this.selectedAssignees.length} assignees`;
  }

  getLabelsText(): string {
    if (this.selectedLabels.length === 0) return 'Labels';
    if (this.selectedLabels.length === 1) return this.selectedLabels[0]?.name ?? 'Label';
    return `${this.selectedLabels.length} labels`;
  }

  removeAllAssignees(event: Event) {
    event.stopPropagation(); 
    this.selectedAssignees = [];
  }

  removeAllLabels(event: Event) {
    event.stopPropagation(); 
    this.selectedLabels = [];
  }

  
  removeStates(event: Event) {
    event.stopPropagation();
    this.selectedStates = []; 
  }

  removePriority(event: Event) {
    event.stopPropagation();
    this.selectedPriority = { name: 'None', class: 'none' }; 
  }
  removeEstimatedTime(event: Event) {
    event.stopPropagation();
    this.selectedEstimatedTime = null; 
  }

  removeStartDate(event: Event) {
    event.stopPropagation();
    this.selectedStartDate = null;
  }

  removeDueDate(event: Event) {
    event.stopPropagation();
    this.selectedDueDate = null;
  }

  removeCycle(event: Event) {
    event.stopPropagation();
    this.selectedCycle = null;
  }

  removeModule(event: Event) {
    event.stopPropagation();
    this.selectedModule = null;
  }

  removeParent(event: Event) {
    event.stopPropagation();
    this.selectedParent = null;
  }

  removAttachment(event: Event) {
    event.stopPropagation();
    this.selectedParent = null;
  }


  async addAttachment(wId: any) {
  const staffId = localStorage.getItem('staffId');
  const staffName = localStorage.getItem('staffName');
  const workitemId = wId;

  try {
    const uploadedUrl: any = await this._imageUpload.uploadComponentsImages(
      this.selectedAttachment,
      'WorkItemAttachments'
    );

    if (!uploadedUrl) {
      this.projectService.openSnack('File upload failed', 'Ok');
      return;
    }


    const payload = {
      url: uploadedUrl.Location, 
      name: this.selectedAttachmentName,
      staff: {
        id: staffId,
        name: staffName
      }
    };

    console.log('Uploading attachment payload:', payload);
    this.projectService.addAttachment(workitemId, payload).subscribe({
      next: (res: any) => {
      
        this.isAttachmentAdded = false;
        this.selectedAttachment = null;
        this.selectedAttachmentName = null;
         this.dialogRef.close(true);
         this.isSaving = false;
         this.projectService.openSnack('Work item created successfully','Ok')
      },
      error: (error) => {
        console.error('Error adding attachment:', error);
        this.projectService.openSnack('Failed to add attachment', 'Ok');
      }
    });
  } catch (err) {
    console.error('Error during upload:', err);
    this.projectService.openSnack('Upload failed', 'Ok');
  }
}

onPasteImage(event: ClipboardEvent) {
  const items = event.clipboardData?.items;
  if (!items) return;

  // ✅ Convert DataTransferItemList → Array
  const itemsArray = Array.from(items);

  for (const item of itemsArray) {
    if (item.type.indexOf('image') === 0) {
      const file = item.getAsFile();
      if (file) {
        // Upload the image to your storage
    this._imageUpload.uploadComponentsImages(file, 'WorkItemDescription')
  .then((uploadedUrl) => {
    const url = uploadedUrl as string; // ✅ cast unknown → string

    const selection = window.getSelection();
    if (selection && selection.rangeCount > 0) {
      const img = document.createElement('img');
      img.src = url;
      img.style.maxWidth = '100%';
      selection.getRangeAt(0).insertNode(img);
    }
  })
  .catch((err) => console.error('Image upload failed:', err));

      }
    }
  }
}





  createWorkItemAPI(){
    if (!this.work_title || this.work_title.trim() === '') {
      this.projectService.openSnack('Please enter the work item title', 'Ok');
      return;
    }
    
    this.isSaving = true;
    let bDetails = window.localStorage.getItem('bDetails') || ''

   
    if (bDetails) {
      this.bDetails = JSON.parse(bDetails)
      this.businessName = this.bDetails.name;
      this.businessId = this.bDetails?.id || '';
    }

  //  const assignees = (this.selectedAssignees || [])
  // .filter(a => a.memberId)
  // .map(a => ({ id: a.memberId, name: a.name }));

    let payload = {
      title: this.work_title,
      description:this.work_description,
      startDate:this.selectedStartDate,
      endDate:this.selectedDueDate,
      label: this.selectedLabels,
      state: this.selectedStates ? {id:  this.selectedStates.id, name:  this.selectedStates.name} : null,
      createdBy:{
        id: localStorage.getItem(StorageKeys.STAFF_ID),
        name: localStorage.getItem(StorageKeys.STAFF_NAME)
      },
      priority:this.selectedPriority.name.toUpperCase(),
      estimate: this.selectedEstimatedTime ? this.selectedEstimatedTime : null,
      estimateSystem: this.estimateSystem,
      status:'ACCEPTED',
      assignee:this.selectedAssignees,
      modules: this.selectedModule,
      cycle: this.selectedCycle,
      // modules: this.data?.feature == 'MODULE' ? { id: this.data?.selectedId, name: this.data?.selectedName } : (this.selectedModule ? { id: this.selectedModule?.id, name: this.selectedModule?.name } : null),
      // modules: this.data?.status == 'MODULE' ? { id: this.data?.moduleId, name: this.data?.moduleName } : (this.selectedModule ? { id: this.selectedModule?.id, name: this.selectedModule?.name } : null),
      // cycle: this.data?.status=='CYCLE' ? { id: this.data?.cycleId, name: this.data?.cycleName } : (this.selectedCycle ? { id: this.selectedCycle?.id, name: this.selectedCycle?.name } : null),
      // cycle: this.data?.feature == 'CYCLE' ? { id: this.data?.selectedId, name: this.data?.selectedName } : (this.selectedCycle ? { id: this.selectedCycle?.id, name: this.selectedCycle?.name } : null),
      parent: this.data?.status=='PARENT' ? { id: this.data?.item?.id, name: this.data?.item?.title } : (this.selectedParent ? { id: this.selectedParent?.id, name: this.selectedParent?.name } : null),
      // modules:{id: '', name: ''},
      project:{id: this.projectId, name: this.projectName},
      // view:{id: '', name: ''},
      business: { id: this.businessId, name: this.businessName },
      // members:{id: '', name: ''},
      // lead: { id: '', name: '' },
    }
   
  
    this.projectService.createWorkItem(payload).subscribe({
      next: (res: any) => {
        if(!this.isAttachmentAdded){
     this.isSaving = false;
        }
        if(!this.isCreateMore && !this.isAttachmentAdded){
            this.dialogRef.close(true);
        }else{
          this.work_title = '';
           this.work_description = '';
    //          this.selectedCycle = null;
    // this.selectedModule =  null;
    // this.selectedParent = null;
    // this.selectedStartDate = null;
    // this.selectedDueDate = null;
    // this.selectedStates = this.projectSettingsData.states[0];
    // this.selectedPriority = { name: 'None', class: 'none' };
    // this.selectedEstimatedTime = null;
    // this.selectedAssignees = [];
    // this.selectedLabels = [];
        }
        this.response = res.data;
        if(this.isAttachmentAdded){
          this.addAttachment(this.response.id);
        }
       
        // this.projectService.openSnack('Work item created successfully','Ok')
      },
      error: (error) => {
        this.isSaving = false;
        console.error('Error creating work item:', error);
        this.projectService.openSnack('Error creating work item','Ok')
      }
    })
  }

  moduleList: any;
  getallModules(){
    let payload = {
      projectId: this.projectSettingsData.projectId,
      businessId: localStorage.getItem('businessId')
    }
    this.projectService.getAllModules(payload).subscribe({
      next: (response: any) => {
        this.moduleList = response.data;
        
      },
      error: (error) => {
        console.error('Error fetching modules:', error);
      }
    });
  }

  cycleList: any;
  getAllCycles() {
    this.projectService.getCycleById(this.businessId,this.projectId).subscribe({
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

  subStateList:any[] = [];
  stateList:any;
  getAllSubStateList(){
    this.projectService.getAllSubStatesList(this.projectId).subscribe({
      next: (response: any) => {
        this.stateList = response.data;
        this.subStateList = this.stateList.flatMap((state: any) => 
        state.subStates.map((subState: any) => ({
          ...subState,
          stateName: state.name,  // Add parent state name for reference
          stateId: state.id       // Add parent state ID for reference
        }))
      );
        
      },
      error: (error) => {
        console.error('Error fetching sub-states:', error);
      }
    });
  }

  labelsList: any= [];
  getAllLabels() {
  let projectId = this.projectId;
  this.projectService.getAllLabels(projectId).subscribe(
    (res: any) => {
      this.labelsList = res.data || [];
      
    },
    (error: any) => {
      console.error('Error fetching labels:', error);
    }
  );
}

membersList:any;
getProjectMembers() {
  let projectId = this.projectId;
  this.projectService.getAllMembers(projectId).subscribe(
    (res: any) => {
      this.membersList = res.data || [];
      
    },
    (error: any) => {
      console.error('Error fetching members:', error);
    }
  );
}

workItemList:any;
getWorkItemList(){
  let payload = {
    projectId: this.projectId,
    businessId: this.businessId
  }
  this.projectService.getAllWorkItems(payload).subscribe(
    (res: any) => {
      this.workItemList = res.data || [];
      console.log('Fetched work items:', this.workItemList);
    },
    (error: any) => {
      console.error('Error fetching work items:', error);
    }
  );
}

  moduleId: any;
  moduleName: any;
  moduleSelected:any;
  moduleData: any;
//   moduleIdAndName() {
//   this.moduleSelected = this.eventEmitter.showButton.asObservable()
//     .pipe(
//       filter(res => res !== null)
//     )
//     .subscribe((res: any) => {
//       
//       this.moduleData = res;
//     });
// }

  
  ngOnDestroy() {
    if (this.moduleSelected) {
      this.moduleSelected.unsubscribe();
    }
  }

  quillModules = {
  toolbar: false,
  clipboard: {
    matchVisual: false
  }
};

onEditorCreated(quill: any) {
  // Prevent pasting images
  quill.clipboard.addMatcher('IMG', () => null);
  // If we have a plain-text description (no delta), paste as text
  if (typeof this.work_description === 'string') {
    try {
      quill.setText(this.work_description);
    } catch {}
  }
}

  // Templates functionality
  loadTemplates(): void {
    const templates = [
      {
        id: 'bug-fix',
        name: 'Bug Fix',
        description: 'Report and track software bugs and issues',
        title: '🐛 Bug Fix: [Brief Description]',
        content: '## Bug Description\n\n## Steps to Reproduce\n\n## Expected Behavior\n\n## Actual Behavior\n\n## Additional Information\n',
        category: 'Development',
        priority: 'High',
        estimatedTime: 60,
        color: '#ef4444',
        icon: '🐛'
      },
      {
        id: 'feature-request',
        name: 'Feature Request',
        description: 'Request new features or functionality',
        title: '✨ Feature Request: [Feature Name]',
        content: '## Feature Description\n\n## Business Value\n\n## User Experience\n\n## Technical Requirements\n\n## Acceptance Criteria\n',
        category: 'General',
        priority: 'Medium',
        estimatedTime: 120,
        color: '#8b5cf6',
        icon: '✨'
      },
      {
        id: 'general-task',
        name: 'General Task',
        description: 'General work items and tasks',
        title: '📝 Task: [Task Description]',
        content: '## Task Description\n\n## Requirements\n\n## Deliverables\n\n## Notes\n',
        category: 'General',
        priority: 'Medium',
        estimatedTime: 60,
        color: '#3b82f6',
        icon: '📝'
      },
      {
        id: 'documentation',
        name: 'Documentation',
        description: 'Documentation and knowledge base updates',
        title: '📚 Documentation: [Document Title]',
        content: '## Document Title\n\n## Purpose\n\n## Content Outline\n\n## Target Audience\n\n## Review Requirements\n',
        category: 'Documentation',
        priority: 'Low',
        estimatedTime: 90,
        color: '#10b981',
        icon: '📚'
      },
      {
        id: 'research-task',
        name: 'Research Task',
        description: 'Research and investigation tasks',
        title: '🔍 Research: [Research Topic]',
        content: '## Research Topic\n\n## Research Questions\n\n## Methodology\n\n## Expected Findings\n\n## Resources Needed\n',
        category: 'Research',
        priority: 'Medium',
        estimatedTime: 180,
        color: '#f59e0b',
        icon: '🔍'
      },
      {
        id: 'code-review',
        name: 'Code Review',
        description: 'Code review and feedback',
        title: '👀 Code Review: [Component/Module]',
        content: '## Code Location\n\n## Review Focus Areas\n\n## Code Quality\n\n## Best Practices\n\n## Security Considerations\n',
        category: 'Review',
        priority: 'Medium',
        estimatedTime: 45,
        color: '#8b5cf6',
        icon: '👀'
      },
      {
        id: 'meeting-notes',
        name: 'Meeting Notes',
        description: 'Meeting notes and action items',
        title: '📅 Meeting: [Meeting Purpose]',
        content: '## Meeting Purpose\n\n## Attendees\n\n## Discussion Points\n\n## Action Items\n\n## Follow-up\n',
        category: 'Meeting',
        priority: 'Low',
        estimatedTime: 30,
        color: '#06b6d4',
        icon: '📅'
      },
      {
        id: 'technical-spike',
        name: 'Technical Spike',
        description: 'Technical investigation and prototyping',
        title: '🔬 Technical Spike: [Investigation Topic]',
        content: '## Investigation Topic\n\n## Technical Questions\n\n## Approach\n\n## Expected Outcomes\n\n## Time Constraint\n',
        category: 'Technical',
        priority: 'High',
        estimatedTime: 240,
        color: '#f97316',
        icon: '🔬'
      }
    ];
    this.filteredTemplates = templates;
  }

  // search and categories removed per UI simplification

  selectTemplate(template: any): void {
    this.selectedTemplate = template;
  }

  cancelTemplate(): void {
    this.selectedTemplate = null;
  }

  useTemplate(): void {
    if (!this.selectedTemplate || !this.userPrompt.trim()) {
      return;
    }

    const payload = {
      prompt: this.userPrompt,
      template: {
        title: this.selectedTemplate.title,
        content: this.selectedTemplate.content
      }
    };

    this.projectService.generateWorkItemWithAI(payload).subscribe({
      next: (res: any) => {
        const parsed = this.parseAiResponse(res);
        this.work_title = parsed.title;
        this.work_description = parsed.description;
        this.isTemplatesMode = false;
        this.projectService.openSnack('Content generated successfully!', 'Ok');
      },
      error: (err) => {
        console.error('AI generation failed', err);
        this.projectService.openSnack('AI generation failed. Using template instead.', 'Ok');
        // Fallback: process locally and populate fields
        const processedTemplate = this.processTemplateWithPrompt(this.selectedTemplate, this.userPrompt);
        this.work_title = processedTemplate.title;
        this.work_description = this.normalizeIncomingDescription(processedTemplate.content);

        // Switch out of templates mode to show the regular form
        this.isTemplatesMode = false;
      }
    });
  }

  private parseAiResponse(res: any): { title: string; description: string } {
    const aggregated = this.collectGeneratedPayload(res);

    const titleCandidates = [
      aggregated.title,
      aggregated.name,
      typeof res?.title === 'string' ? res.title.trim() : undefined,
      this.selectedTemplate?.title,
      this.userPrompt?.trim()
    ];

    const descriptionCandidates = [
      aggregated.description,
      aggregated.content,
      typeof res?.description === 'string' ? res.description : undefined,
      typeof res?.content === 'string' ? res.content : undefined,
      this.selectedTemplate?.content
    ];

    const title = (titleCandidates.find(value => typeof value === 'string' && value.trim().length > 0) || '').trim();
    const rawDescription = descriptionCandidates.find(value => typeof value === 'string' && value.trim().length > 0) || '';

    return {
      title,
      description: this.normalizeIncomingDescription(rawDescription)
    };
  }

  private collectGeneratedPayload(res: any): AiGeneratedPayload {
    const buckets: Array<Record<string, any> | null> = [
      this.safeJsonParse(res),
      this.safeJsonParse(res?.data),
      this.safeJsonParse(res?.result),
      this.safeJsonParse(res?.response),
      this.safeJsonParse(res?.title),
      this.safeJsonParse(res?.description),
      this.safeJsonParse(res?.content)
    ];

    return buckets
      .filter((value): value is Record<string, any> => !!value && typeof value === 'object')
      .reduce((acc, current) => ({ ...acc, ...current }), {} as AiGeneratedPayload);
  }

  private safeJsonParse(raw: any): Record<string, any> | null {
    if (!raw) {
      return null;
    }

    if (typeof raw === 'object') {
      return raw;
    }

    if (typeof raw !== 'string') {
      return null;
    }

    const trimmed = raw.trim();
    if (!trimmed) {
      return null;
    }

    const candidates: string[] = [];

    const fenceMatch = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i);
    if (fenceMatch) {
      candidates.push(fenceMatch[1]);
    }

    candidates.push(trimmed);

    const start = trimmed.indexOf('{');
    const end = trimmed.lastIndexOf('}');
    if (start !== -1 && end !== -1 && end > start) {
      candidates.push(trimmed.substring(start, end + 1));
    }

    for (const candidate of candidates) {
      try {
        return JSON.parse(candidate);
      } catch {
        // Continue trying next candidate
      }
    }

    return null;
  }

  processTemplateWithPrompt(template: any, prompt: string): any {
    let processedTitle = template.title;
    let processedContent = template.content;

    // Simple template processing - replace placeholders with prompt content
    if (prompt) {
      processedContent += `\n\n## User Requirements\n\n${prompt}`;
    }

    return {
      ...template,
      title: processedTitle,
      content: processedContent
    };
  }

  estimatedList:any[] = [];
estimateSystem: string | null = null;
getEstimation(){
    this.projectService.getEstimation(this.projectId).subscribe((res:any)=>{
      const est = res?.data?.[0] || null;
      this.estimateSystem = est?.estimateSystem || null;
      this.estimatedList = Array.isArray(est?.custom) ? est.custom : [];
    },error=>{
      console.error('Error fetching estimation points:', error);
    });
  }
  
formatEstimatedTime(): string {
  if (!this.selectedEstimatedTime) {
    return 'Estimated Time';
  }

  if ((this.estimateSystem || '').toUpperCase() === 'TIME') {
    const hr = parseInt(this.selectedEstimatedTime?.hr ?? '0', 10) || 0;
    const min = parseInt(this.selectedEstimatedTime?.min ?? '0', 10) || 0;

    if (hr === 0 && min > 0) return `${min} min`;
    if (min === 0 && hr > 0) return `${hr} hr`;
    if (hr > 0 && min > 0) return `${hr} hr ${min} min`;
    return '0 min';
  }

  return String(this.selectedEstimatedTime);
}

// Convert badge or label into a known type (like 'dropdown', 'text', etc.)
mapBadgesToType(badges: any[]): string {
  if (!badges) return '';
  if (badges.find(b => b.type === 'multi')) return 'multi-select';
  if (badges.find(b => b.type === 'single')) return 'dropdown';
  if (badges.find(b => b.type === 'paragraph')) return 'textarea';
  if (badges.find(b => b.type === 'readonly')) return 'readonly';
  return 'text'; // default fallback
}

// Determine if it's multi-select
hasMultiSelect(badges: any[]): boolean {
  return badges?.some(b => b.type === 'multi');
}

// Convert badge type to field type
mapBadgesToFieldType(badgeType: string): string {
  switch (badgeType) {
    case 'multi-select':
      return 'multi-select';
    case 'dropdown':
      return 'select';
    case 'textarea':
      return 'textarea';
    case 'readonly':
      return 'static-text';
    default:
      return 'text';
  }
}

// Map icon by type using your existing logic
getPropertyIcon(type: string): string {
  switch (type) {
    case 'text':
      return 'subject';
    case 'number':
      return 'tag';
    case 'select':
    case 'dropdown':
      return 'arrow_drop_down_circle';
    case 'boolean':
      return 'toggle_on';
    case 'date':
      return 'calendar_today';
    case 'member':
      return 'person';
    case 'multi-select':
      return 'check_circle';
    case 'textarea':
      return 'notes';
    case 'static-text':
      return 'drag_indicator';
    default:
      return 'help';
  }
}


formFields: any[] = []; // define at the top

getAllEpicProperties() {
  this.projectService.getAllEpicProperties(this.projectId).subscribe(
    (res: any) => {
      
      if (res && res.data) {
        // ✅ Filter only active properties
        this.customPropertiesList = res?.data
          .filter((item: any) => item.active)
          .map((item: any) => ({
            ...item,
            isEdit: false,
            propertyType: {
              ...item.propertyType,
              attributeValue: ''
            }
          }));

        // ✅ Map to formFields
        this.formFields = this.customPropertiesList.map((item: any) => {
          const type = this.mapToFieldType(item.propertyType?.value);
          const field: any = {
            icon: this.getPropertyIcon(item.propertyType?.value),
            label: item.title,
            required: item.mandatory || false,
            tooltip: item.description || '',
            type: type,
            placeholder: item.title || '',
            attributeValue: ''
          };

          // Handle options (if dropdown or multiselect)
          if (type === 'select' || type === 'multi-select') {
            field.options = (item.propertyType?.attributeOptions || []).map((opt: string) => ({
              label: opt,
              value: opt
            }));
          }

          return field;
        });
      }
    },
    error => {
      console.error('Error fetching epic properties:', error);
    }
  );
}
  // mapToFieldType(value: any) {
  //   throw new Error('Method not implemented.');
  // }


mapToFieldType(value: string): string {
  switch(value) {
    case 'text':
    case 'textarea':
      return 'text';
    case 'number':
      return 'number';
    case 'dropdown':
    case 'select':
      return 'select';
    case 'multi-select':
      return 'multi-select';
    case 'boolean':
      return 'boolean';
    case 'date':
      return 'date';
    case 'member':
      return 'member';
    case 'static-text':
    case 'readonly':
      return 'static-text';
    default:
      return 'text';
  }
}


attributeValue:any
CreateEpic(){
  if (!this.work_title || this.work_title.trim() === '') {
      this.projectService.openSnack('Please enter the work item title', 'Ok');
      return;
    }
    
    this.isSaving = true;
    const businessId = localStorage.getItem('businessId');
    const businessName = localStorage.getItem('businessName');

  let payload = {
    title: this.work_title,
    description: this.work_description,
    startDate: this.selectedStartDate,
    endDate: this.selectedDueDate,
    label: this.selectedLabels,
    state: this.selectedStates ? { id: this.selectedStates.id, name: this.selectedStates.name } : null,
    createdBy: {
      id: localStorage.getItem(StorageKeys.STAFF_ID),
      name: localStorage.getItem(StorageKeys.STAFF_NAME)
    },
    priority: this.selectedPriority.name.toUpperCase(),
    assignee: this.selectedAssignees,
    project: { id: this.projectId, name: this.projectName },
    business: { id: businessId, name: businessName },
    customProperties: (this.customPropertiesList || []).map((prop: any,index: number) => ({
      id: prop.id,
      projectId: prop.projectId,
      title: prop.title,
      description: prop.description,
      propertyType: {
        value: prop.propertyType?.value || '',
        attributeType: prop.propertyType?.attributeType || '',
        attributeValue: prop.propertyType?.attributeValue || '',
        attributeOptions: prop.propertyType?.attributeOptions || []
      },
      active: prop.active,
      mandatory: prop.mandatory,
    }))
  }

    this.projectService.createEpic(payload).subscribe({
      next: (res: any) => {
        this.isSaving = false;
        if(!this.isCreateMore){
            this.dialogRef.close(true);
        }else{
          this.work_title = '';
           this.work_description = '';
        }
        this.response = res.data;
        this.projectService.openSnack('Epic created successfully','Ok')
      },
      error: (error) => {
        this.isSaving = false;
        console.error('Error creating epic:', error);
        this.projectService.openSnack('Error creating epic','Ok')
      }
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
    });
  }

  openSurpriseMe(){
    let payload = {
      title: this.work_title,
      description: this.work_description
    }
    this.projectService.generateWithAiSurprise(payload).subscribe({
      next: (res: any) => {
        const parsed = this.parseAiResponse(res);
        this.work_title = parsed.title;
        this.work_description = parsed.description;
        this.projectService.openSnack('Content generated successfully!', 'Ok');
      },error: (err) => {
        console.error('AI generation failed', err);
        this.projectService.openSnack('AI generation failed. Please try again.', 'Ok');
      }
    }
    )
  }
}
