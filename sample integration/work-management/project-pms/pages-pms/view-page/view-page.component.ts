import { Component, HostListener, Input, OnInit } from '@angular/core';
import { Router, ActivatedRoute } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { WorkManagementService } from '../../../work-management.service';

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
  linkedCycles: any[];
  linkedModules: any[];
  linkedPages: any[];
}

@Component({
  selector: 'app-view-page',
  templateUrl: './view-page.component.html',
  styleUrls: ['./view-page.component.scss']
})
export class ViewPageComponent implements OnInit {
  screenWidth: any;
  pageId: string | null = null;
  screenLoading: boolean = false;
  projectDetails:any;

  // @Input() pageId: any;
  // @Input() projectDetails: any;

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
    wordCount: 0,
    linkedCycles: [],
    linkedModules: [],
    linkedPages: []
  };

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private _snackbar: MatSnackBar,
    private projectService: WorkManagementService
  ) {

    this.route.queryParams.subscribe(params => {
    if (params['pageId']) {
        this.pageId = params['pageId'];
        this.projectDetails = JSON.parse(localStorage.getItem('projectDetails') || '{}');
      } 
      else {
        this.pageId = history.state.pageId;
        this.projectDetails = history.state.projectDetails;
      }
  });
    
    // if (this.router.getCurrentNavigation()?.extras.state?.['pageId']) {
    //   this.pageId = this.router.getCurrentNavigation()?.extras.state?.['pageId'];
    //   this.projectDetails = this.router.getCurrentNavigation()?.extras.state?.['projectDetails'];
    // } else {
    //   this.route.queryParams.subscribe(params => {
    //     this.pageId = params['pageId'];
    //     this.projectDetails = params['projectDetails'];
    //   });
    // }

    this.getScreenSize();
  }

  @HostListener('window:resize', ['$event'])
  getScreenSize() {
    this.screenWidth = window.innerWidth;
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
    
    if (this.isDropdownOpen) {
      setTimeout(() => {
        const button = (event.target as HTMLElement).closest('.linked-items-btn');
        const dropdown = document.querySelector('.linked-items-dropdown') as HTMLElement;
        
        if (button && dropdown) {
          const buttonRect = button.getBoundingClientRect();
          dropdown.style.top = `${buttonRect.bottom + 4}px`;
          dropdown.style.left = `${buttonRect.left}px`;
          
          const rightEdge = buttonRect.left + dropdown.offsetWidth;
          if (rightEdge > window.innerWidth) {
            dropdown.style.left = `${buttonRect.right - dropdown.offsetWidth}px`;
          }
        }
      });
    }
  }

  hasLinkedItems(): boolean {
    return this.getLinkedCyclesCount() > 0 || 
           this.getLinkedPagesCount() > 0 || 
           this.getLinkedModulesCount() > 0;
  }

  getLinkedItemsText(): string {
    const totalItems = this.getLinkedCyclesCount() + 
                      this.getLinkedPagesCount() + 
                      this.getLinkedModulesCount();
    
    if (totalItems === 1) {
      if (this.getLinkedCyclesCount() === 1) return this.getLinkedCycles()[0].name;
      if (this.getLinkedPagesCount() === 1) return this.getLinkedPages()[0].name;
      if (this.getLinkedModulesCount() === 1) return this.getLinkedModules()[0].name;
    }
    
    return `${totalItems} items linked`;
  }

  getLinkedPagesCount(): number {
    return this.page?.linkedPages?.length || 0;
  }

  getLinkedModulesCount(): number {
    return this.page?.linkedModules?.length || 0;
  }

  getLinkedCyclesCount(): number {
    return this.page?.linkedCycles?.length || 0;
  }

  getLinkedPages(): any[] {
    return this.page?.linkedPages || [];
  }

  getLinkedModules(): any[] {
    return this.page?.linkedModules || [];
  }

  getLinkedCycles(): any[] {
    return this.page?.linkedCycles || [];
  }

  async ngOnInit(): Promise<void> {
    if (this.pageId) {
      await this.loadPageDetails();
    } else {
      // For testing - remove this in production
      // this.loadTestData();
      this._snackbar.open('No page ID provided', 'Close', { duration: 3000 });
      this.back();
    }
  }



  async loadPageDetails(): Promise<void> {
  this.screenLoading = true;
  try {
    const pageDetail: any = await this.projectService.getPageDetailsById(this.pageId!).toPromise();

    if (pageDetail && (pageDetail.data || pageDetail.id)) {
      const data = pageDetail.data || pageDetail;

      this.page.id = data.id;
      this.page.pageTitle = data.title;
      this.page.visibility = data.visibility as 'PUBLIC' | 'PRIVATE' | 'ARCHIVED';
      this.page.locked = data.locked;
      this.page.favourite = data.favourite;

      // Parse blocks
      let blocksArray = [];
      try {
        const content = data.content;
        if (typeof content === 'string') {
          const parsed = JSON.parse(content);
          blocksArray = Array.isArray(parsed?.blocks) ? parsed.blocks : [];
        } else if (typeof content === 'object') {
          blocksArray = Array.isArray(content?.blocks) ? content.blocks : [];
        }
      } catch (e) {
        console.warn('Error parsing content:', e);
      }
      this.page.blocks = blocksArray;

      // Reading stats
      this.calculateReadingStats();

      // ✅ Ensure project & business are set from API
      this.page.business = data.business || { id: '', name: '' };
      this.page.project = data.project || { id: '', name: '' };
      this.page.createdBy = data.createdBy || { id: '', name: '' };

      this.page.linkedCycles = data.linkedCycles || [];
      this.page.linkedModules = data.linkedModules || [];
      this.page.linkedPages = data.linkedPages || [];

      // ✅ Fix: also sync projectDetails for navigation
      if (data.project) {
        this.projectDetails = {
          projectId: data.project.id,
          projectName: data.project.name
        };
      }

      this.page.linkedCycles = data.linkedCycle || [];
      this.page.linkedModules = data.linkedModule || [];
      this.page.linkedPages = data.linkedPages || [];

    } else {
      this._snackbar.open('Page not found or returned empty data.', 'Close', { duration: 3000 });
      this.back();
    }
  } catch (error) {
    console.error('Error loading page details:', error);
    this._snackbar.open('Failed to load page details. Please try again.', 'Close', { duration: 3000 });
    this.back();
  } finally {
    this.screenLoading = false;
  }
}

  private calculateReadingStats(): void {
    let wordCount = 0;
    let fullText = '';

    this.page.blocks.forEach(block => {
      if (block.data && block.data.text) {
        let textContent = block.data.text;
        textContent = textContent.replace(/<[^>]*>/g, '');
        fullText += textContent + ' ';
      }
    });

    fullText = fullText.trim();
    wordCount = fullText ? fullText.split(/\s+/).filter(word => word !== '').length : 0;

    const wordsPerMinute = 225;
    const readTimeInMinutes = wordCount / wordsPerMinute;
    const minutes = Math.floor(readTimeInMinutes);
    const seconds = Math.round((readTimeInMinutes - minutes) * 60);

    if (minutes > 0 || seconds > 0) {
      this.page.readTime = `${minutes > 0 ? `${minutes} minute${minutes !== 1 ? 's' : ''}` : ''}${minutes && seconds ? ' ' : ''}${seconds > 0 ? `${seconds} second${seconds !== 1 ? 's' : ''}` : ''}`;
    } else {
      this.page.readTime = wordCount > 0 ? '< 1 minute' : '0 minutes';
    }

    this.page.wordCount = wordCount;
  }

  back() {
    this.router.navigate(['/admin/work-management/work-item'], {
      queryParams: { projectId: this.page.project.id , tab: 'PAGES_TAB' }
    });
  }

  editPage() {
    localStorage.setItem('pageId', this.pageId!);
    localStorage.setItem('projectDetails', JSON.stringify(this.projectDetails));
    this.router.navigate(['admin/work-management/pages/create-pages']);
  }
  

  deletePage() {
  }

  viewCycle(cycle: any) {
    // this.router.navigate(['/admin/work-management/work-item'], {
    //   queryParams: { type: 'CYCLE', cycleId: cycle.id, cycleName: cycle.name, tab: 'CYCLES_TAB', projectId: this.projectDetails.projectId }
    // });
    this.router.navigate(['/admin/work-management/work-item'], {
      queryParams: { projectId: this.projectDetails.projectId },
      state: {
        tab: 'WORKITEM_TAB',
        data: cycle,
        feature: 'CYCLE'
      }
    });
  }
  viewModule(modules: any) {
    // this.router.navigate(['/admin/work-management/work-item'], {
    //   queryParams: { type: 'MODULE', moduleId: modules.id, moduleName: modules.name, tab: 'MODULES_TAB', projectId: this.projectDetails.projectId }
    // });
    this.router.navigate(['/admin/work-management/work-item'], {
      queryParams: { projectId: this.projectDetails.projectId },
      state: {
        tab: 'WORKITEM_TAB',
        data: modules,
        feature: 'MODULE'
      }
    });
  }
  viewPage(pages:any){
    this.pageId = pages.id;
    this.loadPageDetails();
  }
}
