import { Component, Inject, Input, ViewChild, ElementRef, HostListener, AfterViewInit, ChangeDetectorRef } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogRef, MatDialog } from '@angular/material/dialog';
import { WorkManagementService } from '../../../work-management.service';
import { PopupPmsComponent } from '../../popup-pms/popup-pms.component';
import { MatSnackBar } from '@angular/material/snack-bar';
import { CreateWorkitemComponent } from '../create-workitem/create-workitem.component';
import { ImageUploadService } from 'src/app/services/ImageUploadService/image-upload.service';
import { ComponentImageUploadService } from 'src/app/services/component-image-upload.service';
import { StorageKeys } from 'src/app/shared-module-files/simpo.constant';
import { stat } from 'fs';
import Quill from 'quill';
import { MastersService } from 'src/app/master-config-components/master/screens/master.service';
import { CustomDeleteComponent } from 'src/app/master-config-components/micro-apps/crm/custom-delete/custom-delete.component';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { integer } from 'aws-sdk/clients/cloudfront';
import { double } from 'aws-sdk/clients/lightsail';

@Component({
  selector: 'app-detail-workitem',
  templateUrl: './detail-workitem.component.html',
  styleUrls: ['./detail-workitem.component.scss']
})
export class DetailWorkitemComponent implements AfterViewInit {
  subWorkItemList: any[] = [];
  selectedWorkItem: any;
  isSubWorkItemsExpanded: boolean = false;
  isAttachmentsExpanded: boolean = false;
  fromScreen:any;
  showEpicProperties: boolean = true;
item: any;

  toggleSubWorkItems(): void {
    this.isSubWorkItemsExpanded = !this.isSubWorkItemsExpanded;
  }
  toggleAttachments(): void {
    this.isAttachmentsExpanded = !this.isAttachmentsExpanded;
  }

  toggleEpicProperties(event?: MouseEvent): void {
    if (event) event.stopPropagation();
    this.showEpicProperties = !this.showEpicProperties;
  }

  constructor(private dialogRef: MatDialogRef<DetailWorkitemComponent>,
        private projectService: WorkManagementService,
        private matDialog: MatDialog,
        private snackBar: MatSnackBar,
        private masterService : MastersService,
        private imageUploadService: ImageUploadService,
        private _imageUpload: ComponentImageUploadService,
        private sanitizer: DomSanitizer,
        private cdr: ChangeDetectorRef,

    @Inject(MAT_DIALOG_DATA) public data: any) { }


  ngOnInit() {
    this.fromScreen = this.data?.fromScreen || null;
    this.workitem = this.data.item;
    if(this.data?.fromScreen === 'EPIC'){
    this.getEpicDetail();
    }else{
      this.getWorkitemDetail();
    }
    this.projectData = this.data.projectData; 
    this.feature = this.data?.projectData?.features; 

  }

  wholeData: any;
  workitem: any;
  projectData: any;
  imagePreview: string | ArrayBuffer | null = null;
  updatedByList: any = [];
  attachmentsList: any;
  private timelineDataLoaded: boolean = false;
  progress: number = 0;
  isEnableAddUpdate:any= true
  
  showImagePreview: boolean = false;
  selectedAttachment: any = null;
  feature: any;

  isSubmittingComment: boolean = false;

  showLogWorkPopup: boolean = false;
  logHours: number | null = null;
logMinutes: number | null = null;
  logDescription: string = '';
  description:string='';
  id:string='';
  comment:string='';

  get logHeaderLabel(): string {
     if ((this.logHours == null || this.logHours === 0) && (this.logMinutes == null || this.logMinutes === 0)) {
    return 'Log Work';
  }
    const h = this.logHours ?? 0;
  const m = this.logMinutes ?? 0;
  return `${h}h ${m}m`;
  }

 get isLogWorkValid(): boolean {
  const hours = this.logHours ?? 0;
  const minutes = this.logMinutes ?? 0;
  const totalMinutes = hours * 60 + minutes;

  const hasDescription = !!this.logDescription && this.logDescription.trim().length > 0;
  const hasTime = totalMinutes > 0;

  return hasDescription && hasTime;
}


  openLogWorkDialog(event?: MouseEvent) {
    if (event) event.stopPropagation();
    this.showLogWorkPopup = true;
  }

  closeLogWorkDialog() {
    this.showLogWorkPopup = false;
    this.logHours = 0;
    this.logMinutes = 0;
    this.logDescription = '';
  }

 incLogHours(delta: number) {
  const current = this.logHours ?? 0; // handle null safely
  const next = current + delta;
  this.logHours = Math.max(0, next);
}

incLogMinutes(delta: number) {
  let currentMinutes = this.logMinutes ?? 0;
  let currentHours = this.logHours ?? 0;

  let next = currentMinutes + delta;

  while (next >= 60) {
    currentHours++;
    next -= 60;
  }
  while (next < 0) {
    if (currentHours > 0) {
      currentHours--;
      next += 60;
    } else {
      next = 0;
      break;
    }
  }

  this.logHours = currentHours;
  this.logMinutes = Math.max(0, Math.min(59, next));
}

saveLogWork() {
  const hours = this.logHours ?? 0;
  const minutes = this.logMinutes ?? 0;
  const totalMinutes = hours * 60 + minutes;

  const hasDescription = !!this.logDescription && this.logDescription.trim().length > 0;
  const hasTime = totalMinutes > 0;

  if (!hasDescription) {
    this.snackBar.open('Please provide a description for the work log.', 'Close', { duration: 1500 });
    return;
  }

  if (!hasTime) {
    this.snackBar.open('Please specify time (hours and/or minutes) for the work log.', 'Close', { duration: 1500 });
    return;
  }

  this.snackBar.open(
    `Logged ${this.logHeaderLabel}` + 
    (this.logDescription?.trim() ? ' • ' + this.logDescription.trim() : ''),
    'Close',
    { duration: 1500 }
  );

  this.logWork();
  this.closeLogWorkDialog();
}


  onHoursChange(val: any) {
    const n = Number(val);
    this.logHours = Number.isFinite(n) ? Math.max(0, Math.floor(n)) : 0;
  }

  onMinutesChange(val: any) {
    const n = Number(val);
    const safe = Number.isFinite(n) ? Math.floor(n) : 0;
    this.logMinutes = Math.max(0, Math.min(59, safe));
  }



  @HostListener('document:keydown.escape', ['$event'])
onEscapeKey(event: KeyboardEvent) {
  if (this.showImagePreview) {
    this.closeImagePreview();
    event.preventDefault();
  }
  if (this.showLogWorkPopup) {
    this.closeLogWorkDialog();
    event.preventDefault();
  }
  if (this.isFilterMenuOpen) {
    this.isFilterMenuOpen = false;
    event.preventDefault();
  }
}

  @HostListener('document:click')
  onDocClick() {
    if (this.showLogWorkPopup) {
      this.closeLogWorkDialog();
    }
  }

  /**
   * Auto-resize textarea based on content
   */
  autoResizeTextarea(event: any): void {
    const textarea = event.target;
    if (textarea) {
      // Reset height to recalculate
      textarea.style.height = 'auto';
      // Set height based on scroll height
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
  }

  /**
   * Initialize view after it's created
   */
  ngAfterViewInit(): void {
    // Use setTimeout to avoid ExpressionChangedAfterItHasBeenCheckedError
    setTimeout(() => {
      this.resizeAllCommentTextareas();
    }, 0);
  }

  resizeAllCommentTextareas(): void {
    const textareas = document.querySelectorAll('.comment-display-textarea');
    textareas.forEach((textarea: any) => {
      if (textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
      }
    });
  }

  initializeEditor() {  
    // Initialize editor configuration after members are loaded
    setTimeout(() => {
      console.log('Initializing editor with members:', this.membersList);
      console.log('Custom mention functionality ready');
    }, 1000); // Wait for members to load
  }
  
  private _editorContent: string = '';
  
  get editorContent(): string {
    return this._editorContent || '';
  }
  
  set editorContent(value: string) {
    this._editorContent = value || '';
  }

  showMentionPopup: boolean = false;
  mentionSearchTerm: string = '';
  filteredMembers: any[] = [];
  mentionPosition: { top: number, left: number } = { top: 0, left: 0 };
  currentEditor: any = null;
  lastMentionIndex: number = -1; // Store the @ position
  currentSelectionIndex: number = -1; // Store current cursor position

  // Handle when editor is ready
  onEditorCreated(editor: any) {
    console.log('Editor created:', editor);
    console.log('Editor type:', typeof editor);
    console.log('Editor methods:', Object.keys(editor));
    this.currentEditor = editor;
    
    // Ensure editor content is properly initialized
    if (!this.editorContent) {
      this.editorContent = '';
    }
    
    // Set initial empty content safely
    try {
      editor.setText('');
    } catch (error) {
      console.warn('Error setting initial editor text:', error);
    }
    
    console.log('Adding event listeners...');
    
    // Add multiple event listeners for better detection
    editor.root.addEventListener('keyup', (event: KeyboardEvent) => {
      console.log('Keyup event detected on editor:', event.key);
      this.handleKeyUp(event, editor);
    });

    editor.root.addEventListener('keydown', (event: KeyboardEvent) => {
      console.log('Keydown event detected on editor:', event.key);
      if (event.key === '@') {
        console.log('@ key detected on keydown');
        setTimeout(() => this.checkForMentions(), 50);
      }
    });

    editor.root.addEventListener('input', (event: any) => {
      console.log('Input event detected on editor');
      setTimeout(() => this.checkForMentions(), 50);
    });
    
    editor.root.addEventListener('click', () => {
      console.log('Click event detected on editor');
      this.hideMentionPopup();
    });

    // Also listen to Quill's text-change event
    editor.on('text-change', () => {
      console.log('Quill text-change event detected');
      setTimeout(() => this.checkForMentions(), 50);
    });
    
    // Add paste event handler to clean pasted content
    editor.root.addEventListener('paste', (event: ClipboardEvent) => {
      console.log('Paste event detected');
      setTimeout(() => {
        // Get current content and clean it
        const currentContent = editor.root.innerHTML;
        const cleanedContent = this.cleanPastedContent(currentContent);
        if (cleanedContent !== currentContent) {
          editor.root.innerHTML = cleanedContent;
        }
      }, 10);
    });
    
    console.log('Event listeners added successfully');
  }

  handleKeyUp(event: KeyboardEvent, editor: any) {
    console.log('KeyUp event triggered:', event.key);
    
    const selection = editor.getSelection();
    console.log('Selection:', selection);
    
    if (!selection) {
      console.log('No selection found');
      return;
    }

    const text = editor.getText(0, selection.index);
    console.log('Text before cursor:', text);
    console.log('Text length:', text.length);
    
    const lastAtIndex = text.lastIndexOf('@');
    console.log('Last @ index:', lastAtIndex);
    
    if (lastAtIndex !== -1) {
      const textAfterAt = text.substring(lastAtIndex + 1);
      console.log('Text after @:', textAfterAt);
      
      // Check if there's a space after @, if so, hide popup
      if (textAfterAt.includes(' ') || textAfterAt.includes('\n')) {
        console.log('Space or newline found, hiding popup');
        this.hideMentionPopup();
        return;
      }
      
      // Show mention popup
      console.log('Showing mention popup with search term:', textAfterAt);
      this.mentionSearchTerm = textAfterAt;
      this.filterMembers();
      this.showMentionPopupAt(editor, selection);
    } else {
      console.log('No @ symbol found, hiding popup');
      this.hideMentionPopup();
    }
  }

  filterMembers() {
    console.log('Filtering members...');
    console.log('Members list:', this.membersList);
    console.log('Search term:', this.mentionSearchTerm);
    
    if (!this.membersList || this.membersList.length === 0) {
      console.log('No members list available');
      this.filteredMembers = [];
      return;
    }
    
    this.filteredMembers = this.membersList.filter((member: any) => {
      const name = member.name || member.staffName || '';
      const matches = name.toLowerCase().includes(this.mentionSearchTerm.toLowerCase());
      console.log(`Member ${name} matches: ${matches}`);
      return matches;
    }).slice(0, 5); // Limit to 5 results
    
    console.log('Filtered members:', this.filteredMembers);
  }

  showMentionPopupAt(editor: any, selection: any) {
    console.log('Showing mention popup at position...');
    
    const bounds = editor.getBounds(selection.index);
    const editorRect = editor.root.getBoundingClientRect();
    
    // Store the current positions for later use
    const text = editor.getText(0, selection.index);
    this.lastMentionIndex = text.lastIndexOf('@');
    this.currentSelectionIndex = selection.index;
    
    console.log('Stored lastMentionIndex:', this.lastMentionIndex);
    console.log('Stored currentSelectionIndex:', this.currentSelectionIndex);
    
    // Use fixed positioning for better visibility
    this.mentionPosition = {
      top: bounds.top + bounds.height + editorRect.top,
      left: bounds.left + editorRect.left
    };
    
    console.log('Mention position:', this.mentionPosition);
    console.log('Bounds:', bounds);
    console.log('Editor rect:', editorRect);
    
    this.showMentionPopup = true;
    console.log('showMentionPopup set to true');
    
    // Force change detection
    setTimeout(() => {
      console.log('Popup should be visible now');
    }, 100);
  }

  hideMentionPopup() {
    this.showMentionPopup = false;
    this.mentionSearchTerm = '';
    this.filteredMembers = [];
    this.lastMentionIndex = -1;
    this.currentSelectionIndex = -1;
  }

  selectMention(member: any, event?: MouseEvent) {
    event?.stopPropagation();
    console.log('selectMention called with member:', member);
    
    if (!this.currentEditor) {
      console.log('No current editor available');
      return;
    }

    const mentionStart = this.lastMentionIndex;
    const selectionEnd = this.currentSelectionIndex;
    
    // Use stored positions instead of current selection
    if (mentionStart === -1 || selectionEnd === -1) {
      console.log('No stored mention position available');
      return;
    }
    
    console.log('Using stored lastMentionIndex:', mentionStart);
    console.log('Using stored currentSelectionIndex:', selectionEnd);
    
    // Calculate the length to delete (from @ to current cursor position)
    const deleteLength = selectionEnd - mentionStart;
    console.log('Deleting text from', mentionStart, 'length:', deleteLength);
    
    // Remove the @ and search term
    this.currentEditor.deleteText(mentionStart, deleteLength);
    
    // Insert the mention
    const memberName = member.name || member.staffName;
    const mentionText = `@${memberName} `;
    console.log('Inserting mention:', mentionText);
    this.currentEditor.insertText(mentionStart, mentionText, 'user');
    
    // Set cursor after the mention - try multiple approaches
    const newPosition = mentionStart + mentionText.length;
    console.log('Setting cursor position to:', newPosition);
    console.log('Mention text length:', mentionText.length);
    console.log('LastMentionIndex:', mentionStart);
    
    // Try immediate selection first
    this.currentEditor.setSelection(newPosition, 0);
    
    // Also try with timeout and focus
    setTimeout(() => {
      console.log('Setting cursor position with timeout...');
      this.currentEditor.focus();
      this.currentEditor.setSelection(newPosition, 0);
      
      // Verify the cursor position
      const currentSelection = this.currentEditor.getSelection();
      console.log('Current selection after setting:', currentSelection);
      
      // If selection is still wrong, try manual positioning
      if (currentSelection && currentSelection.index !== newPosition) {
        console.log('Selection mismatch, trying again...');
        this.currentEditor.setSelection(newPosition);
        
        // Final attempt with a longer delay
        setTimeout(() => {
          this.currentEditor.setSelection(newPosition, 0);
          console.log('Final cursor positioning attempt');
        }, 50);
      }
    }, 20);
    
    // Reset stored positions
    this.lastMentionIndex = -1;
    this.currentSelectionIndex = -1;
    
    this.hideMentionPopup();
  }
  
  // Handle editor content changes
  onEditorContentChanged(event: any) {
    try {
      // Safely extract the HTML content from the event
      if (event && typeof event === 'object' && event.html !== undefined) {
        this.editorContent = event.html || '';
      } else if (typeof event === 'string') {
        this.editorContent = event;
      } else if (event === null || event === undefined) {
        this.editorContent = '';
      } else {
        // Fallback for unexpected event types
        this.editorContent = '';
        console.warn('Unexpected editor event type:', typeof event, event);
      }
      
      console.log('Editor content changed:', this.editorContent);
      console.log('Type of content:', typeof this.editorContent);
      
      // Check for @ mentions on content change as well
      if (this.currentEditor) {
        this.checkForMentions();
      }
      
      // Debug mention functionality
      if (this.editorContent && this.editorContent.includes('@')) {
        console.log('@ symbol detected in content');
        console.log('Members list available:', this.membersList?.length || 0);
      }
    } catch (error) {
      console.error('Error handling editor content change:', error);
      this.editorContent = '';
    }
    this.comment = event.text.trim();
  }

  checkForMentions() {
    if (!this.currentEditor) return;
    
    const selection = this.currentEditor.getSelection();
    if (!selection) {
      console.log('No selection in checkForMentions');
      return;
    }

    const text = this.currentEditor.getText(0, selection.index);
    const lastAtIndex = text.lastIndexOf('@');
    
    console.log('checkForMentions - text:', text);
    console.log('checkForMentions - lastAtIndex:', lastAtIndex);
    console.log('checkForMentions - selection.index:', selection.index);
    
    if (lastAtIndex !== -1) {
      const textAfterAt = text.substring(lastAtIndex + 1);
      console.log('checkForMentions - textAfterAt:', textAfterAt);
      
      // Check if there's a space after @, if so, hide popup
      if (textAfterAt.includes(' ') || textAfterAt.includes('\n')) {
        console.log('Space or newline found in checkForMentions, hiding popup');
        this.hideMentionPopup();
        return;
      }
      
      // Show mention popup
      console.log('Showing mention popup from checkForMentions with search term:', textAfterAt);
      this.mentionSearchTerm = textAfterAt;
      this.filterMembers();
      this.showMentionPopupAt(this.currentEditor, selection);
    } else {
      console.log('No @ symbol found in checkForMentions, hiding popup');
      this.hideMentionPopup();
    }
  }
  // @Input() issue: any;
 editorConfig: any = {
  theme: 'snow',
  placeholder: 'Add comment...',
  modules: {
    toolbar: [
      ['bold', 'italic', 'underline', 'strike'],
      [{ 'list': 'ordered' }, { 'list': 'bullet' }],
      ['blockquote', 'code-block'],
      ['link']
    ],
    clipboard: {
      // Strip some formatting on paste but preserve basic formatting
      matchVisual: false,
      matchers: [
        // Allow basic formatting but strip complex styling
        ['span[style]', (node: any, delta: any) => {
          // Remove style attributes from spans but keep the text
          return delta.compose({ retain: delta.length() });
        }]
      ]
    }
  },
  formats: [
    'bold', 'italic', 'underline', 'strike',
    'list', 'bullet',
    'blockquote', 'code-block',
    'link'
  ]
};

epicDescriptionModules = {
  toolbar: false,
  clipboard: {
    matchVisual: false
  }
};

onEpicDescriptionEditorCreated(quill: any) {
  quill.clipboard.addMatcher('IMG', () => null);
  if (this.tempDescription) {
    quill.root.innerHTML = this.tempDescription;
  }
}

onWorkItemDescriptionEditorCreated(quill: any) {
  quill.clipboard.addMatcher('IMG', () => null);
  if (this.tempDescription) {
    quill.root.innerHTML = this.tempDescription;
  }
}


  onClose() {
    this.dialogRef.close();
  }

  submitComment() {
    if (this.isSubmittingComment) {
      return;
    }
  
    if (this.editorContent && this.editorContent.trim()) {
      this.isSubmittingComment = true;
      
      this.extractMentionedUsers();
      
      this.addcommentWorkItem();
    } else {
      console.error('No content to submit');
    }
  }
 
  

  onStateEdit(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      data: { status: 'STATUS', states: this.subStateList, selectedState: this.wholeData.state }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.wholeData.state = result;
        // this.updateWorkItemField('state', result);
        if( this.fromScreen === 'EPIC'){
           this.updateEpicProperties('state', result);
        }else{
          this.updateFunction('state', result);
        }
       
      }
    });
  }

  
  


  onPriorityEdit(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      data: { status: 'PRIORITY', selectedPriority: { name: this.wholeData.priority } }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.wholeData.priority = result.name;
        // this.updateWorkItemField('priority', result.name);
      
           if( this.fromScreen === 'EPIC'){
           this.updateEpicProperties('priority', result.name);
        }else{
   this.updateFunction('priority', result.name);
        }
      }
    });
  }

   onEstimateTime(event: MouseEvent) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '12%',
    height: '25%',
    position: { top: position.top, right: position.right },
    data: { status: 'ESTIMATE_TIME', estimatedList: this.estimatedList, estimatedSystem: this.estimateSystem, selectedEstimatedTime: this.wholeData?.estimatedList }
  });
  
  dialogRef.afterClosed().subscribe(result => {
    if (result) {
        this.wholeData.estimate = result;
        this.updateWorkItemField('estimate', result);

    }
  });
}

onDueDateEdit(event: MouseEvent) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '19%',
    height: '43%',
    position: { top: position.top, right: position.right },
    data: { status: 'DUE_DATE' }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      const startDate = this.wholeData.startDate ? new Date(this.wholeData.startDate) : null;
      const dueDate = new Date(result);

      if (startDate && dueDate < startDate) {
        this.projectService.openSnack('Due date cannot be earlier than start date.', 'Ok');
        return;
      }

      this.wholeData.endDate = result;

           if( this.fromScreen === 'EPIC'){
           this.updateEpicProperties('endDate', result);
        }else{
   this.updateFunction('endDate', result);
        }
    
    }
  });
}


onStartDateEdit(event: MouseEvent) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '19%',
    height: '43%',
    position: { top: position.top, right: position.right },
    data: { status: 'START_DATE' }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      const dueDate = this.wholeData.endDate ? new Date(this.wholeData.endDate) : null;
      const startDate = new Date(result);

      if (dueDate && startDate > dueDate) {
    
          this.projectService.openSnack('Start date cannot be later than due date.', 'Ok');
        return;
      }

      this.wholeData.startDate = result;
           if( this.fromScreen === 'EPIC'){
           this.updateEpicProperties('startDate', result);
        }else{
   this.updateFunction('startDate', result);
        }
  
    }
  });
}




  onReleaseDateEdit(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '19%',
      height: '43%',
      position: { top: position.top, right: position.right },
      data: { status: 'DUE_DATE' }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.wholeData.releaseDate = result;
        // this.updateWorkItemField('endDate', result);
        this.updateFunction('releaseDate', result);
      }
    });
  }

  onModuleEdit(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      data: { status: 'MODULE', module: this.moduleList, selectedModule: this.wholeData.modules }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result !== undefined) {
        // result can be null (unselect) or an object (select)
        this.wholeData.modules = result;
        // this.updateWorkItemField('modules', result);

       
             if( this.fromScreen === 'EPIC'){
           this.updateEpicProperties('modules', result);
        }else{
   this.updateFunction('modules', result);
        }
      }
    });
  }

  onCycleEdit(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      data: { status: 'CYCLE', cycle: this.cycleList, selectedCycle: this.wholeData.cycle }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result !== undefined) {
        this.wholeData.cycle = result === null ? [] : result;

        if (this.fromScreen === 'EPIC') {
          this.updateEpicProperties('cycle', this.wholeData.cycle);
        } else {
          this.updateFunction('cycle', this.wholeData.cycle);
        }
      }
    });
  }

  onParentEdit(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      data: { status: 'PARENT' }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.wholeData.parent = result.name;
        this.updateWorkItemField('parent', result.name);
      }
    });
  }

  onLabelEdit(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      disableClose: false,
      hasBackdrop: true,
      backdropClass: 'transparent-backdrop',
      data: { status: 'LABEL', label: this.labelsList, selectedLabels: this.wholeData.label }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result && result.finalSelection) {
        this.wholeData.label = result.labels;
    
             if (this.fromScreen === 'EPIC') {
          this.updateEpicProperties('label', this.wholeData.label);
        } else {
          this.updateFunction('label', this.wholeData.label);
        }
      }
    });
  }

  onAssigneeEdit(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      disableClose: false,
      hasBackdrop: true,
      backdropClass: 'transparent-backdrop',
      data: { status: 'ASSIGNEE', members: this.membersList, selectedAssignees: this.wholeData.assignee }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result && result.finalSelection) {
        this.wholeData.assignee = result.assignees;
        
        if( this.fromScreen === 'EPIC'){
           this.updateEpicProperties('assignee', this.wholeData.assignee);
        }else{
   this.updateFunction('assignee', this.wholeData.assignee);
        }
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

  // durationInMinutes: number = 0;
  updateWorkItemField(field: string, value: any) {
    const updateData = {
      id: this.wholeData.id,
      business: {
        id: localStorage.getItem('businessId'),
        name: localStorage.getItem('businessName')
      },
      project: {
        id: this.data?.item?.project?.id,
        name: this.data?.item?.project?.name
      },
      displayBugNo: this.wholeData.displayBugNo,
      title: this.wholeData.title,
      description: this.wholeData.description,
      priority: this.wholeData.priority,
      status: this.wholeData.status,
      assignee: this.wholeData.assignee,
      label: this.wholeData.label,
      startDate: this.wholeData.startDate,
      endDate: this.wholeData.endDate,
      modules: this.wholeData.modules,
      cycle: this.wholeData.cycle,
      parent: this.wholeData.parent,
      state: this.wholeData.state,
      createdBy: {id:this.wholeData.createdBy.id, name: this.wholeData.createdBy.name},
      updatedBy: this.updatedByList,
      estimate: this.wholeData?.estimate,
      estimateSystem: this.wholeData?.estimateSystem,
      workLogs: this.wholeData?.workLogs,
      [field]: value
    };

    
    this.projectService.updateWorkItem(updateData).subscribe((res: any) => {

      this.snackBar.open(`${field} updated successfully`, 'Close', { duration: 1000 });
      this.getTimelineData();
      this.getWorkitemDetail();
    });
  }

  updateFunction(field: string, value: any) {
    const staffId = localStorage.getItem('staffId');
  const staffName = localStorage.getItem('staffName');
    const workItemId = this.wholeData.id;
    let payload: any = {};
    if ((field === 'startDate' || field === 'endDate') && (value === null || value === undefined)) {
      if (field === 'startDate') {
        payload.isStartDateRemoved = true;
      } else {
        payload.isEndDateRemoved = true;
      }
      payload.user = {
        id: staffId,
        name: staffName
      };
    } else {
      payload[field] = value;
      payload.user = {
        id: staffId,
        name: staffName
      };
    }
    this.projectService.updateWorkitemFields(workItemId, payload).subscribe((res: any) => {
      this.snackBar.open('Work item updated successfully', 'Close', { duration: 1000 });
      this.getTimelineData();
    }, (error) => {
      console.error('Error updating work item:', error);
    });
  }

    updateEpicProperties(field: string, value: any) {
    const staffId = localStorage.getItem('staffId');
  const staffName = localStorage.getItem('staffName');
    const id = this.wholeData.id;
    let payload: any = {};
    if ((field === 'startDate' || field === 'endDate') && (value === null || value === undefined)) {
      if (field === 'startDate') {
        payload.isStartDateRemoved = true;
      } else {
        payload.isEndDateRemoved = true;
      }
      payload.user = {
        id: staffId,
        name: staffName
      };
    } else {
      payload[field] = value;
      payload.user = {
        id: staffId,
        name: staffName
      };
    }
    this.projectService.updateEpicFields(id, payload).subscribe((res: any) => {
      this.snackBar.open('Epic property updated successfully', 'Close', { duration: 1000 });
      this.getTimelineData();
    }, (error) => {
      console.error('Error updating epic', error);
    });
  }


  isDescriptionEditing = false;
  tempDescription = '';
  showFullDescription = false;

  isTitleEditing = false;
  tempTitle = '';
  @ViewChild('titleInput') titleInput!: ElementRef;

  onTitleEdit() {
    this.isTitleEditing = true;
    this.isDescriptionEditing = true;
    this.tempTitle = this.wholeData.title || '';
    this.tempDescription = this.wholeData.description || '';
    setTimeout(() => {
      if (this.titleInput) {
        this.titleInput.nativeElement.focus();
        this.titleInput.nativeElement.select();
      }
    }, 0);
  }

  onTitleSave() {
    if (this.tempTitle !== this.wholeData.title) {
      this.wholeData.title = this.tempTitle;
      this.updateWorkItemField('title', this.tempTitle);
    }
    this.isTitleEditing = false;
  }

  onTitleCancel() {
    this.isTitleEditing = false;
    this.isDescriptionEditing = false;
    this.tempTitle = '';
    this.tempDescription = '';
  }

  onDescriptionEdit() {
    this.showFullDescription = false; 
    this.isDescriptionEditing = true;
    this.isTitleEditing = true; 
    this.tempTitle = this.wholeData.title || '';
    this.tempDescription = this.wholeData.description || '';
  }

  onDescriptionSave() {
    if (this.tempDescription !== this.wholeData.description) {
      this.wholeData.description = this.tempDescription;
      this.updateWorkItemField('description', this.tempDescription);
    }
    this.isDescriptionEditing = false;
  }

  onDescriptionCancel() {
    this.isDescriptionEditing = false;
    this.isTitleEditing = false;
    this.tempTitle = '';
    this.tempDescription = '';
  }

  toggleDescription(event: Event): void {
    event.stopPropagation();
    this.showFullDescription = !this.showFullDescription;
  }

  getTruncatedDescription(description: string): string {
    if (!description) return '';
    const lines = description.split('\n');
    if (lines.length <= 8) return description;
    return lines.slice(0, 8).join('\n');
  }

  removeAssignee(assignee: any, event: Event) {
    event.stopPropagation();

    if (Array.isArray(this.wholeData.assignee)) {
      this.wholeData.assignee = this.wholeData.assignee.filter((a: any) => a.id !== assignee.id);

      if (this.fromScreen === 'EPIC') {
        this.updateEpicProperties('assignee', this.wholeData.assignee);
      } else {
        this.updateFunction('assignee', this.wholeData.assignee);
      }
    }
  }

  removeLabel(label: any, event: Event) {
    event.stopPropagation();
    this.wholeData.label = this.wholeData.label.filter((l: any) => l.id !== label.id);
   
    if (this.fromScreen === 'EPIC') {
        this.updateEpicProperties('label', this.wholeData.label);
      } else {
        this.updateFunction('label', this.wholeData.label);
      }
  }
  removeDate(dateField: string, event: Event) {
    event.stopPropagation();

    if (dateField === 'startDate') {
      this.wholeData.startDate = null;

          if (this.fromScreen === 'EPIC') {
        this.updateEpicProperties('startDate', null);
      } else {
        this.updateFunction('startDate', null);
      }
    } else if (dateField === 'endDate') {
      this.wholeData.endDate = null;
          if (this.fromScreen === 'EPIC') {
        this.updateEpicProperties('endDate', null);
      } else {
        this.updateFunction('endDate', null);
      }
    }
  }
  moduleList: any;
  getallModules(){
    let payload = {
      projectId: this.projectData.projectId,
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

  subStateList:any[] = [];
  stateList:any;
  getAllSubStatesList(){
    let projectId = this.projectData.projectId;
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
        this.computeEpicProgress();
        
      },
      error: (error) => {
        console.error('Error fetching sub-states:', error);
      }
    });
  }

  cycleList: any;
  getAllCycles() {
    let businessId = localStorage.getItem('businessId');
    let projectId = this.projectData.projectId;
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
  membersList: any[] = [];
  getProjectMembers() {
    let projectId = this.projectData.projectId;
    this.projectService.getAllMembers(projectId).subscribe(
      (res: any) => {
        this.membersList = res.data || [];        
      },
      (error: any) => {
        console.error('Error fetching members:', error);
        this.membersList = [];
      }
    );
  }

  labelsList: any= [];
  getAllLabels() {
  let projectId = this.projectData.projectId;
  this.projectService.getAllLabels(projectId).subscribe(
      (res: any) => {
        this.labelsList = res.data || [];
        
      },
      (error: any) => {
        console.error('Error fetching labels:', error);
      }
    );
  }
  updateEpicField(field: string, value: any) {
    const updateData = {
      id: this.wholeData.id,
      business: {
        id: localStorage.getItem('businessId'),
        name: localStorage.getItem('businessName')
      },
      project: {
        id: this.data?.item?.project?.id,
        name: this.data?.item?.project?.name
      },
      bugNo: this.wholeData.bugNo,
      title: this.wholeData.title,
      description: this.wholeData.description,
      priority: this.wholeData.priority,
      status: this.wholeData.status,
      assignee: this.wholeData.assignee,
      label: this.wholeData.label,
      startDate: this.wholeData.startDate,
      endDate: this.wholeData.endDate,
      // modules: this.wholeData.modules,
      // cycle: this.wholeData.cycle,
      parent: this.wholeData.parent,
      state: this.wholeData.state,
      createdBy: { id: this.wholeData.createdBy.id, name: this.wholeData.createdBy.name },
      updatedBy: this.updatedByList,
      customProperties: this.wholeData.customProperties.map(prop => ({
        id: prop.id,
        projectId: prop.projectId,
        title: prop.title,
        description: prop.description,
        propertyType: {
          value: prop.propertyType?.value,
          attributeType: prop.propertyType?.attributeType,
          attributeValue: prop.propertyType?.attributeValue, // updated value from form
          attributeOptions: prop.propertyType?.attributeOptions || []
        },
        active: prop.active,
        mandatory: prop.mandatory
      })),

      [field]: value
    };


    this.projectService.createEpic(updateData).subscribe((res: any) => {

      this.snackBar.open(`${field} updated successfully`, 'Close', { duration: 1000 });
      this.getTimelineData();
      this.getEpicDetail();
    });
  }


  selectedSubWorkItem:any;
  // selectedWorkItem:any;
  selectedExistingWorkItem:any;

  addSubWorkItem(event: MouseEvent,) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '10%',
    height: '12%',
    position: { top: position.top, right: position.right },
    data: { status: 'SUB_WORK',id: this.wholeData.id }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      this.selectedSubWorkItem = result;
      
      if(this.selectedSubWorkItem === 'Create new'){
        this.createWorkItem();
      }else{
        const type = 'SUB_WORK';
        this.addExistingWorkItem(event,position,type);
      }
    }
  });
}

selectedrelarionType:any;
  addRelationDialog(event: MouseEvent,selectedIssue:any) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '10%',
    height: '22%',
    position: { top: position.top, right: position.right },
    data: { status: 'ADD_RELATION' }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      this.selectedrelarionType = result;
      
     this.addRelationDialog1(event,selectedIssue);
    }
  });
}

addExistingWorkItem(event: MouseEvent,position:any,type:any){
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '45%',
    height: 'fit-content',
    maxHeight: '47vh',
    position: { top: '150px', right: '400px' },
    data: { status: 'WORK_ITEM_LIST', type: type, projectId: this.projectData.projectId , parentId: this.wholeData.id }
  });

  dialogRef.afterClosed().subscribe(result => {
    this.getSubWorkItemList();
    this.getEpicWorkitemList();
  });
}


addLinkDialog(event: MouseEvent){
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '46%',
    height: '38%',
    position: { top: '150px', right: '400px' },
    data: { status: 'ADD_LINK' }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      this.selectedSubWorkItem = result;


    }
  });
}

addRelationDialog1(event: MouseEvent,data:any){
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '45%',
    height: '60%',
    position: { top: '150px', right: '400px' },
    data: { status: 'WORK_ITEM_LIST_2' }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      this.selectedSubWorkItem = result;


    }
  });
}

createWorkItem(): void {
    const dialogConfig = {
      width: '55%',
      height: 'fit-content',
      maxWidth: '100vw',
      position: { top: '10vh' },
      data: { item: this.data.item, projectData: this.data.projectData, status: 'PARENT' }
    };

    const dialog = this.matDialog.open(CreateWorkitemComponent, dialogConfig);
    dialog.afterClosed().subscribe(result => {
      this.getSubWorkItemList();
      this.getEpicWorkitemList();
    });

  }

//   file: any;
//    imgLoader : boolean = false;
//   imgUrl: any;
//  async updatePostImage(ev: Event) {
//   const input = ev.target as HTMLInputElement;
//   if (input.files && input.files.length > 0) {
//     const file = input.files[0];
//     this.file = file;
//     this.imgLoader = true;

//     try {
//     this.imgUrl = await this.imageUploadService.uploadSEOimages(file,'Blogs')
//     this.imgUrl = this.imgUrl.Location;
//       this.imagePreview = this.imgUrl;
//     } catch (error) {
//       console.error('Image upload failed:', error);
//     }

//     this.imgLoader = false;
//   }
// }

getCompletedCount(): number {
    return this.subWorkItemList.filter(item => item.stateMaster?.name === 'Completed').length;
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
  workItemsList = [1,2,3,4,5];

detailWorkitem(item: any) {
  console.info('detailWorkItem>> ',item);
  ;
    const dialogRef = this.matDialog.open(DetailWorkitemComponent, {
        width: '45%',
        height: '100%',
        panelClass: 'custom-dialog',
        position: { top: '0', right: '0' },
        data: { item, projectData: this.projectData, status: 'SUBWORKITEM_DETAIL', bugNo: this.wholeData.bugNo , title: this.wholeData.title}
    });

  dialogRef.afterClosed().subscribe(result => {
    this.getSubWorkItemList();
    this.getWorkitemDetail();

  });
}
detailEpic(item: any) {
  console.info('detailWorkItem>> ',item);
  ;
    const dialogRef = this.matDialog.open(DetailWorkitemComponent, {
        width: '45%',
        height: '100%',
        panelClass: 'custom-dialog',
        position: { top: '0', right: '0' },
        data: { item, projectData: this.projectData, status: 'SUBWORKITEM_DETAIL', bugNo: this.wholeData.bugNo , title: this.wholeData.title}
    });

  dialogRef.afterClosed().subscribe(result => {
    this.getEpicWorkitemList();
    this.getEpicDetail();

  });
}

getSubWorkItemList() {
    const parentId = this.wholeData.id;
    this.projectService.getSubWorkItemByParentId(parentId).subscribe({
        next: (response: any) => {
            this.subWorkItemList = response?.data;

        },
        error: (error) => {
            console.error('Error fetching sub work items:', error);
        }
    });
}

  getInitial(name: string): string {
    return name?.charAt(0).toUpperCase() || '';
  }

  activeDropdownIndex: number | null = null;

  toggleMoreOptions(event: MouseEvent, index: number): void {
    event.stopPropagation();
    this.activeDropdownIndex = this.activeDropdownIndex === index ? null : index;
  }

  removeSubWorkItem(item: any) {
    const parentId = this.wholeData.id;
    const childId = item.id;
    this.projectService.removeSubWorkitem(parentId, childId).subscribe({
      next: () => {
        this.getSubWorkItemList();
      },
      error: (error) => {
     
      }
    });
  }

  deleteWorkitem(element: any) {
      let dialog = this.masterService.openDeleteDialog(
        CustomDeleteComponent,
        'auto',
        'auto',
        {
          heading: "Delete Work Item",
          subText: "Are you sure you want to delete this item?",
          secondaryButton: "Cancel", primaryButton: "Delete"
        },
        '80vw',
        
      );
      dialog.afterClosed().subscribe((data) => {
        if (data.response !== 'cancel') {
          if(this.fromScreen === 'EPIC' ){
             this.projectService.deleteEpic(element.id).subscribe
             (
            {
              next: (value: any) => {
                this.snackBar.open("Successfully Deleted", 'Close',{
                  duration: 1000
                })
                this.dialogRef.close();   
              },
              error: (err: any) => {
                this.snackBar.open(
                  `${err.error.message}`,
                  'Close',
                  {
                    duration: 1000
                  }
                )
              },
  
            }
          );
          }else{
            this.projectService.deleteWorkItem(element.id).subscribe(
            {
              next: (value: any) => {
                this.snackBar.open("Successfully Deleted", 'Close',{
                  duration: 1000
                })
                this.dialogRef.close();   
              },
              error: (err: any) => {
                this.snackBar.open(
                  `${err.error.message}`,
                  'Close',
                  {
                    duration: 1000
                  }
                )
              },
  
            }
          )
          }
        }
      });
    }

  mentionedUsers: any[] = [];

  // Add this method to extract mentioned users from editor content
extractMentionedUsers() {
  this.mentionedUsers = [];
  
  if (!this.editorContent) {
    return;
  }
  
  // If editorContent is a string (HTML format)
  if (typeof this.editorContent === 'string') {
    const parser = new DOMParser();
    const doc = parser.parseFromString(this.editorContent, 'text/html');
    const mentions = doc.querySelectorAll('.mention, [data-mention]');
    
    mentions.forEach(mention => {
      const id = mention.getAttribute('data-id') || mention.getAttribute('data-mention-id');
      const name = mention.getAttribute('data-value') || mention.getAttribute('data-mention-value') || mention.textContent;
      // const email = mention.getAttribute('data-email') || mention.getAttribute('data-mention-email') || '';
      
      if (id && name) {
        this.mentionedUsers.push({
          id: id,
          name: name.replace('@', ''), // Remove @ symbol from name
          // email: email
        });
      }
    });
    
    // Fallback: look for @mentions in text if no proper mention elements found
    if (this.mentionedUsers.length === 0) {
      const mentionRegex = /@(\w+)/g;
      let match;
      while ((match = mentionRegex.exec(this.editorContent)) !== null) {
        const mentionName = match[1];
        // Try to find the user in membersList
        const member = this.membersList?.find((m: any) => 
          (m.name && m.name.toLowerCase().includes(mentionName.toLowerCase())) ||
          (m.staffName && m.staffName.toLowerCase().includes(mentionName.toLowerCase()))
        );
        
        if (member) {
          this.mentionedUsers.push({
            id: member.memberId,
            name:member.name,
            // email: member.email || member.staffEmail || ''
          });
        }
      }
    }
  } else {
    // If editorContent is in Delta format (Quill's native format)
    try {
      const delta = JSON.parse(this.editorContent);
      if (delta.ops) {
        delta.ops.forEach((op: any) => {
          if (op.insert && op.insert.mention) {
            this.mentionedUsers.push({
              id: op.insert.mention.id,
              name: op.insert.mention.value,
              // email: op.insert.mention.email || ''
            });
          }
        });
      }
    } catch (error) {
      console.error('Error parsing editor content:', error);
    }
  }
  
  console.log('Extracted mentioned users:', this.mentionedUsers);
}

  addcommentWorkItem() {
  if (this.editorContent && this.editorContent.trim()) {
    // Clean the comment text - preserve basic formatting but remove unwanted HTML
    let cleanCommentText = this.cleanHtmlToPlainText(this.editorContent);
    
    const payload = {
      workItemId: this.wholeData.id,
      commentText: cleanCommentText,
      user: {
        id: localStorage.getItem(StorageKeys.STAFF_ID),
        name: localStorage.getItem(StorageKeys.STAFF_NAME)
      },
      mentions: this.mentionedUsers
    };
    
    console.log('Sending comment payload:', payload);
    
    this.projectService.addCommentWorkItem(payload).subscribe({
      next: (response: any) => {
        console.log('Comment added successfully:', response);
        // Clear editor content safely
        this.clearEditorContent();
        this.mentionedUsers = [];
        this.getSubWorkItemList();
        this.getTimelineData(); 
        this.isSubmittingComment = false;
      },
      error: (error) => {
        console.error('Error adding comment:', error);
        this.isSubmittingComment = false;
      }
    });
  } else {
    this.isSubmittingComment = false;
  }
}

/**
 * Clean HTML content while preserving basic formatting
 */
cleanHtmlToPlainText(htmlContent: string): string {
  if (!htmlContent) return '';
  
  try {
    // For basic formatting, we'll preserve the HTML but clean unwanted attributes
    return this.cleanAndPreserveBasicFormatting(htmlContent);
  } catch (error) {
    console.error('Error cleaning HTML content:', error);
    // Fallback: return original content if cleaning fails
    return htmlContent;
  }
}

/**
 * Clean HTML while preserving basic formatting like bold, italic, lists, etc.
 */
cleanAndPreserveBasicFormatting(htmlContent: string): string {
  if (!htmlContent) return '';
  
  try {
    // Create a temporary div to parse HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = htmlContent;
    
    // Remove unwanted style attributes but keep basic formatting tags
    const elementsWithStyle = tempDiv.querySelectorAll('[style]');
    elementsWithStyle.forEach(element => {
      // Only remove style attributes that contain color, background, font-family, etc.
      const style = element.getAttribute('style') || '';
      if (style.includes('color:') || style.includes('background') || style.includes('font-family')) {
        element.removeAttribute('style');
      }
    });
    
    // Remove unwanted span tags that only contain styling (no semantic meaning)
    const spans = tempDiv.querySelectorAll('span');
    spans.forEach(span => {
      const hasStyle = span.hasAttribute('style');
      const hasClass = span.hasAttribute('class');
      const hasOtherAttributes = Array.from(span.attributes).some(attr => 
        attr.name !== 'style' && attr.name !== 'class'
      );
      
      // Remove Quill UI spans specifically
      if (span.classList.contains('ql-ui')) {
        span.remove();
        return;
      }
      
      // If span only has style/class attributes and no semantic meaning, unwrap it
      if ((hasStyle || hasClass) && !hasOtherAttributes) {
        const parent = span.parentNode;
        if (parent) {
          while (span.firstChild) {
            parent.insertBefore(span.firstChild, span);
          }
          parent.removeChild(span);
        }
      }
    });
    
    // Fix Quill's list structure issues
    this.fixQuillListStructure(tempDiv);
    
    // Clean up excessive nested divs but preserve content structure
    const unnecessaryDivs = tempDiv.querySelectorAll('div:empty');
    unnecessaryDivs.forEach(div => div.remove());
    
    // Convert some div structures to proper paragraph breaks
    const divs = tempDiv.querySelectorAll('div');
    divs.forEach((div, index) => {
      // If div has no special formatting, convert to paragraph-like structure
      if (!div.hasAttribute('class') && !div.hasAttribute('style')) {
        if (index > 0 && div.previousSibling) {
          div.before('\n');
        }
      }
    });
    
    // Clean up extra spacing between paragraphs and lists
    let cleaned = tempDiv.innerHTML;
    
    // Remove multiple consecutive <br> tags
    cleaned = cleaned.replace(/<br\s*\/?>\s*<br\s*\/?>/g, '<br>');
    
    // Remove <br> tags that are immediately before lists
    cleaned = cleaned.replace(/<br\s*\/?>\s*(<[ou]l>)/gi, '$1');
    
    // Remove <br> tags that are immediately after lists
    cleaned = cleaned.replace(/(<\/[ou]l>)\s*<br\s*\/?>/gi, '$1');
    
    // Remove extra paragraph spacing around lists
    cleaned = cleaned.replace(/<p><\/p>\s*(<[ou]l>)/gi, '$1');
    cleaned = cleaned.replace(/(<\/[ou]l>)\s*<p><\/p>/gi, '$1');
    
    return cleaned;
  } catch (error) {
    console.error('Error preserving basic formatting:', error);
    return htmlContent;
  }
}

/**
 * Clean pasted content to remove unwanted styling
 */
cleanPastedContent(htmlContent: string): string {
  if (!htmlContent) return '';
  
  try {
    // Create a temporary div to parse HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = htmlContent;
    
    // Remove all style attributes
    const elementsWithStyle = tempDiv.querySelectorAll('[style]');
    elementsWithStyle.forEach(element => {
      element.removeAttribute('style');
    });
    
    // Remove specific unwanted tags but keep their content
    // Handle regular tags
    const unwantedTags = ['span', 'font'];
    unwantedTags.forEach(tagName => {
      const elements = tempDiv.querySelectorAll(tagName);
      elements.forEach(element => {
        const parent = element.parentNode;
        if (parent) {
          while (element.firstChild) {
            parent.insertBefore(element.firstChild, element);
          }
          parent.removeChild(element);
        }
      });
    });
    
    // Handle XML namespaced elements (like o:p from Microsoft Office)
    // Use getElementsByTagName instead of querySelectorAll for XML elements
    let officeParagraphs = tempDiv.getElementsByTagName('o:p');
    // Convert to array to avoid live collection issues
    const officeParagraphsArray = Array.from(officeParagraphs);
    officeParagraphsArray.forEach(element => {
      const parent = element.parentNode;
      if (parent) {
        while (element.firstChild) {
          parent.insertBefore(element.firstChild, element);
        }
        parent.removeChild(element);
      }
    });
    
    // Remove other common Office XML elements
    const xmlElements = ['w:p', 'w:r', 'w:t', 'w:br', 'v:*', 'o:*'];
    xmlElements.forEach(tagPattern => {
      if (tagPattern.includes('*')) {
        // Handle wildcard patterns
        const prefix = tagPattern.replace('*', '');
        const allElements = tempDiv.getElementsByTagName('*');
        const elementsArray = Array.from(allElements);
        elementsArray.forEach(element => {
          if (element.tagName.toLowerCase().startsWith(prefix)) {
            const parent = element.parentNode;
            if (parent) {
              while (element.firstChild) {
                parent.insertBefore(element.firstChild, element);
              }
              parent.removeChild(element);
            }
          }
        });
      } else {
        // Handle specific tags
        const elements = Array.from(tempDiv.getElementsByTagName(tagPattern));
        elements.forEach(element => {
          const parent = element.parentNode;
          if (parent) {
            while (element.firstChild) {
              parent.insertBefore(element.firstChild, element);
            }
            parent.removeChild(element);
          }
        });
      }
    });
    
    // Remove empty paragraphs and divs
    const emptyElements = tempDiv.querySelectorAll('p:empty, div:empty');
    emptyElements.forEach(element => {
      element.remove();
    });
    
    return tempDiv.innerHTML;
  } catch (error) {
    console.error('Error cleaning pasted content:', error);
    return htmlContent;
  }
}

/**
 * Fix Quill's list structure issues
 */
fixQuillListStructure(container: HTMLElement): void {
  // Find all list items with data-list attributes
  const listItems = container.querySelectorAll('li[data-list]');
  
  if (listItems.length === 0) return;
  
  // Group consecutive list items by their data-list type
  let currentGroup: HTMLLIElement[] = [];
  let currentType: string | null = null;
  
  listItems.forEach((li, index) => {
    const listType = li.getAttribute('data-list');
    
    if (listType !== currentType) {
      // Process the previous group
      if (currentGroup.length > 0) {
        this.createProperListFromGroup(currentGroup, currentType!);
      }
      
      // Start new group
      currentGroup = [li as HTMLLIElement];
      currentType = listType;
    } else {
      currentGroup.push(li as HTMLLIElement);
    }
    
    // Process the last group
    if (index === listItems.length - 1 && currentGroup.length > 0) {
      this.createProperListFromGroup(currentGroup, currentType!);
    }
  });
}

/**
 * Create proper list structure from grouped list items
 */
createProperListFromGroup(listItems: HTMLLIElement[], listType: string): void {
  if (listItems.length === 0) return;
  
  const firstItem = listItems[0];
  const parent = firstItem.parentNode;
  
  if (!parent) return;
  
  // Create the appropriate list container
  const listContainer = document.createElement(listType === 'bullet' ? 'ul' : 'ol');
  
  // Clean up list items and move them to the new container
  listItems.forEach(li => {
    // Remove the data-list attribute since we're using proper HTML structure
    li.removeAttribute('data-list');
    
    // Remove any ql-ui spans
    const qlUiSpans = li.querySelectorAll('span.ql-ui');
    qlUiSpans.forEach(span => span.remove());
    
    // Remove empty content
    if (li.innerHTML.trim() === '<br>' || li.innerHTML.trim() === '') {
      return; // Skip empty items
    }
    
    // Clone the item to avoid moving issues
    const cleanItem = li.cloneNode(true) as HTMLLIElement;
    listContainer.appendChild(cleanItem);
  });
  
  // Only proceed if we have items to add
  if (listContainer.children.length > 0) {
    // Replace the first item with our new list
    parent.insertBefore(listContainer, firstItem);
    
    // Remove the original items
    listItems.forEach(li => {
      if (li.parentNode) {
        li.parentNode.removeChild(li);
      }
    });
  }
}

timelineData:any=[];
showAllTimeline: boolean = false;
timelineDisplayLimit: number = 5;
  isFilterMenuOpen: boolean = false;
  filterOptions: { updates: boolean; comments: boolean; worklogs: boolean } = {
    updates: true,
    comments: true,
    worklogs: true
  };

  @ViewChild('menuWrapper', { static: false }) menuWrapper!: ElementRef;

get displayedTimelineData() {
  const filtered = this.getFilteredTimeline();
  if (this.showAllTimeline || filtered.length <= this.timelineDisplayLimit) {
    return filtered;
  }
  return filtered.slice(0, this.timelineDisplayLimit);
}

get hasMoreTimelineItems() {
  return this.getFilteredTimeline().length > this.timelineDisplayLimit;
}

toggleShowAllTimeline() {
  this.showAllTimeline = !this.showAllTimeline;
  // Resize textareas after timeline visibility changes
  setTimeout(() => {
    this.resizeAllCommentTextareas();
  }, 50);
}

toggleFilterMenu(event: MouseEvent) {
  event.stopPropagation();
  this.isFilterMenuOpen = !this.isFilterMenuOpen;
}

@HostListener('document:click', ['$event'])
onGlobalClick(event: MouseEvent) {
  const target = event.target as HTMLElement;
  if (this.isFilterMenuOpen && this.menuWrapper && !this.menuWrapper.nativeElement.contains(target)) {
    this.isFilterMenuOpen = false;
  }
  const clickedOnDropdown = target.closest('.status-pill') || target.closest('.status-dropdown') || target.closest('.status-dropdown1');
  if (!clickedOnDropdown) {
    this.isDropdownOpen = false;
    
    if (this.EpicStatusUpdateList) {
      this.EpicStatusUpdateList.forEach(item => {
        if (item.isDropdownOpen) {
          item.isDropdownOpen = false;
        }
      });
    }
  }
}

toggleFilter(type: 'updates' | 'comments' | 'worklogs') {
  this.filterOptions[type] = !this.filterOptions[type];
}

private getFilteredTimeline() {
  if (!this.timelineData?.length) return [];
  return this.timelineData.filter((item: any) => {
    const t = (item?.type || '').toUpperCase();
    const isWorklog = t === 'TIME_LOGGED' || t === 'WORKLOG' || t === 'WORK_LOGGED';
    if (isWorklog && !this.feature?.timeTracking) return false;
    if (t === 'COMMENTED') return this.filterOptions.comments;
    if (isWorklog) return this.filterOptions.worklogs;
    return this.filterOptions.updates;
  });
}

get filteredTimelineCount() {
  return this.getFilteredTimeline().length;
}

latestChangeData:any;
getTimelineData(){
  this.projectService.getTimelineData(this.wholeData.id).subscribe({
    next: (response: any) => {
      console.log('Timeline data retrieved successfully:', response);
      console.log('Response type:', typeof response);
      console.log('Is array:', Array.isArray(response));
      
      let timelineArray: any[] = [];
      
      if (Array.isArray(response)) {
        timelineArray = response;
      } else if (response && Array.isArray(response.data)) {
        timelineArray = response.data;
      } else if (response && typeof response === 'object') {
        // If response is an object but not an array, try to extract array from common properties
        timelineArray = response.timeline || response.activities || response.items || [];
      } else {
        console.warn('Unexpected response format, defaulting to empty array');
        timelineArray = [];
      }
      
      this.timelineData = timelineArray.sort((a: any, b: any) => 
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      this.latestChangeData = this.timelineData[0] || {};
      
      console.log('Processed timeline data:', this.timelineData);
      
      setTimeout(() => {
        this.resizeAllCommentTextareas();
      }, 100);
    },
    error: (error) => {
      console.error('Error retrieving timeline data:', error);
      this.timelineData = []; 
    }
  });
}

getIconForActivityType(type: string): string {
  switch (type) {
    case 'CREATED':
      return 'fas fa-layer-group';
    case 'UPDATED':
      return 'fas fa-edit';
    case 'PRIORITY_CHANGED':
      return 'fas fa-chart-line';
    case 'LABEL_ADDED':
      return 'fas fa-tag';
    case 'DATE_CHANGED':
      return 'fas fa-calendar-alt';
    case 'ASSIGNEE_ADDED':
      return 'fas fa-user-plus';
    case 'STATE_CHANGED':
      return 'fas fa-exchange-alt';
    default:
      return 'fas fa-info-circle';
  }
}

getRelativeTime(timestamp: string): string {
  const now = new Date();
  // const activityTime = new Date(timestamp);
  const activityTime = new Date(timestamp);
  const diffInMs = now.getTime() - activityTime.getTime();
  
  const diffInMinutes = Math.floor(diffInMs / (1000 * 60));
  const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60));
  const diffInDays = Math.floor(diffInMs / (1000 * 60 * 60 * 24));
  const diffInMonths = Math.floor(diffInDays / 30);
  const diffInYears = Math.floor(diffInDays / 365);

  if (diffInMinutes < 1) {
    return 'just now';
  } else if (diffInMinutes < 60) {
    return `${diffInMinutes} minute${diffInMinutes === 1 ? '' : 's'} ago`;
  } else if (diffInHours < 24) {
    return `${diffInHours} hour${diffInHours === 1 ? '' : 's'} ago`;
  } else if (diffInDays < 30) {
    return `${diffInDays} day${diffInDays === 1 ? '' : 's'} ago`;
  } else if (diffInMonths < 12) {
    return `${diffInMonths} month${diffInMonths === 1 ? '' : 's'} ago`;
  } else {
    return `${diffInYears} year${diffInYears === 1 ? '' : 's'} ago`;
  }
}

/**
 * Safely clear the Quill editor content to avoid clipboard module errors
 */
clearEditorContent() {
  try {
    // Use setTimeout to ensure this happens after current execution cycle
    setTimeout(() => {
      if (this.currentEditor) {
        // Use Quill's native method to clear content
        this.currentEditor.setText('');
        this.currentEditor.setSelection(0, 0);
      }
      // Also clear the bound variable using setter
      this.editorContent = '';
    }, 10);
  } catch (error) {
    console.warn('Error clearing editor content:', error);
    // Fallback: just clear the variable with a delay
    setTimeout(() => {
      this.editorContent = '';
    }, 10);
  }
}

addAttachment(){
  const staffId = localStorage.getItem('staffId');
  const staffName = window.localStorage.getItem('staffName');
  const workitemId = this.wholeData.id;
  let payload = {
    url: this.attachments[0].url.url,
    name: this.attachments[0].name,
    staff: {
      id: staffId,
      name: staffName
    }
  }
  if(this.fromScreen === 'EPIC'){
     this.projectService.addEpicAttachment(workitemId, payload).subscribe({
    next: () => {
      this.snackBar.open('Attachment added successfully!', 'Close', { duration: 1000 })
      ;
      
    },
    error: (error) => {
      console.error('Error adding attachment:', error);
      this.snackBar.open('Failed to add attachment. Please try again.', 'Close', { duration: 1000 });
    }
  });
  }else{
      this.projectService.addAttachment(workitemId, payload).subscribe({
    next: () => {
      this.snackBar.open('Attachment added successfully!', 'Close', { duration: 1000 })
      ;
      
    },
    error: (error) => {
      console.error('Error adding attachment:', error);
      this.snackBar.open('Failed to add attachment. Please try again.', 'Close', { duration: 1000 });
    }
  });
  }

}
attachments: any[] = [];
pageLoader: boolean = false;

async onFileSelected(event: any) {
  const file = event.target.files[0];
  if (!file) return;

  try {
    this.pageLoader = true;
    this.snackBar.open('Uploading attachment...', 'Close', { duration: 3000 });
    
    const uploadedUrl: any = await this._imageUpload.uploadComponentsImages(file, 'WorkItemAttachments');
    
    if (uploadedUrl && uploadedUrl.Location) {
      const attachment = {
        name: file.name,
        url: { url: uploadedUrl.Location },
        type: file.type,
        size: file.size,
        date: new Date(),
        uploadedBy: localStorage.getItem(StorageKeys.STAFF_NAME)
      };
      
      this.attachments.push(attachment);
      this.attachmentsList.push(attachment);

      await this.addAttachment();

      this.snackBar.open('Attachment uploaded successfully!', 'Close', { duration: 3000 });
    } else {
      throw new Error('Upload failed - no URL returned');
    }
  } catch (error) {
    console.error('Error uploading attachment:', error);
    this.snackBar.open('Failed to upload attachment. Please try again.', 'Close', { duration: 3000 });
  } finally {
    this.pageLoader = false;
    event.target.value = '';
  }
}

// async updateWorkItemAttachments() {
//   try {
//     const updateData = {
//       url: this.attachmentsList
//     };
    
//     await 
//     this.projectService.updateWorkItem(updateData);

//     // this.wholeData.url = this.attachmentsList;
    
//   } catch (error) {
//     console.error('Error updating work item attachments:', error);
//     throw error;
//   }
// }

isImageFile(fileName: string): boolean {
  const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'];
  const extension = fileName.split('.').pop()?.toLowerCase();
  return imageExtensions.includes(extension || '');
}

isPdfFile(fileName: string): boolean {
  return fileName.toLowerCase().endsWith('.pdf');
}

isVideoFile(fileName: string): boolean {
  const videoExtensions = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', '3gp', 'ogv'];
  const extension = fileName.split('.').pop()?.toLowerCase();
  return videoExtensions.includes(extension || '');
}

isDocFile(fileName: string): boolean {
  const docExtensions = ['doc', 'docx', 'txt', 'rtf'];
  const extension = fileName.split('.').pop()?.toLowerCase();
  return docExtensions.includes(extension || '');
}

isCsvFile(fileName: string): boolean {
  return fileName.toLowerCase().endsWith('.csv');
}

formatFileSize(bytes: number): string {
  if (!bytes) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// downloadAttachment(attachment: any) {
//   window.open(this.getAttachmentUrl(attachment), '_blank');
// }

// clipBoardCopy(attachment: any) {
//   let val = this.getAttachmentUrl(attachment);
//   let selBox = document.createElement('textarea');
//   selBox.style.position = 'fixed';
//   selBox.style.left = '0';
//   selBox.style.top = '0';
//   selBox.style.opacity = '0';
//   selBox.value = val;
//   document.body.appendChild(selBox);
//   selBox.focus();
//   selBox.select();
//   document.execCommand('copy');
//   document.body.removeChild(selBox);
//   this.snackBar.open("Link copied successfully", "Close", { duration: 2000 });
// }

// browseFiles() {
//   document.getElementById('browse_attachment_file')?.click();
// }

// async removeAttachment(index: number) {
//   try {
//     const attachment = this.attachmentsList[index];
    
//     // Remove from local list
//     this.attachmentsList.splice(index, 1);
    
//     // Update work item
//     await this.updateWorkItemAttachments();
    
//     // Optional: Delete file from Azure (uncomment if you want to delete files)
//     // await this.imageUploadService.deleteFileInAzure(attachment.url, 'WorkItemAttachments');
    
//     this.snackBar.open('Attachment removed successfully!', 'Close', { duration: 3000 });
//   } catch (error) {
//     console.error('Error removing attachment:', error);
//     this.snackBar.open('Failed to remove attachment. Please try again.', 'Close', { duration: 3000 });
//   }
// }

removeAttachment(res:any){
  if (res.id){
  const attachmentId = res?.id;
  const workitemId = this.wholeData?.id;
  if(this.fromScreen === 'EPIC'){
  this.projectService.removeEpicAttachment(workitemId ,attachmentId).subscribe({
    next: () => {
      this.attachmentsList = this.attachmentsList.filter((attachment: any) => attachment.id !== attachmentId);
      this.snackBar.open('Attachment removed successfully!', 'Close', { duration: 1000 });
    },
    error: (error) => {
      console.error('Error removing attachment:', error);
      this.snackBar.open('Failed to remove attachment. Please try again.', 'Close', { duration: 1000 });
    }
  });
  }else{
      this.projectService.removeAttachment(workitemId ,attachmentId).subscribe({
    next: () => {
      this.attachmentsList = this.attachmentsList.filter((attachment: any) => attachment.id !== attachmentId);
      this.snackBar.open('Attachment removed successfully!', 'Close', { duration: 1000 });
    },
    error: (error) => {
      console.error('Error removing attachment:', error);
      this.snackBar.open('Failed to remove attachment. Please try again.', 'Close', { duration: 1000 });
    }
  });
  }

} else {
  const attachmentName = res?.name;
  this.attachments = this.attachments.filter((attachment: any) => attachment.name !== attachmentName);
  this.attachmentsList = this.attachmentsList.filter((attachment: any) => attachment.name !== attachmentName);
  this.snackBar.open('Attachment removed successfully!', 'Close', { duration: 1000 });
}
}

previewAttachment(attachment: any) {
  this.selectedAttachment = attachment;
  this.showImagePreview = true;
  
  document.body.style.overflow = 'hidden';
}

handleAttachmentClick(attachment: any) {
  if (this.isPdfFile(attachment.name) || this.isDocFile(attachment.name) || this.isCsvFile(attachment.name)) {
    this.openFileInNewTab(attachment);
  } else {
    this.previewAttachment(attachment);
  }
}

closeImagePreview() {
  this.showImagePreview = false;
  this.selectedAttachment = null;
  
  document.body.style.overflow = 'auto';
}
getAttachmentUrl(attachment: any): string {
  if (!attachment) return '';
  if (attachment.url && typeof attachment.url === 'object' && attachment.url.url) {
    return attachment.url.url;
  }
    if (attachment.url && typeof attachment.url === 'string') {
    return attachment.url;
  }
  
  return '';
}

getSafeUrl(url: string): SafeResourceUrl {
  return this.sanitizer.bypassSecurityTrustResourceUrl(url);
}

downloadAttachment(attachment: any) {
  const url = this.getAttachmentUrl(attachment);
  if (url) {
    const link = document.createElement('a');
    link.href = url;
    link.download = attachment.name || 'download';
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
}

openFileInNewTab(attachment: any) {
  const url = this.getAttachmentUrl(attachment);
  if (url) {
    window.open(url, '_blank', 'noopener,noreferrer');
  }
}

logWork(){
  let payload = {
    user: {
      id: localStorage.getItem('staffId'),
      name: localStorage.getItem('staffName')
    },
    hours: this.logHours,
    minutes: this.logMinutes,
    description: this.logDescription
  }
  this.projectService.logWork(this.wholeData.id,payload).subscribe({
    next: (response: any) => {
      this.snackBar.open('Work logged successfully!', 'Close', { duration: 1000 });
      this.getTimelineData();
      this.getWorkitemDetail();
      this.logHours = 0;
      this.logMinutes = 0;
      this.logDescription = '';
    },
    error: (error) => {
      console.error('Error logging work:', error);
      this.snackBar.open('Failed to log work. Please try again.', 'Close', { duration: 1000 });
    }
  });
}

totalTime: string = '';
timeconversion(){
  const totalMinutes = this.wholeData?.workLogs?.reduce((acc, log) => {
  return acc + (log.hours * 60 + log.minutes);
}, 0) ?? 0;

const totalHours = Math.floor(totalMinutes / 60);
const remainingMinutes = totalMinutes % 60;
this.totalTime = `${totalHours}h ${remainingMinutes}m`;

}

getWorkitemDetail(){
  let payload ={
    taskId: this.workitem.id
  }
  this.projectService.getAllWorkItems(payload).subscribe({
    next: (response: any) => {
      console.log('releasedate responose::',response);
      this.wholeData = response?.data[0];
      this.timeconversion();
    if (!this.editorContent) {
      this.editorContent = '';
    }
    
    if (!this.wholeData?.assignee || !Array.isArray(this.wholeData?.assignee)) {
      this.wholeData.assignee = [];
    }

    if (!this.wholeData?.label || !Array.isArray(this.wholeData?.label)) {
      this.wholeData.label = [];
    }
    
    this.getallModules();
    this.getAllSubStatesList();
    this.getAllCycles();
    this.getProjectMembers();
    this.getAllLabels();
    this.getEstimation();
    this.updatedByList = this.wholeData?.updatedBy || [];
    this.updatedByList.push({
      id: localStorage.getItem(StorageKeys.STAFF_ID),
      name: localStorage.getItem(StorageKeys.STAFF_NAME)
    });
    this.getSubWorkItemList();
    this.getTimelineData();
    this.initializeEditor();
    this.attachmentsList = this.wholeData.attachmentUrl || [];

    },
    error: (error) => {
      console.error('Error fetching work item details:', error);
    }
  });
}
commentList:any;
customProperties:any[] = [];
tempWorkitemList:any;
getEpicDetail(){
  let payload ={

    epicId: this.workitem.id
  }
  this.projectService.getEpicListing(payload).subscribe({
    next: (response: any) => {
      this.wholeData = response?.data[0];
      this.customProperties = this.wholeData?.customProperties || [];
      this.EpicStatusUpdateList = response?.data[0]?.epicUpdates;
      this.commentList = response?.data[0]?.epicComments;
      this.timeconversion();
    if (!this.editorContent) {
      this.editorContent = '';
    }
    
    if (!this.wholeData?.assignee || !Array.isArray(this.wholeData?.assignee)) {
      this.wholeData.assignee = [];
    }

    if (!this.wholeData?.label || !Array.isArray(this.wholeData?.label)) {
      this.wholeData.label = [];
    }
    
    this.getallModules();
    this.getAllSubStatesList();
    this.getAllCycles();
    this.getProjectMembers();
    this.getAllLabels();
    this.getEstimation();
    this.updatedByList = this.wholeData?.updatedBy || [];
    this.updatedByList.push({
      id: localStorage.getItem(StorageKeys.STAFF_ID),
      name: localStorage.getItem(StorageKeys.STAFF_NAME)
    });
      this.getTimelineData();
      this.getEpicWorkitemList();
      // this.createOnTrack(true);
    this.initializeEditor();
    this.attachmentsList = this.wholeData.attachmentUrl || [];

    },
    error: (error) => {
      console.error('Error fetching work item details:', error);
    }
  });
}

isTimelineTop: boolean = true;

swapSections() {
  this.isTimelineTop = !this.isTimelineTop;
}
estimatedList:any[] = [];
estimateSystem: string | null = null;
getEstimation(){
  let projectId = this.projectData?.projectId;
    this.projectService.getEstimation(projectId).subscribe((res:any)=>{
      const est = res?.data?.[0] || null;
      this.estimateSystem = est?.estimateSystem || null;
      this.estimatedList = Array.isArray(est?.custom) ? est.custom : [];
    },error=>{
      console.error('Error fetching estimation points:', error);
    });
  }

formatEstimatedList(list: any): string {
  if (list == null) return 'N/A';

  const formatOne = (item: any): string => {
    const toNum = (v: any) => (v != null && v !== '' ? Number(v) : 0);
    const hr = toNum(item?.hr);
    const min = toNum(item?.min);

    if (hr === 0 && min === 0) return '0 min';
    if (hr > 0 && min === 0) return `${hr} hr`;
    if (hr === 0 && min > 0) return `${min} min`;
    return `${hr} hr ${min} min`;
  };

  if (Array.isArray(list)) {
    if (list.length === 0) return 'N/A';

    if (typeof list[0] === 'object' && (list[0]?.hr !== undefined || list[0]?.min !== undefined)) {
      return list.map((item: any) => formatOne(item)).join(', ');
    }

    return list.filter((val) => val != null && val !== '').join(', ');
  }

  if (typeof list === 'object' && (list?.hr !== undefined || list?.min !== undefined)) {
    return formatOne(list);
  }

  return list?.toString() ?? '';
}

// EPIC 

backlog = { count: 1, percent: 20 };
unstarted = { count: 1, percent: 20 };
started = { count: 1, percent: 20 };
completed = { count: 1, percent: 20 };
cancelled = { count: 1, percent: 20 };
  
  progressItems: any[] = [];

  selectedTab = 0;
 

  EpicStatusUpdateList: any[] = [];


updateText = '';
cancel() {
  this.updateText = '';
}
addUpdate() {
  // Your save logic here
  console.log(this.updateText);
}

isCreating: boolean = false;
  createOnTrack(isInitialLoad = false) {
    if (this.isCreating) return; 
  this.isCreating = true;
    const createData = {
   epicId: this.wholeData.id,
  projectId: this.projectData.projectId,
  status: this.selectedStatus.value,
  description: isInitialLoad ? '' : this.description,
  createdBy: {
    id: localStorage.getItem('staffId'),
    name: localStorage.getItem('staffName')
  },
  title: "",
  reaction: "",
  comment: "",
  type: "STATUS"
    };

  
      this.projectService.addTrack(createData).subscribe({
      next: (res: any) => {
        
        this.getEpicDetail();
        this.description = '';
        if (!isInitialLoad) {
          this.description = '';
          this.snackBar.open('Created successfully', 'Close', { duration: 1000 });
          this.showUpdateForm = false;
        }
        this.isCreating = false;
        console.log('ontrackdata:', res);
      },
      error: (err) => {
        console.error('Error creating status:', err);
        this.isCreating = false;
      }
    });
  
  }
    updateOnTrack(res:any,) {
      console.log("responseeeeeeeeeeee:",res)
  

  
      this.projectService.addTrack(res).subscribe({
      next: (res: any) => {
        this.isEditable

          this.description = '';
          this.snackBar.open('Updated successfully', 'Close', { duration: 1000 });
    

        console.log('ontrackdata:', res);
      },
      error: (err) => {
        console.error('Error creating status:', err);
      }
    });
  
  }

  sendComment() {
    if (this.isSubmittingComment) return;
    if (!this.editorContent || this.editorContent.trim() === '') {
    this.snackBar.open('Please enter a comment before submitting.', 'Close', { duration: 1000 });
    return;
  }

  this.isSubmittingComment = true;
    const createData = {
      epicId: this.wholeData.id,
      projectId: this.projectData.projectId,
      comment: this.editorContent,
      type: "COMMENT",
      createdBy: {
        id: localStorage.getItem('staffId'),
        name: localStorage.getItem('staffName')
      }
    };

    this.projectService.addTrack(createData).subscribe({
      next: (res: any) => {
        this.getEpicDetail();
        this.editorContent = '';
        this.isSubmittingComment = false;
        this.comment = '';
        this.snackBar.open(`Created successfully`, 'Close', { duration: 1000 });
        // if (res?.data) {
        //   this.EpicStatusUpdateList = res.data;
        // }

        console.log('ontrackdata:', res);
      },
      error: (err) => {
        console.error('Error creating status:', err);
        this.isSubmittingComment = false;
      }
    });

  }

  isDropdownOpen = false;
  getStatusDetails(status: string) {
    return this.statusMap[status] || {
      label: 'Unknown',
      icon: 'help_outline',
      color: '#9e9e9e'
    };
  }

  // UI mapping for colors/icons
  statusMap: any = {
    ON_TRACK: { label: 'On Track', icon: 'check_circle', color: 'green' },
    AT_RISK: { label: 'At Risk', icon: 'error_outline', color: '#e68a00' },
    OFF_RISK: { label: 'Off Track', icon: 'error', color: 'red' }
  };

statuses = [
    { label: 'On Track', icon: 'check_circle', color: 'green', value: 'ON_TRACK' },
    { label: 'At Risk', icon: 'error_outline', color: '#e68a00', value: 'AT_RISK' },
    { label: 'Off Track', icon: 'error', color: 'red', value: 'OFF_RISK' }
  ];
  options = [
    "Edit" ,
     "Delete" ,

  ];


  selectedStatus = this.statuses[0]; // Default

toggleDropdown(item?: any) {
  // If we are in "Add Update" mode (no item passed)
  if (!item) {
    this.isDropdownOpen = !this.isDropdownOpen;
    return;
  }

  // If we are editing a specific item
  item.isDropdownOpen = !item.isDropdownOpen;
}

 selectStatus(status: any, item?: any) {
  this.selectedStatus = status;

  // Close the right dropdown
  if (item) {
    item.isDropdownOpen = false;   // for edit mode
  } else {
    this.isDropdownOpen = false;   // for add update mode
  }
}
onEditEpicStatus(item: any) {
  console.log('Edit clicked for:', item);

  // Reset edit mode on all items
  this.EpicStatusUpdateList.forEach(i => i.isEditable = false);

  // Set current item to editable
  item.isEditable = true;
  item.isDropdownOpen = false;

  // Store references for editing
  this.editingItem = item;
  this.description = item.description || '';

  // Try to find the status object based on value or label
  const found = this.statuses.find(s =>
    s.value === item.status || s.label === item.status
  );

  if (found) {
    this.selectedStatus = found;
    item.status = found.value; // ✅ Normalize status to value (e.g., "ON_TRACK")
  } else {
    this.selectedStatus = this.statuses[0]; // Fallback to default if not found
  }

  this.isEditable = true;
}


onDelete(item: any) {
  
  console.log('Delete clicked for:', item);
  // Optionally call delete API
}

deleteTrack(id: string) {
  const epicId = this.wholeData.id;
  const type = 'STATUS';
  
  let dialog = this.masterService.openDeleteDialog(
    CustomDeleteComponent,
    'auto',
    'auto',
    {
      heading: "Delete Work Item",
      subText: "Are you sure you want to delete this item?",
      secondaryButton: "Cancel",
      primaryButton: "Delete"
    },
    '80vw'
  );

  dialog.afterClosed().subscribe((data) => {
    if (data.response !== 'cancel') {
      this.projectService.delteEpicStatus(epicId, id, type).subscribe({
        next: () => {
          this.snackBar.open("Successfully Deleted", 'Close', { duration: 1000 });
          this.getEpicDetail();
        },
        error: (err: any) => {
          this.snackBar.open(`${err.error.message}`, 'Close', { duration: 1000 });
        },
      });
    }
  });
}
showUpdateForm = false;
isEditable=false
editingItem: any = null;

openUpdateForm() {
  this.EpicStatusUpdateList.forEach(i => i.isEditable = false);
  this.isEditable = false;
  this.editingItem = null;
  this.description = '';
  this.showUpdateForm = true;
}

cancelUpdate() {
  this.showUpdateForm = false;
  this.description = '';
  this.isDropdownOpen = false;
}
cancelEdit() {
  this.EpicStatusUpdateList.forEach(i => i.isEditable = false);
  this.isEditable = false;
  this.editingItem = null;
  this.description = '';
}
updateItem() {
  if (!this.editingItem) return;
  this.editingItem.description = this.description;
  this.editingItem.status = this.selectedStatus.label;

  const payload = {
    id: this.editingItem.id,
    epicId: this.wholeData?.id ,
    projectId: this.projectData?.projectId,
    status: this.selectedStatus?.value || this.editingItem.status,
    description: this.description,
    title: this.editingItem.title || '',
    type: this.editingItem.type
  };

  this.updateOnTrack(payload);

  this.cancelEdit();
}
saveUpdate() {
  if (this.editingItem) {
    // ✅ Update existing
    this.editingItem.description = this.description;
    this.editingItem.status = this.selectedStatus.label;
  } else {
    // ✅ Create new
    const newItem = {
      id: Date.now(),
      description: this.description,
      status: this.selectedStatus.label,
      date: 'Today',
      user: 'anand',
    };
    this.EpicStatusUpdateList.unshift(newItem);
  }

  // Reset form
  this.cancelUpdate();
}

cancelEditItem(item: any) {
  if (!item) return;
  item.isEditable = false;
  if (this.editingItem && this.editingItem.id === item.id) {
    this.editingItem = null;
  }
  this.description = '';
  this.isEditable = false;
}

submitEdit(item: any) {
  if (!item) return;
  const payload = {
    id: item.id,
    epicId: this.wholeData?.id,
    projectId: this.projectData?.projectId,
    status: this.selectedStatus?.value || item.status,
    description: this.description,
    title: item.title,
    type: item.type
  };

  this.updateOnTrack(payload);
  item.description = this.description;
  item.status = this.selectedStatus.value;
  item.isEditable = false;
  this.editingItem = null;
  this.description = '';
  this.isEditable = false;
  item.isDropdownOpen = false;
}

addWorkItemInEpic(event: MouseEvent,) {
  const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
  const rightValue = parseFloat(position.right) + 100 + 'px';
  const dialogRef = this.matDialog.open(PopupPmsComponent, {
    width: '11%',
    height: '12%',
    position: { top: position.top, right: rightValue },
    data: { status: 'WORK_ITEM_EPIC' ,id: this.wholeData.id},
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result) {
      this.selectedSubWorkItem = result;
      
      if(this.selectedSubWorkItem === 'Create new'){
        this.createWorkItem();
      }else{
        const type = 'EPIC'
        this.addExistingWorkItem(event,position,type);
      }
    }
  });
}

epicWorkitemList: any = [];
displayWorkitemComponent: any;
getEpicWorkitemList(){
  const epicId = this.wholeData.id;
  this.projectService.getEpicWorkitemList(epicId).subscribe({
    next: (response: any) => {
      this.epicWorkitemList = response?.data || [];
      console.log('Epic workitem list:', this.epicWorkitemList);
      this.computeEpicProgress();
    },
    error: (error) => {
      console.error('Error fetching epic workitem list:', error);
      this.epicWorkitemList = [];
      this.computeEpicProgress();
    }
  });
}

computeEpicProgress(): void {
  const STATIC_STATES = [
    { name: 'Backlog' },
    { name: 'Unstarted' },
    { name: 'Started' },
    { name: 'Completed' },
    { name: 'Cancelled' }
  ];
  const states = STATIC_STATES;
  const items = Array.isArray(this.epicWorkitemList) ? this.epicWorkitemList : [];
  const total = items.length;

  const progress: any[] = [];
  let matchedCount = 0;

  states.forEach((st: any) => {
  const sName = (st.name || '').toLowerCase();

  // Count items where stateMaster.name matches the static state
  const cnt = items.filter((it: any) => 
    (it.stateMaster?.name?.toLowerCase() || '') === sName
  ).length;

  matchedCount += cnt;
  progress.push({
    label: st.name,
    count: cnt,
    percent: total > 0 ? Math.round((cnt / total) * 100) : 0,
    class: st.name.toLowerCase().replace(/\s+/g, '-')
  });
});

  const other = total - matchedCount;
  if (other > 0) {
    progress.push({ label: 'Other', count: other, percent: total > 0 ? Math.round((other / total) * 100) : 0, class: 'other' });
  }

  this.progressItems = progress;
  const completedEntry = progress.find((p: any) => p.label === 'Completed');
  this.progress = completedEntry ? (completedEntry.percent || 0) : 0;
}



enableAddUpdateBtn(){
  console.log
  this.isEnableAddUpdate = true;
}
remobveAddbtn(){
    this.isEnableAddUpdate = false;
}


removeWorkitemFromEpic(id:any){
  const epicId = this.wholeData.id;
  this.projectService.removeWorkitem(epicId,id).subscribe({
    next: (response) => {
      console.log('Workitem removed from epic:', response);
      this.getEpicWorkitemList();
    },
    error: (error) => {
      console.error('Error removing workitem from epic:', error);
    }
  });
}

 deleteEpic(item: any) {
    this.projectService.deleteEpic(item).subscribe((res: any) => {
    this.dialogRef.close();

    });
  }

  onEpicDescriptionSave() {
    if (this.tempDescription !== this.wholeData.description) {
      this.wholeData.description = this.tempDescription;
      this.updateEpicField('description', this.tempDescription);
    }
    this.isDescriptionEditing = false;
  }
  onEpicTitleSave() {
    if (this.tempTitle !== this.wholeData.title) {
      this.wholeData.title = this.tempTitle;
      this.updateEpicField('title', this.tempTitle);
    }
    this.isTitleEditing = false;
  }

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

updatePropertyType(res:any){
  this.projectService.updateEpicCustomProperties(this.workitem.id,res).subscribe({
    next: (response) => {
      console.log('update from epic:', response);
       this.snackBar.open('Property update successfully', 'Close', { duration: 2000 });
    },
    error: (error) => {
      console.error('Error removing workitem from epic:', error);
    }
  });

}

copyWorkitemLink() {
  const projectId = this.wholeData.project.id;
  const workitemId = this.wholeData.id;

  const workitemLink = `${window.location.origin}/admin/work-management/work-item?projectId=${projectId}&workitemId=${workitemId}`;

  navigator.clipboard.writeText(workitemLink)
    .then(() => {
      this.snackBar.open('Work item link copied to clipboard!', 'Close', { duration: 2000 });
    })
    .catch(err => {
      console.error('Failed to copy work item link:', err);
      this.snackBar.open('Failed to copy link. Please try again.', 'Close', { duration: 2000 });
    });
}
}
