import {
  Component,
  ElementRef,
  HostListener,
  ViewChild,
  OnInit,
  AfterViewInit,
  OnDestroy,
  Input
} from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import Checklist from '@editorjs/checklist'
import EditorJS, { OutputData } from '@editorjs/editorjs';
const Header = require('@editorjs/header');
import ImageTool from '@editorjs/image';
import List from '@editorjs/list';
import Table from '@editorjs/table';
import Strikethrough from 'editorjs-strikethrough';
import underline from '@editorjs/underline';
import * as AWS from 'aws-sdk';
const Delimiter = require('@editorjs/delimiter');
const InlineCode = require('@editorjs/inline-code');
const ColorPlugin = require('editorjs-text-color-plugin');
import { environment } from 'src/environments/environment';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatDialog, MatDialogRef } from '@angular/material/dialog';
import { WorkManagementService } from '../../../work-management.service';
import { PopupPmsComponent } from '../../popup-pms/popup-pms.component';
import { DeleteSegmentationComponent } from 'src/app/master-config-components/micro-apps/crm/segmentation/delete-segmentation/delete-segmentation.component';
import { CreatePagesTemplateComponent } from './create-pages-template.component';
import { ContextEnvelope } from './context-envelope';

interface Page {
  id?: string;
  pageTitle: string;
  blocks: any[];
  visibility: 'PUBLIC' | 'PRIVATE' | 'ARCHIVED';
  pageType: 'BUSINESS';
  business: { id: string; name: string };
  project: { id: string; name: string };
  createdBy: { id: string; name: string };
  locked: boolean;
  favourite: boolean;
  readTime: string;
  wordCount: number;
}

@Component({
  selector: 'app-create-pages',
  templateUrl: './create-pages.component.html',
  styleUrls: ['./create-pages.component.scss']
})
export class CreatePagesComponent implements OnInit, AfterViewInit, OnDestroy {
  action: String = '';
  homeDirection: boolean = false;
  screenWidth: any;
  screenLoading: boolean = false;
  readTime: any = 0;
  wordCount: any = 0;
  characterCount: any = 0;
  paragraphCount: any = 0;
  sentenceCount: any = 0;
  fullWidth: boolean = false;
  unsavedChanges: boolean = false;

  page: Page = {
    id: undefined,
    pageTitle: '',
    blocks: [],
    visibility: 'PUBLIC',
    pageType: 'BUSINESS',
    business: { id: '', name: '' },
    project: { id: '', name: '' },
    createdBy: { id: '', name: '' },
    locked: false,
    favourite: false,
    readTime: '0',
    wordCount: 0
  };

  editor: EditorJS | undefined;
  previousData: OutputData | undefined;
  showAnalytics: boolean = false;

  autoSaveInterval: any;
  autoSaveTimer: any;
  lastSaveTime: Date | null = null;
  isSaving: boolean = false;
  autoSaveDelay: number = 3000; 
  autoSaveIntervalTime: number = 30000;

  selectedCycles: any[] = [];
  selectedModules: any[] = [];
  selectedPage: any[] = [];
  selectedMembers: any[] = [];
  cycleList: any = [];
  moduleList: any = [];
  businessId: any;
  projectId: any;


  @ViewChild('editor', { read: ElementRef, static: true }) editorElement: ElementRef | undefined;
  pageId: string | null = null;
  pageDetail: any;
  @Input() projectDetails: any;

constructor(
  private router: Router,
  private route: ActivatedRoute,
  private _snackbar: MatSnackBar,
  public dialogRef: MatDialogRef<CreatePagesComponent>,
  private projectService: WorkManagementService,
  private matDialog: MatDialog
) {
  // ✅ Handle query params
  this.route.queryParams.subscribe(queryParams => {
    this.action = queryParams['action'];
    this.pageId = queryParams['pageId'] || localStorage.getItem('pageId'); // fallback from LS

    if (this.action === 'addPageHome') {
      this.homeDirection = true;
    }
  });

  // ✅ Prefer state → fallback to localStorage
  this.projectDetails = this.router.getCurrentNavigation()?.extras.state?.['projectDetails'];

  if (!this.projectDetails) {
    const local = localStorage.getItem('projectDetails');
    if (local) {
      try {
        this.projectDetails = JSON.parse(local);
      } catch {
        this._snackbar.open('Failed to load project details.', 'Close', { duration: 1000 });
      }
    }
  }

  this.getScreenSize();
}

@HostListener('window:resize', ['$event'])
getScreenSize() {
  this.screenWidth = window.innerWidth;
}
@HostListener('window:beforeunload', ['$event'])
handleBeforeUnload(event: Event) {
  this.performAutoSave(); 
}

async ngOnInit(): Promise<void> {
  // ✅ Business details
  try {
    const bDetails = localStorage.getItem('bDetails');
    if (bDetails) {
      const parsed = JSON.parse(bDetails);
      this.page.business.id = parsed.id;
      this.page.business.name = parsed.name || 'Default Business Name';
    }
  } catch {
    this._snackbar.open('Failed to load business details.', 'Close', { duration: 1000 });
  }

  if (!this.pageId) {
    this.page.createdBy.id = localStorage.getItem('staffId') || '';
    this.page.createdBy.name = localStorage.getItem('staffName') || '';
  }
  // ✅ Project setup
  if (this.projectDetails) {
    this.page.project.id = this.projectDetails.projectId;
    this.page.project.name = this.projectDetails.projectName;
    this.projectId = this.projectDetails.projectId;
  }
  this.businessId = this.page.business.id;

  if (this.businessId && this.projectId) {
    this.getAllCycles();
    this.getallModules();
    this.getAllPages();
  }

  // ✅ Editing mode
  if (this.pageId) {
    await this.loadPageForEditing();
  } else {
    // ✅ New page
    this.previousData = { blocks: [] };
    this.intialzedEditor();
  }

  this.startAutoSave();
  this.getProjectMembers(this.projectId);
  if(!this.pageId){
    this.selectedMembers.push({
      id: localStorage.getItem('staffId'),
      name: localStorage.getItem('staffName')
    });
  }
}

// 🔹 Extracted logic into a helper for readability
private async loadPageForEditing(): Promise<void> {
  this.screenLoading = true;
  try {
    this.pageDetail = await this.projectService.getPageDetailsById(this.pageId!).toPromise();

    if (this.pageDetail?.data) {
      const data = this.pageDetail.data;

      // Base info
      this.page.id = data.id;
      this.page.pageTitle = data.title;
      this.page.visibility = data.visibility;
      this.page.locked = data.locked;
      this.page.favourite = data.favourite;
      this.page.readTime = data.readTime;
      this.page.wordCount = data.wordCount;
      this.page.createdBy = data.createdBy;

      // Project / Business fallback
      this.page.project.id = this.page.project.id || data.project?.id || '';
      this.page.project.name = this.page.project.name || data.project?.name || '';
      this.projectId = this.page.project.id;

      this.page.business.id = this.page.business.id || data.business?.id || '';
      this.page.business.name = this.page.business.name || data.business?.name || '';
      this.businessId = this.page.business.id;

      // Parse editor blocks
      try {
        const content = typeof data.content === 'string' ? JSON.parse(data.content) : data.content;
        this.page.blocks = Array.isArray(content?.blocks) ? content.blocks : [];
      } catch (err) {
        console.warn('Error parsing content:', err);
      }

      this.previousData = { blocks: this.page.blocks };

  if (data.linkedCycle && Array.isArray(data.linkedCycle)) {
    this.selectedCycles = data.linkedCycle.filter((cycle: any) => cycle.id);
  }
  if (data.linkedModule && Array.isArray(data.linkedModule)) {
    this.selectedModules = data.linkedModule.filter((module: any) => module.id);
  }
  if (data.linkedPages && Array.isArray(data.linkedPages)) {
    this.selectedPage = data.linkedPages.filter((page: any) => page.id);
  }
  if (data.linkedMembers && Array.isArray(data.linkedMembers)) {
    this.selectedMembers = data.linkedMembers.filter((member: any) => member.id);
  }

      this.intialzedEditor();
    } else {
      this._snackbar.open('Page not found or returned empty data.', 'Close', { duration: 1000 });
    }
  } catch {
    this._snackbar.open('Failed to load page for editing. Please try again.', 'Close', { duration: 1000 });
  } finally {
    this.screenLoading = false;
  }
}



  ngAfterViewInit(): void {
    // this.intialzedEditor();
  }

private intialzedEditor(): void {
  if (!this.editorElement?.nativeElement) return;

  const isReadOnly = this.page?.locked || false;

  this.editor = new EditorJS({
    holder: this.editorElement.nativeElement,
    readOnly: isReadOnly, // 👈 read-only mode if locked or readOnly is true
    tools: {
      
      delimiter: Delimiter,
      header: {
        class: Header,
        shortcut: 'CMD+SHIFT+H',
        inlineToolbar: ['link', 'bold', 'italic', 'underline', 'strikethrough'],
      },
      underline: underline,
      strikethrough: Strikethrough,
      Color: {
        class: ColorPlugin,
        config: {
          colorCollections: [
            '#EC7878', '#9C27B0', '#673AB7', '#3F51B5', '#0070FF',
            '#03A9F4', '#00BCD4', '#4CAF50', '#8BC34A', '#CDDC39', '#FFF',
          ],
          defaultColor: '#FF1300',
          type: 'text'
        }
      },
      Marker: {
        class: ColorPlugin,
        config: {
          defaultColor: '#FFBF00',
          type: 'marker'
        }
      },
      list: {
        class: List,
        inlineToolbar: true,
        config: {
          defaultStyle: 'unordered' 
        }
      },
      checklist: {
        class: Checklist,
        inlineToolbar: true
      },
      inlineCode: {
        class: InlineCode,
        shortcut: 'CMD+SHIFT+M'
      },
      image: {
        class: ImageTool,
        config: {
          data: {
            withBorder: false,
            stretched: false,
            withBackground: false
          },
          uploader: {
            uploadByFile: (file: any) => {
              if (isReadOnly) {
                return Promise.resolve({
                  success: 0,
                  file: { url: '' }
                });
              }

              const AWSService = AWS;
              const imageEnvCognito = environment.componentImageUploading.CredentialsProvider.CognitoIdentity.Default;
              const imageEnvUtility = environment.componentImageUploading.S3TransferUtility.Default;
              const region = imageEnvUtility.Region;
              const bucketName = imageEnvUtility.Bucket;
              const IdentityPoolId = imageEnvCognito.PoolId;

              AWSService.config.update({
                region: region,
                credentials: new AWSService.CognitoIdentityCredentials({ IdentityPoolId })
              });

              const s3 = new AWSService.S3({ apiVersion: '2012-07-10', params: { Bucket: bucketName } });

              return new Promise((res, rej) => {
                if (file) {
                  const reader = new FileReader();
                  reader.readAsDataURL(file);
                  reader.onload = () => {
                    s3.upload(
                      {
                        Key: 'images/' + Math.floor(100000 + Math.random() * 900000) + 'c' + new Date().getTime() + file.name,
                        Bucket: bucketName,
                        Body: file,
                        ACL: 'public-read'
                      },
                      (err: any, data: any) => {
                        if (err) rej(err);
                        else res(data);
                      }
                    );
                  };
                } else {
                  rej('No file provided for upload.');
                }
              })
              .then((data: any) => ({
                success: 1,
                file: { url: data.Location, height: '500px' }
              }))
              .catch(() => ({
                success: 0,
                file: { url: '' }
              }));
            }
          }
        }
      },
      table: {
        class: Table,
        inlineToolbar: true,
        config: { rows: 4, cols: 5 }
      }
    },
    data: this.previousData,
    defaultBlock: 'header',
    autofocus: !isReadOnly,
    placeholder: isReadOnly ? '' : 'Press \'/\' for commands...',
    onChange: () => {
      this.wordCounter(null);
      this.onContentChange();
    }
  });
}



//   setVisibility(visibility: 'PUBLIC' | 'PRIVATE' | 'ARCHIVED'): void {
//     this.page.visibility = visibility;
//     this._snackbar.open(`Page visibility set to ${visibility.toLowerCase()}!`, 'Ok', { duration: 1000 });
//   }
//   toggleVisibility(): void {
//   const newVisibility = this.page.visibility === 'PUBLIC' ? 'PRIVATE' : 'PUBLIC';
//   this.page.visibility = newVisibility;
//   this._snackbar.open(
//     `Page visibility set to ${newVisibility.toLowerCase()}!`,
//     'Ok',
//     { duration: 1000 }
//   );
// }
toggleVisibility(): void {
  const newVisibility = this.page.visibility === 'PUBLIC' ? 'PRIVATE' : 'PUBLIC';
  this.setVisibility(newVisibility);
}

setVisibility(visibility: 'PUBLIC' | 'PRIVATE' | 'ARCHIVED'): void {
  this.page.visibility = visibility;
  this.savePage();
  this._snackbar.open(
    `Page visibility set to ${visibility.toLowerCase()}!`,
    'Ok',
    { duration: 1000 }
  );
}

restoreVisibility(): void {
  this.setVisibility('PUBLIC');
}



  private preparePageData(): any {
    return {
      id: this.page.id || undefined,
      title: this.page.pageTitle,
      content: JSON.stringify({ blocks: this.page.blocks }),
      business: this.page.business,
      project: this.page.project,
      createdBy: this.page.createdBy,
      visibility: this.page.visibility,
      locked: this.page.locked,
      favourite: this.page.favourite,
      readTime: Math.ceil(this.wordCount / 225).toString(),
      wordCount: this.wordCount,
      linkedCycle: this.selectedCycles.map(cycle => ({
        id: cycle?.id,
        name: cycle?.name
      })),
      linkedModule: this.selectedModules.map(module => ({
        id: module?.id,
        name: module?.name
      })),
      linkedMembers: this.selectedMembers.map(member => ({
        id: member?.id,
        name: member?.name
      })),
      linkedPages: this.selectedPage
    };
  }

  savePage() {
    this.screenLoading = true;
    this.editor?.save().then((data: OutputData) => {
      if (!this.page.pageTitle.trim()) {
        this._snackbar.open('Please enter a page title.', 'Close', { duration: 1000 });
        this.screenLoading = false;
        return;
      }

      if (!data.blocks || !data.blocks.length) {
        this._snackbar.open('Please write some content for the page.', 'Close', { duration: 1000 });
        this.screenLoading = false;
        return;
      }

      this.page.blocks = data.blocks;
      this.getBlocksTextLen(data.blocks);
      const pageToSave = this.preparePageData();

      this.projectService.createPage(pageToSave).subscribe({
        next: () => {
          this._snackbar.open(`Page ${this.page.id ? 'updated' : 'saved'} successfully!`, 'Ok', { duration: 1000 });
          this.screenLoading = false;
          this.lastSaveTime = new Date();
          this.unsavedChanges = false;
          this.back();
        },
        error: () => {
          this._snackbar.open(`Failed to ${this.page.id ? 'update' : 'save'} page. Please try again.`, 'Close', { duration: 1000 });
          this.screenLoading = false;
        }
      });
    }).catch(() => {
      this.screenLoading = false;
      this._snackbar.open('An error occurred while preparing content. Please try again.', 'Close', { duration: 1000 });
    });
  }

  startAutoSave(): void {
    this.autoSaveInterval = setInterval(() => {
      this.performAutoSave();
    }, this.autoSaveIntervalTime);
  }

  onContentChange(): void {
    this.unsavedChanges = true;
    if (this.autoSaveTimer) {
      clearTimeout(this.autoSaveTimer);
    }
    this.autoSaveTimer = setTimeout(() => {
      this.performAutoSave();
    }, this.autoSaveDelay);
  }

  performAutoSave(): void {
    if (this.isSaving || !this.unsavedChanges || !this.page.pageTitle.trim()) {
      return;
    }

    this.isSaving = true;
    
    this.editor?.save().then((data: OutputData) => {
      if (!data.blocks || !data.blocks.length) {
        this.isSaving = false;
        return;
      }

      this.page.blocks = data.blocks;
      this.getBlocksTextLen(data.blocks);
      const pageToSave = this.preparePageData();

      this.projectService.createPage(pageToSave).subscribe({
        next: (response: any) => {
          if (!this.page.id && response?.data?.id) {
            this.page.id = response.data.id;
          }
          this.lastSaveTime = new Date();
          this.unsavedChanges = false;
          this.isSaving = false;
        },
        error: (error) => {
          this.isSaving = false;
          console.error('Auto-save failed:', error);
        }
      });
    }).catch((error) => {
      this.isSaving = false;
      console.error('Auto-save preparation failed:', error);
    });
  }

  stopAutoSave(): void {
    if (this.autoSaveInterval) {
      clearInterval(this.autoSaveInterval);
      this.autoSaveInterval = null;
    }
    
    if (this.autoSaveTimer) {
      clearTimeout(this.autoSaveTimer);
      this.autoSaveTimer = null;
    }
  }

  getLastSaveText(): string {
    if (!this.lastSaveTime) {
      return 'Never saved';
    }
    
    return 'Saved';
  }

  onTitleChange(): void {
    this.unsavedChanges = true;
    this.onContentChange();
  }

  couldBeCounted(block: any): boolean {
    return 'text' in block.data;
  }

  getBlocksTextLen(blocks: any[]): void {
    this.wordCount = 0;
    this.characterCount = 0;
    this.sentenceCount = 0;
    this.paragraphCount = 0;

    let fullText = '';
    blocks.filter(this.couldBeCounted).forEach(block => {
      let data = block.data.text;
      data = data.replace(/<[^>]*>/g, '');
      fullText += data + ' ';
    });

    fullText = fullText.trim();
    this.characterCount = fullText.length;
    this.wordCount = fullText ? fullText.split(/\s+/).filter(word => word !== '').length : 0;
    this.sentenceCount = fullText ? fullText.split(/[.!?]\s*/).filter(sentence => sentence.trim() !== '').length : 0;
    this.paragraphCount = blocks.length;

    const wordsPerMinute = 225;
    const readTimeInminutes = this.wordCount / wordsPerMinute;
    const minutes = Math.floor(readTimeInminutes);
    const seconds = Math.round((readTimeInminutes - minutes) * 60);

    if (minutes > 0 || seconds > 0) {
      this.readTime = `${minutes > 0 ? `${minutes} minute${minutes !== 1 ? 's' : ''}` : ''}${minutes && seconds ? ' ' : ''}${seconds > 0 ? `${seconds} second${seconds !== 1 ? 's' : ''}` : ''}`;
    } else {
      this.readTime = this.wordCount > 0 ? '< 1 minute' : '0 minutes 0 seconds';
    }
  }

  async wordCounter(_: any) {
    const savedData = await this.editor?.save();
    if (savedData) {
      this.getBlocksTextLen(savedData.blocks);
    }
  }

  back() {
    if (this.unsavedChanges && this.page.pageTitle.trim()) {
      this.performAutoSave();
      setTimeout(() => {
        this.navigateBack();
      }, 500);
    } else {
      this.navigateBack();
    }
  }

  private navigateBack() {
    if (this.homeDirection) {
      this.router.navigate(['/admin/home']);
    } else {
      this.router.navigate(['/admin/work-management/work-item'], {
        queryParams: { projectId: this.page.project.id , tab: 'PAGES_TAB' }
      });
    }
  }

  openPageSettingsDialog(ev: MouseEvent) {
    ev.stopPropagation();
    this._snackbar.open('Page settings dialog would open here', 'Ok', { duration: 1500 });
  }

  deletePage() {
    this._snackbar.open(this.page.id ? 'Page delete dialog would open here' : 'Cannot delete a page that has not been saved yet.', 'Ok', { duration: 1500 });
  }

  backToView() {
    if(this.pageId){
      this.router.navigate(['/admin/work-management/pages/view-page'], {
      state: {
        pageId: this.pageId,
        projectDetails: this.projectDetails
      }
    });
    } else {
      this.router.navigate(['/admin/work-management/work-item'], {
      queryParams: { projectId: this.page.project.id , tab: 'PAGES_TAB' }
    });
    }
  }
  closePage() {
    if (this.unsavedChanges && this.page.pageTitle.trim()) {
      this.performAutoSave();
      setTimeout(() => {
        this.backToView();
      }, 500);
    } else {
      this.backToView();
    }
  }

  toggleAnalytics(event: MouseEvent) {
    event.stopPropagation();
    this.showAnalytics = !this.showAnalytics;

    if (this.showAnalytics) {
      setTimeout(() => document.addEventListener('click', this.closeAnalytics), 0);
    }
  }

  closeAnalytics = (event: MouseEvent) => {
    const analyticsPopup = document.querySelector('.analytics-popup');
    const toggleButton = (event.target as HTMLElement)?.closest('.btn-primary')?.querySelector('.fa-chart-bar');

    if (analyticsPopup && !analyticsPopup.contains(event.target as Node) && !toggleButton?.contains(event.target as Node)) {
      this.showAnalytics = false;
      document.removeEventListener('click', this.closeAnalytics);
    }
  }

  onCycle(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      data: { status: 'CYCLE', cycle: this.cycleList }
    });
    
    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        const existingIndex = this.selectedCycles.findIndex(cycle => cycle.id === result.id);
        if (existingIndex === -1) {
          this.selectedCycles.push(result);
        }
      }
    });
  }
  onModule(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      data: { status: 'MODULE', module: this.moduleList }
    });
    
    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        const existingIndex = this.selectedModules.findIndex(module => module.id === result.id);
        if (existingIndex === -1) {
          this.selectedModules.push(result);
        }
      }
    });
  }

  onPage(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '25%',
      position: { top: position.top, right: position.right },
      data: { status: 'PAGE', page: this.pageList }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        const existingIndex = this.selectedPage.findIndex(page => page.id === result.id);
        if (existingIndex === -1) {
          this.selectedPage.push(result);
        }
      }
    });
  }
  onMembers(event: MouseEvent) {
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
      }
    });
  }

  // Get button position for popup positioning
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
      top = buttonRect.bottom + window.scrollY - 80;
    } else {
      // Place above if there's not enough space below but enough above
      top = buttonRect.top + window.scrollY - dialogHeight - 80; 
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

  getallModules() {
    if (!this.projectId || !this.businessId) return;
    
    let payload = {
      projectId: this.projectId,
      businessId: this.businessId
    }
    this.projectService.getAllModules(payload).subscribe({
      next: (response: any) => {
        this.moduleList = response.data || [];
      },
      error: (error) => {
        console.error('Error fetching modules:', error);
      }
    });
  }

  getAllCycles() {
    if (!this.businessId || !this.projectId) return;
    
    this.projectService.getCycleById(this.businessId, this.projectId).subscribe({
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

  pageList:any ;
  getAllPages(){
    let pId = this.projectId;
        let payload = {
      moduleId: null,
      cycleId: null,
      pageId: null,
      createdBy: null,
      memberIds: null
    };
    this.projectService.getAllPages(pId, payload).subscribe({
      next: (response: any) => {
        const data = response?.data || [];
        this.pageList = data;
      },
      error: (error) => {
        console.error('Error fetching pages:', error);
      }
    });
  }

  removeCycle(event: Event, cycleId?: string) {
    event.stopPropagation();
    if (cycleId) {
      this.selectedCycles = this.selectedCycles.filter(cycle => cycle.id !== cycleId);
    } else {
      this.selectedCycles = [];
    }
  }

  removeModule(event: Event, moduleId?: string) {
    event.stopPropagation();
    if (moduleId) {
      this.selectedModules = this.selectedModules.filter(module => module.id !== moduleId);
    } else {
      this.selectedModules = [];
    }
  }
  removePage(event: Event, pageId?: string) {
    event.stopPropagation();
    if (pageId) {
      this.selectedPage = this.selectedPage.filter(page => page.id !== pageId);
    } else {
      this.selectedPage = [];
    }
  }

  removeMember(event: Event, memberId?: string) {
    event.stopPropagation();
    if (memberId) {
      this.selectedMembers = this.selectedMembers.filter(member => member.id !== memberId);
    } else {
      this.selectedMembers = [];
    }
  }

  confirmDiscardOrSave() {
  const dialogRef = this.matDialog.open(DeleteSegmentationComponent, {
    width: '400px',
    data: {
      title: 'Unsaved Changes',
      message: 'You have unsaved changes. Do you want to save them before leaving?',
      confirmText: 'Save',
      cancelText: 'Discard'
    }
  });

  dialogRef.afterClosed().subscribe(result => {
    if (result === 'save') {
      this.savePage();
      this.unsavedChanges = false;
    } else if (result === 'discard') {
      this.unsavedChanges = false;
    }
  });
}
@HostListener('document:click', ['$event'])
handleOutsideClick(event: MouseEvent) {
  if (this.editorElement && !this.editorElement.nativeElement.contains(event.target)) {
    if (this.unsavedChanges && this.page.pageTitle.trim()) {
      this.performAutoSave();
    }
  }
}
  isDropdownOpen = false;

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent) {
    const dropdownElement = (event.target as HTMLElement).closest('.linked-dropdown');
    if (!dropdownElement) {
      this.isDropdownOpen = false;
    }
  }

  toggleDropdown(event: Event) {
    event.stopPropagation();
    this.isDropdownOpen = !this.isDropdownOpen;
  }

  hasLinkedItems(): boolean {
    return this.selectedCycles.length > 0 || 
           this.selectedPage.length > 0 || 
           this.selectedModules.length > 0 ||
           this.selectedMembers.length > 0;
  }

  getLinkedItemsText(): string {
    const totalItems = this.selectedCycles.length + 
                       this.selectedPage.length + 
                       this.selectedModules.length +
                       this.selectedMembers.length;
    
    if (totalItems === 1) {
      if (this.selectedCycles.length > 0) return this.selectedCycles[0].name;
      if (this.selectedPage.length > 0) return this.selectedPage[0].name;
      if (this.selectedModules.length > 0) return this.selectedModules[0].name;
      if (this.selectedMembers.length > 0) return this.selectedMembers[0].name;
    }
    
    return `${totalItems} items linked`;
  }

  getCycleButtonText(): string {
    return this.selectedCycles.length > 0 ? 'Add Cycle' : 'Link Cycle';
  }

  getModuleButtonText(): string {
    return this.selectedModules.length > 0 ? 'Add Module' : 'Link Module';
  }
  getPageButtonText(): string {
    return this.selectedPage.length > 0 ? 'Add Page' : 'Link Page';
  }

  ngOnDestroy() {
    localStorage.removeItem('projectDetails');
    localStorage.removeItem('pageId');
    document.removeEventListener('click', this.closeAnalytics);
    if (this.unsavedChanges && this.page.pageTitle.trim()) {
      this.performAutoSave();
    }
    
    this.stopAutoSave();
    this.editor?.destroy();
  }

  makeCopy() {
    this._snackbar.open('Make a copy functionality would be implemented here.', 'Ok', { duration: 1500 });
  }

  viewVersionHistory() {
    this._snackbar.open('Version history functionality would be implemented here.', 'Ok', { duration: 1500 });
  }

  copyMarkdown() {
    this._snackbar.open('Copy markdown functionality would be implemented here.', 'Ok', { duration: 1500 });
  }

  exportPage() {
    this._snackbar.open('Export page functionality would be implemented here.', 'Ok', { duration: 1500 });
  }

   membersList:any;
   addMemberAccess:any;
  getProjectMembers(projectId: any) {
  this.projectService.getAllMembers(projectId).subscribe(
    (res: any) => {
      this.membersList = res.data || [];
      const staffId = localStorage.getItem('staffId');
      const matchedMember = this.membersList.find(member => member.memberId === staffId);
      this.addMemberAccess = matchedMember;
    },
    (error: any) => {
      console.error('Error fetching members:', error);
    }
  );
}

  // Template functionality - same as work items
  openTemplates(): void {
    const dialogConfig = {
      width: this.screenWidth > 992 ? '50%' : '55%',
      height: 'fit-content',
      maxWidth: '100vw',
      position: { top: '8vh' },
      data: {
        mode: 'PAGE_TEMPLATES',
        projectData: this.projectDetails,
        pageId: this.pageId,
        template: this.page.pageTitle ? 'existing' : 'new'
      }
    };

    const dialog = this.matDialog.open(CreatePagesTemplateComponent, dialogConfig);
    dialog.afterClosed().subscribe((result) => {
      if (result) {
        this.handleTemplateResult(result);
      }
      this.refreshData();
    });
  }

  private refreshData(): void {
    // Refresh page data if needed
  }

  private insertContentIntoEditor(content: string): void {
    if (this.editor && content) {
      const blocks = this.parseContentToBlocks(content);
      this.editor.render({ blocks }).then(() => {
        if (this.editor) {
          this.editor.focus();
        }
        this.onContentChange();
      }).catch((error) => {
        console.error('Error rendering content:', error);
      });
    }
  }

  private parseContentToBlocks(content: string): any[] {
    const blocks: any[] = [];

    if (!content.trim()) return blocks;

    // Split by markdown headers and paragraphs
    const lines = content.split('\n');
    let currentText = '';

    for (const line of lines) {
      if (line.startsWith('# ')) {
        // Push previous text as paragraph if exists
        if (currentText.trim()) {
          blocks.push({
            type: 'paragraph',
            data: { text: currentText.trim() }
          });
          currentText = '';
        }

        // Add header
        blocks.push({
          type: 'header',
          data: {
            text: line.substring(2).trim(),
            level: 1
          }
        });
      } else if (line.startsWith('## ')) {
        // Push previous text as paragraph if exists
        if (currentText.trim()) {
          blocks.push({
            type: 'paragraph',
            data: { text: currentText.trim() }
          });
          currentText = '';
        }

        // Add header
        blocks.push({
          type: 'header',
          data: {
            text: line.substring(3).trim(),
            level: 2
          }
        });
      } else if (line.startsWith('### ')) {
        // Push previous text as paragraph if exists
        if (currentText.trim()) {
          blocks.push({
            type: 'paragraph',
            data: { text: currentText.trim() }
          });
          currentText = '';
        }

        // Add header
        blocks.push({
          type: 'header',
          data: {
            text: line.substring(4).trim(),
            level: 3
          }
        });
      } else if (line.trim() === '') {
        // Empty line - push current text if exists
        if (currentText.trim()) {
          blocks.push({
            type: 'paragraph',
            data: { text: currentText.trim() }
          });
          currentText = '';
        }
      } else {
        // Regular text line
        currentText += line + '\n';
      }
    }

    // Push remaining text
    if (currentText.trim()) {
      blocks.push({
        type: 'paragraph',
        data: { text: currentText.trim() }
      });
    }

    return blocks.length > 0 ? blocks : [{
      type: 'paragraph',
      data: { text: content }
    }];
  }

  // Handle template result
  private handleTemplateResult(result: any): void {
    if (result) {
      // Handle new blocks format
      if (result.blocks && Array.isArray(result.blocks)) {
        // Set page title based on first header block or use a default
        const firstHeader = result.blocks.find((block: any) => block.type === 'header');
        this.page.pageTitle = firstHeader ? firstHeader.data.text : 'Generated Content';

        // Render blocks directly into editor
        if (this.editor) {
          this.editor.render({ blocks: result.blocks }).then(() => {
            if (this.editor) {
              this.editor.focus();
            }
            this.onContentChange();
          }).catch((error) => {
            console.error('Error rendering blocks:', error);
          });
        }
      }
      // Fallback for old template format (for backward compatibility)
      else if (result.template) {
        // Set page title from template
        this.page.pageTitle = result.template.title || '';

        // Insert content into editor
        if (result.template.content) {
          this.insertContentIntoEditor(result.template.content);
        }

        // Trigger content change to mark as unsaved
        this.onContentChange();
        this.onTitleChange();
      }

      // Trigger content change to mark as unsaved
      this.onContentChange();
      this.onTitleChange();
    }
  }
}
