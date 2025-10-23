import { Component, ElementRef, HostListener, QueryList, ViewChild, ViewChildren, AfterViewInit } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { Router } from '@angular/router';
import * as $ from 'jquery';
import { PopupPmsComponent } from '../../project-pms/popup-pms/popup-pms.component';
import { WorkManagementService } from '../../work-management.service';
import { DetailWorkitemComponent } from '../../project-pms/work-item-pms/detail-workitem/detail-workitem.component';
import { StorageKeys } from 'src/app/shared-module-files/simpo.constant';

declare var bootstrap: any;

interface linkUrls {
  url: string;
  displayTitle: string;
}
interface StateItem {
  name: string;
  completed: boolean;
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

interface Widget {
  name: string;
  enabled: boolean;
}
export interface ProjectItem {
  name: string;
  title: string;
  status: string;
  updatedTimeStamp: string;
  exist: boolean;
}


@Component({
  selector: 'app-home-pms',
  templateUrl: './home-pms.component.html',
  styleUrls: ['./home-pms.component.scss']
})
export class HomePmsComponent implements AfterViewInit {
  getRelativeTime(timestamp: string): string {
    if (!timestamp) return 'Unknown';
    
    const now = new Date();
    let past: Date;
    
    // Handle different timestamp formats
    if (timestamp.includes('T') && (timestamp.includes('+') || timestamp.endsWith('Z'))) {
      // Already in ISO format with timezone (e.g., "2025-08-31T12:45:51.424+00:00" or "2025-08-31T12:45:51.424Z")
      past = new Date(timestamp);
    } else {
      // Legacy format, add Z for UTC
      past = new Date(timestamp + 'Z');
    }
    
    // Check if date is valid
    if (isNaN(past.getTime())) {
      return 'Invalid date';
    }
    
    const diffMs = now.getTime() - past.getTime();

    const seconds = Math.floor(diffMs / 1000);
    const minutes = Math.floor(diffMs / (1000 * 60));
    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (seconds < 60) return 'Just Now';
    if (minutes < 60) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    return `${days} day${days > 1 ? 's' : ''} ago`;
  }
  projectList: any;
  recentActivityList: any;
  recentItems = [
    {
      id: 'SWB-2220',
      title: '[MOB]-lead info->email->create email->after creating add button is breaking',
      time: '1 day ago',
      status: 'Pending'
    },
    {
      id: 'PMS-1',
      title: 'Create Requirement Docs',
      time: '1 day ago',
      status: 'Pending'
    },
    {
      id: 'SWB-2432',
      title: 'send message',
      time: '1 day ago',
      status: 'Active'
    },
    {
      id: 'SWB-2432',
      title: 'send message',
      time: '1 day ago',
      status: 'Active'
    },
    {
      id: 'SWB-2432',
      title: 'send message',
      time: '1 day ago',
      status: 'Active'
    },
  ];

  settingsPayload: any;
  onSaveSettings() {
    throw new Error('Method not implemented.');
  }
  onInput() {
    throw new Error('Method not implemented.');
  }
  organizationName: any;
  timezone: any;
  language: any;
  currency: any;
  selectedFilter: any = 'All';

  constructor(private router: Router, private elementRef: ElementRef, private matDialog: MatDialog,
    private projectService: WorkManagementService,
  ) {
    this.selectedTab = 'STATES';



  }
  selectedTab: any;
  selectedSticky: any

  onTabChange(txt: any) {
    this.selectedTab = txt;
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

  filterDialog(event: MouseEvent) {
    const position = this.getButtonPosition(event, window.innerWidth * 0.12, window.innerHeight * 0.25);

    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '12%',
      height: '20%',
      position: { top: position.top, right: position.right },
      data: { status: 'HOME_FILTER' }
    });

    dialogRef.afterClosed().subscribe(result => {
      

      if (result) {
        const value = result;
        this.selectedFilter = value.name;
        if (this.selectedFilter === 'All') {
          this.getHomeProjects(true, true, true);
        } else if (this.selectedFilter === 'Projects') {
          this.getHomeProjects(true, false, false);
        } else if (this.selectedFilter === 'Work items') {
          this.getHomeProjects(false, true, false);
        } else if (this.selectedFilter === 'Pages') {
          this.getHomeProjects(false, false, true);
        }



      }
    });
  }

  ngOnInit(): void {
    this.getData();
    //  this.getQuiklinks();
    //  this.getSticikeys();
    this.updateGreeting();
    this.selectedFilter = 'All';
    this.sticky;
    this.stickyId;
    if (this.selectedFilter === 'All') {
      this.getHomeProjects(true, true, true);
    }
    let bDetails = window.localStorage.getItem('bDetails') || ''
    if (bDetails) {
      this.bDetails = JSON.parse(bDetails)
      this.businessName = this.bDetails.name;
    }

  this.userName = window.localStorage.getItem('staffName');
  }

  selectedLead = 'tarungarg';
  leads = ['tarungarg', 'shiva', 'abhilesh', 'anand'];
  searchText = '';

  displayedColumns: string[] = ['fullName', 'displayName', 'accountType', 'joiningDate'];

  members = [
    { initials: 'S', fullName: 'Shiva Kumar', displayName: 'shiva.s', accountType: 'Member', joiningDate: 'May 22, 2024' },
    { initials: 'A', fullName: 'Abhilesh Singh', displayName: 'abhileshsingh', accountType: 'Member', joiningDate: 'May 22, 2024' },
    { initials: 'A', fullName: 'Chikkam Anand', displayName: 'anand', accountType: 'Member', joiningDate: 'May 22, 2024' },
    { initials: 'B', fullName: 'Bhanu Konijeti', displayName: 'bhanu', accountType: 'Admin', joiningDate: 'May 21, 2024' },
    { initials: 'B', fullName: 'Bharath', displayName: 'bharath', accountType: 'Member', joiningDate: 'May 22, 2024' },
    { initials: 'G', fullName: 'Gaurav Sharma', displayName: 'gauravsharma531', accountType: 'Admin', joiningDate: 'April 10, 2024' },
    { initials: 'H', fullName: 'Harish Vithan', displayName: 'harish', accountType: 'Member', joiningDate: 'May 23, 2024' },
  ];

  get filteredMembers() {
    return this.members.filter(member =>
      member.fullName.toLowerCase().includes(this.searchText.toLowerCase())
    );
  }

  greeting: string = ""
  updateGreeting() {
    const now = new Date();
    const hours = now.getHours();

    if (hours >= 5 && hours < 12) {
      this.greeting = 'Good Morning';
    } else if (hours >= 12 && hours < 16) {
      this.greeting = 'Good Afternoon';
    } else {
      this.greeting = 'Good Evening';
    }
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

  states = [
    {
      name: 'Backlog',
      completed: false,
      description: '',
      isOpened: false,
      subStates: [
        {
          subStateName: 'Backlog',
          completed: false,
          isOpened: false,
          subStateDescription: '',
        },
        {
          subStateName: 'Reverted',
          completed: false,
          isOpened: false,
          subStateDescription: 'Reverted due to wrong designs',
        },
      ]
    },
    {
      name: 'Unstarted', isOpened: false, completed: true, description: '', subStates: [
        {
          subStateName: 'Unstarted',
          completed: false,
          subStateDescription: '',
          isOpened: false,
        },
      ]
    },
    {
      name: 'Completed', completed: false, isOpened: false, description: '', subStates: [
        {
          subStateName: 'Completed',
          completed: false,
          subStateDescription: '',
          isOpened: false,
        },
      ]
    },
    {
      name: 'Unstarted', completed: false, isOpened: false, description: '', subStates: [
        {
          subStateName: 'Unstarted',
          completed: false,
          subStateDescription: '',
          isOpened: false,
        },
      ]
    },
    {
      name: 'Started', completed: false, isOpened: false, description: '', subStates: [
        {
          subStateName: 'Started',
          completed: false,
          subStateDescription: '',
          isOpened: false,
        },
      ]
    },

  ];

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
      title: 'Intake',
      description: 'Stay in the loop on Work items you are subscribed to. Enable this to get notified.',
      enabled: false,
      hasToggle: true
    },

  ];

  quickLinkEdit: boolean = false;

  openModal(link?: any, editLink: boolean = false) {
    // Set values into modal input fields for editing
    this.quickLinkEdit = editLink;
    if (link && editLink) {
      this.displayTitle = link.displayTitle;
      this.url = link.url;
      this.id = link.id;
    } else {
      // Clear fields if not editing or creating new
      this.displayTitle = '';
      this.url = '';
      this.id = "";
    }

    // Show modal using Bootstrap 5 modal
    const modalElement = document.getElementById('exampleModalCenter');
    if (modalElement) {
      const modal = new bootstrap.Modal(modalElement);
      modal.show();
    }
  }


  closeModal() {
    // Clear the form fields when closing
    this.url = '';
    this.displayTitle = '';
    this.id = '';
    this.quickLinkEdit = false;
    
    const modalElement = document.getElementById('exampleModalCenter');
    if (modalElement) {
      modalElement.style.display = 'none';
      modalElement.classList.remove('show');
      document.body.classList.remove('modal-open');

      const backdrop = document.querySelector('.modal-backdrop');
      if (backdrop) {
        backdrop.remove();
      }
    }
  }




  toggleSetting(setting: SettingItem): void {
    if (setting.hasToggle) {
      setting.enabled = !setting.enabled;
    }
  }
  toggleTimeTracking() {

  }

  openStateCard(res: any) {
    res.isOpened = !res.isOpened
  }

  openSubStateCard(res: any) {
    res.isOpened = !res.isOpened
  }

  onEdit(res: any) {
    res.isOpened = true;
  }
  onCancel(res: any) {
    res.isOpened = false;
  }

  newStateName: string = '';
  editingDescription: { [key: string]: string } = {};
  showDescriptionField: string | null = null;
  timeTracking: boolean = true;

  toggleState(state: StateItem): void {
    state.completed = !state.completed;
  }



  updateDescription(state: StateItem): void {
    if (this.editingDescription[state.name] !== undefined) {
      state.description = this.editingDescription[state.name];
    }
    this.showDescriptionField = null;
  }

  cancelEdit(): void {
    this.showDescriptionField = null;
    this.editingDescription = {};
  }

  labelsList = [
    'Mobile',
    'Web',
    'Backend',
  ];

  stickies: any[] = [];
  stickiesList: any[] = [];
  stickyColors = [
    '#B8E6B8',
    '#FFE4B5',
    '#FFB6C1',
    '#E6E6FA',
    '#F0E68C',
    '#87CEEB',
    '#F5DEB3'
  ];

  currentFocusedSticky = -1;
  private savedSelections: { [key: number]: any } = {};

  addSticky() {

    this.CreateStickiesAPI()
    // const randomColor = this.stickyColors[Math.floor(Math.random() * this.stickyColors.length)];
    // this.stickies.push({
    //   content: '<div>Click to start typing...</div>',
    //   color: randomColor,
    //   isEditing: false,
    //   id: Date.now()
    // });
  }





  // saveSelection(stickyIndex: number) {
  //   const selection = window.getSelection();
  //   if (selection && selection.rangeCount > 0) {
  //     this.savedSelections[stickyIndex] = selection.getRangeAt(5).cloneRange();
  //   }
  // }

saveSelection(index: number): void {
  const selection = window.getSelection();
  if (selection && selection.rangeCount > 0) {
    this.savedSelections[index] = selection.getRangeAt(0);
  }
}
  private updateTimeout: any = null;

  updateStickyContent(index: number, event: any) {
    // Save new content
    this.stickies[index].content = event.target.innerText;

    // Save the selection if needed
    this.saveSelection(index);

    // Clear previous timer
    if (this.updateTimeout) {
      clearTimeout(this.updateTimeout);
    }

    // Start new 2-second timer
    this.updateTimeout = setTimeout(() => {
      // this.UpdateStickesAPI();
    }, 2000);
  }


  restoreSelection(stickyIndex: number) {
    const contentArea = document.getElementById(`sticky-content-${stickyIndex}`);
    if (contentArea && this.savedSelections[stickyIndex]) {
      contentArea.focus();
      const selection = window.getSelection();
      if (selection) {
        selection.removeAllRanges();
        selection.addRange(this.savedSelections[stickyIndex]);
      }
    }
  }

  formatText(command: string, stickyIndex: number) {
    const contentArea = document.getElementById(`sticky-content-${stickyIndex}`);
    if (contentArea) {
      this.isUserTyping[stickyIndex] = true;
      contentArea.focus();

      if (this.savedSelections[stickyIndex]) {
        const selection = window.getSelection();
        if (selection) {
          selection.removeAllRanges();
          selection.addRange(this.savedSelections[stickyIndex]);
        }
      }

      document.execCommand(command, false, undefined);

      this.stickylists[stickyIndex].text = contentArea.innerHTML;

      this.saveSelection(stickyIndex);
      
      setTimeout(() => {
        this.isUserTyping[stickyIndex] = false;
      }, 100);
    }
  }

  isFormatActive(command: string, stickyIndex: number): boolean {
    if (this.currentFocusedSticky !== stickyIndex) return false;

    try {
      return document.queryCommandState(command);
    } catch (e) {
      return false;
    }
  }

  // addEmoji(stickyIndex: number) {
  //   const emojis = ['😀', '😊', '👍', '❤️', '🎉', '💡', '🔥', '⭐', '🚀', '💯'];
  //   const randomEmoji = emojis[Math.floor(Math.random() * emojis.length)];

  //   const contentArea = document.getElementById(`sticky-content-${stickyIndex}`);
  //   if (contentArea) {
  //     contentArea.focus();

  //     if (this.savedSelections[stickyIndex]) {
  //       const selection = window.getSelection();
  //       if (selection) {
  //         selection.removeAllRanges();
  //         selection.addRange(this.savedSelections[stickyIndex]);
  //       }
  //     }

  //     document.execCommand('insertText', false, randomEmoji);

  //     this.stickies[stickyIndex].content = contentArea.innerHTML;

  //     this.saveSelection(stickyIndex);
  //   }
  // }

  // deleteSticky(index: number) {
  //   this.stickies.splice(index, 1);
  //   if (this.currentFocusedSticky === index) {
  //     this.currentFocusedSticky = -1;
  //   }
  //   delete this.savedSelections[index];
  // }

  addEmoji(event: any) {
    console.log('Selected emoji:', event.emoji.native);
    
    if (this.currentFocusedSticky !== null && this.currentFocusedSticky !== -1) {
      const stickyIndex = this.currentFocusedSticky;
      const contentArea = document.getElementById(`sticky-content-${stickyIndex}`) as HTMLElement;
      
      if (contentArea) {
        // Focus the content area
        contentArea.focus();
        
        // Get current selection or create one at the end
        const selection = window.getSelection();
        if (selection && selection.rangeCount > 0) {
          const range = selection.getRangeAt(0);
          range.deleteContents();
          const textNode = document.createTextNode(event.emoji.native);
          range.insertNode(textNode);
          range.setStartAfter(textNode);
          range.collapse(true);
          selection.removeAllRanges();
          selection.addRange(range);
        } else {
          // If no selection, append to the end
          contentArea.innerHTML += event.emoji.native;
        }
        
        // Update the sticky data
        this.stickylists[stickyIndex].text = contentArea.innerHTML;
        this.isUserTyping[stickyIndex] = true;
        
        // Update via API
        this.UpdateStickesAPI(this.stickylists[stickyIndex]);
      }
    }
    
    // Hide emoji picker after selection
    this.showEmojiPicker = false;
  }

  deleteTargetLink: any;
  linkType: string = '';

  deleteModalRef: any;

  deleteLink(link: any): void {
    this.deleteTargetLink = link;
    this.linkType = link.type;

    const modalElement = document.getElementById('deleteLinkConfirmModal');
    this.deleteModalRef = new bootstrap.Modal(modalElement);
    this.deleteModalRef.show();
  }

  confirmDeletSticky(): void {
    if (!this.deleteTargetLink) return;

    const { id, type } = this.deleteTargetLink;

    this.projectService.deleteSticky(this.homeId, id).subscribe({
      next: () => {
        this.stickylists = this.stickylists.filter(item => item.id !== id);
        this.projectService.openSnack(`Sticky deleted successfully`, 'Ok');

        this.deleteTargetLink = null;
        this.linkType = '';
        this.deleteModalRef?.hide();  // Close safely


      },
      error: (err) => {
        console.error('Error deleting sticky:', err);
        this.projectService.openSnack(`Error deleting sticky`, 'Ok');
        this.deleteModalRef?.hide();
      }
    });
  }
  confirmDeleteLink(): void {
    if (!this.deleteTargetLink) return;

    const { id, type } = this.deleteTargetLink;

    this.projectService.deleteLink(this.homeId, id).subscribe({
      next: () => {
        this.quickLinks = this.quickLinks.filter(item => item.id !== id);
        this.projectService.openSnack(`Quiklink deleted successfully`, 'Ok');

        this.deleteTargetLink = null;
        this.linkType = '';
        this.deleteModalRef?.hide();  // Close safely


      },
      error: (err) => {
        console.error('Error deleting sticky:', err);
        this.projectService.openSnack(`Error deleting sticky`, 'Ok');
        this.deleteModalRef?.hide();
      }
    });
  }
  handleDelete(): void {
    if (!this.deleteTargetLink) return;

    // Check which array the item exists in
    const isSticky = this.stickylists?.some(item => item.id === this.deleteTargetLink?.id);
    const isQuickLink = this.quickLinks?.some(item => item.id === this.deleteTargetLink?.id);

    if (isSticky) {
      this.confirmDeletSticky();
    } else if (isQuickLink) {
      this.confirmDeleteLink();
    } else {
      this.projectService.openSnack('Item not found for deletion', 'Ok');
    }
  }








  showAllItems = false;
  readonly itemsToShow = 4;

  toggleShowAll() {
    this.showAllItems = !this.showAllItems;
  }

  get visibleItems() {
    return this.showAllItems ? this.recentItems : this.recentItems.slice(0, this.itemsToShow);
  }

  get shouldShowToggle() {
    return this.recentItems.length > this.itemsToShow;
  }

  quickLinks: any = [];
  stickylists: any = [];
  newLinkUrl: string = '';
  newLinkTitle: string = '';
  activeMenu: number = -1;

  formatUrl(url: string): string {
    if (url && !url.startsWith('http://') && !url.startsWith('https://')) {
      return 'https://' + url;
    }
    return url;
  }

  openQuickLink(url: string) {
    window.open(this.formatUrl(url), '_blank');
  }

  // addQuickLink() {
  //   if (this.newLinkUrl) {
  //     this.quickLinks.push({
  //       url: this.newLinkUrl,
  //       title: this.newLinkTitle || this.newLinkUrl,
  //       createdAt: new Date()
  //     });
  //     this.newLinkUrl = '';
  //     this.newLinkTitle = '';

  //     const modalElement = document.getElementById('exampleModalCenter');
  //     if (modalElement) {
  //       modalElement.style.display = 'none';
  //       modalElement.classList.remove('show');
  //       document.body.classList.remove('modal-open');

  //       const backdrop = document.querySelector('.modal-backdrop');
  //       if (backdrop) {
  //         backdrop.remove();
  //       }
  //     }
  //   }
  // }


  editLink(index: number) {
    const link = this.quickLinks[index];
    this.newLinkUrl = link.url;
    this.newLinkTitle = link.title;
    this.quickLinks.splice(index, 1);
    $('#exampleModalCenter').modal('show');
    this.activeMenu = -1;
  }

  openInNewTab(url: string) {
    window.open(this.formatUrl(url), '_blank');
    this.activeMenu = -1;
  }

  copyLink(url: string) {
    navigator.clipboard.writeText(this.formatUrl(url)).then(() => {
      
    });
    this.activeMenu = -1;
  }

  // deleteLink(index: number) {
  //   this.quickLinks.splice(index, 1);
  //   this.activeMenu = -1;
  // }

  widgets: Widget[] = [
    { name: 'Quicklinks', enabled: true },
    { name: 'Recents', enabled: true },
    { name: 'Your stickies', enabled: true }
  ];

  getWidgetState(widgetName: string): boolean {
    const widget = this.widgets.find(w => w.name === widgetName);
    return widget ? widget.enabled : false;

  }
  totalUrls: number = 0;
  totalProjects: number = 0;
  //  getQuiklinks() {
  //     let businessId = localStorage.getItem("businessId");
  //      let type="QUICKLINKS"
  //   this.projectService.getQuickLinks(businessId,type).subscribe(
  //     (res: any) => {
  //       console.log(res.data)
  //       this.quikUrlList = res.data;
  //       this.totalUrls = this.quikUrlList.length;

  //     }
  //   )
  // }

  //    getSticikeys() {
  //     let businessId = localStorage.getItem("businessId");
  //      let type="STICKES"
  //   this.projectService.getQuickLinks(businessId,type).subscribe(
  //     (res: any) => {
  //       console.log(res.data)
  //       this.stickiesList = res.data
  //       this.sticky = this.sticky;
  //       this.id = this.id;

  //     }
  //   )
  // }
  projectAllList: any[] = [];
  allAssignees: { name: string; imageUrl?: string }[] = [];
  maxToShow = 2;
  getHomeProjects(project: boolean, workItem: boolean, pages: boolean) {
    let businessId = localStorage.getItem("businessId");
    this.projectService.getHomeProjects(businessId, project, workItem, pages).subscribe(
      (res: any) => {
        
        res.data.projectList?.forEach((project: any) => {
          project.type = 'PROJECT'
        })

        res.data.workItemList?.forEach((workItem: any) => {
          workItem.type = 'WORKITEM'
        })
        res.data.pages?.forEach((workItem: any) => {
          workItem.type = 'PAGE'
        })
        this.projectAllList = [
          ...(res.data.pageList || []),
          ...(res.data.projectList || []),
          ...(res.data.workItemList || [])
        ];


        const assigneeList: { name: string; imageUrl?: string }[] = [];

        this.projectAllList.forEach((item: any) => {
          const assignees = item.assignee;
          if (Array.isArray(assignees)) {
            assignees.forEach((a: any) => {
              if (a?.name) {
                assigneeList.push({
                  name: a.name,
                  imageUrl: undefined  // set if image available
                });
              }
            });
          }
        });
        this.allAssignees = assigneeList.filter(
          (user, index, self) => index === self.findIndex(u => u.name === user.name)
        );
      });

  }
  getData() {
    let businessId = localStorage.getItem("businessId");
      let staffId = localStorage.getItem(StorageKeys.STAFF_ID);
    this.projectService.getHomeData(businessId).subscribe(
      (res: any) => {
        console.log('res.data1::',res.data);
        this.projectList = res.data;
        this.quickLinks = res.data.quickLink.filter((link: any) => link.staffId === staffId);
          this.stickylists = res.data.stickies.filter((sticky: any) => sticky.staffId === staffId);
        // this.quickLinks = res.data.quickLink || [];
        // this.stickylists = res.data.stickies || [];

        this.homeId = res.data.id;
        this.id = this.id;

        setTimeout(() => {
          this.initializeStickyContents();
        }, 0);

      });
  }
  bDetails: any;
  businessName: any;
  projectName: any;
  businessId: any;
  response: any;
  widjets: any;
  url: any;
  logo: any;
  id: any;
  stickyId: any;
  displayTitle: any;
  createdDate: any;
  linkUrls: linkUrls[] = [];
  type: any;
  sticky: string = '';
  text: string = '';
  homeId: string = '';
  createdAt: string = '';
  userName:any;

  QuicklinkAPI() {
      let staffId = localStorage.getItem(StorageKeys.STAFF_ID);
    let bDetails = window.localStorage.getItem('bDetails') || ''
    if (bDetails) {
      this.bDetails = JSON.parse(bDetails)
      this.businessName = this.bDetails.name;
      this.businessId = this.bDetails?.id || '';

    }
    const today = new Date();
    const createdAt = `${String(today.getDate()).padStart(2, '0')}-${String(today.getMonth() + 1).padStart(2, '0')}-${today.getFullYear()}`;

    let payload = {
      
      logo: this.logo,
      url: this.url,
      displayTitle: this.displayTitle,
      createdAt: createdAt,
      homeId: this.homeId,
      staffId:staffId

    }


    this.projectService.createQuickLink(payload, this.homeId).subscribe((res: any) => {
      this.response = res.data;
      this.getData();
      console.log('response creation', this.response)

      // Clear the form fields after successful creation
      this.url = '';
      this.displayTitle = '';
      this.id = '';

      const modalElement = document.getElementById('exampleModalCenter');
      if (modalElement) {
        modalElement.style.display = 'none';
        modalElement.classList.remove('show');
        document.body.classList.remove('modal-open');

        const backdrop = document.querySelector('.modal-backdrop');
        if (backdrop) {
          backdrop.remove();
        }
      }

    })
  }
  UpdateQuicklinkAPI() {

  let staffId = localStorage.getItem(StorageKeys.STAFF_ID);
    const today = new Date();
    const createdAt = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    let payload = {
      url: this.url,
      displayTitle: this.displayTitle,
      id: this.id,
      createdAt: createdAt,
      homeId: this.homeId,
      staffId:staffId

    }

    this.projectService.createQuickLink(payload, this.homeId).subscribe((res: any) => {
      this.response = res.data;
      this.getData();
      console.log('response creation', this.response)

      // Clear the form fields after successful update
      this.url = '';
      this.displayTitle = '';
      this.id = '';

      const modalElement = document.getElementById('exampleModalCenter');
      if (modalElement) {
        modalElement.style.display = 'none';
        modalElement.classList.remove('show');
        document.body.classList.remove('modal-open');

        const backdrop = document.querySelector('.modal-backdrop');
        if (backdrop) {
          backdrop.remove();
        }
      }

    })

  }
  CreateStickiesAPI() {
     let staffId = localStorage.getItem(StorageKeys.STAFF_ID);
    const randomColor = this.stickyColors[Math.floor(Math.random() * this.stickyColors.length)];
    const today = new Date();
    const createdAt = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

    let payload = {
      text: this.text,
      color: randomColor,
      createdAt: createdAt,
      staffId:staffId
    }

    console.log('request creation', payload)

    this.projectService.CreateSticky(payload, this.homeId).subscribe((res: any) => {
      this.response = res.data;
      console.log('response creation', this.response)
      this.getData();


      const modalElement = document.getElementById('exampleModalCenter');
      if (modalElement) {
        modalElement.style.display = 'none';
        modalElement.classList.remove('show');
        document.body.classList.remove('modal-open');

        const backdrop = document.querySelector('.modal-backdrop');
        if (backdrop) {
          backdrop.remove();
        }
      }

    }
    )

  }
  status: boolean = true;
  WidgetsStatus(widgetName: string): void {
    let type = '';

    // Map widget name to payload type
    switch (widgetName) {
      case 'Quicklinks':
        type = 'QUICKLINK';
        break;
      case 'Recents':
        type = 'RECENTS';
        break;
      case 'Your stickies':
        type = 'STICKIES';
        break;
      default:
        console.warn('Unknown widget type');
        return;
    }
    const payload = {
      homeId: this.homeId,
      type: type,
      status: this.getWidgetState(widgetName),
    };

    this.projectService.WidgetUpdate(payload).subscribe((res: any) => {
      this.widjets = res.data;
      this.getData();
    });
  }


  debounceTimers: any[] = [];
  private isUserTyping: { [key: number]: boolean } = {};

  ngAfterViewInit() {
    setTimeout(() => {
      this.initializeStickyContents();
    }, 0);
  }

  private initializeStickyContents(): void {
    this.stickylists.forEach((sticky, index) => {
      const element = document.getElementById(`sticky-content-${index}`) as HTMLElement;
      if (element && sticky.text && !this.isUserTyping[index]) {
        element.innerHTML = sticky.text;
      }
    });
  }

  onStickyInput(event: Event, index: number): void {
    const contentArea = event.target as HTMLElement;
    const value = contentArea.innerHTML;
    
    this.isUserTyping[index] = true;
    
    // Update the sticky content
    if (this.stickylists[index]) {
      this.stickylists[index].text = value;
    }

    if (this.debounceTimers[index]) {
      clearTimeout(this.debounceTimers[index]);
    }

    this.debounceTimers[index] = setTimeout(() => {
      this.UpdateStickesAPI(this.stickylists[index]);
      // Mark typing as finished after API call
      this.isUserTyping[index] = false;
    }, 2000);
  }

  callStickyUpdateAPI(index: number): void {
    this.selectedSticky = this.stickiesList[index];
    console.log('Calling API for sticky:', this.selectedSticky);
    // this.UpdateStickesAPI();
  }


  onStickyFocus(index: number): void {
    this.currentFocusedSticky = index;
    this.isUserTyping[index] = true;
  }

  onStickyBlur(index: number): void {
    setTimeout(() => {
      this.isUserTyping[index] = false;
    }, 100);
  }

  // UpdateStickesAPI() {
  //   const randomColor = this.stickyColors[Math.floor(Math.random() * this.stickyColors.length)];
  //   const today = new Date();
  //   const createdAt = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
 
  //   let payload = {
  //     id: this.id,
  //     text: this.text,
  //     color: randomColor,
  //     createdAt: createdAt

  //   }

  //   this.projectService.CreateSticky(payload, this.homeId).subscribe((res: any) => {
  //     this.response = res.data;
  //     console.log('response creation', this.response)


  //     const modalElement = document.getElementById('exampleModalCenter');
  //     if (modalElement) {
  //       modalElement.style.display = 'none';
  //       modalElement.classList.remove('show');
  //       document.body.classList.remove('modal-open');

  //       const backdrop = document.querySelector('.modal-backdrop');
  //       if (backdrop) {
  //         backdrop.remove();
  //       }
  //     }

  //   }
  //   )

  // }



  get sortedProjectList() {
    return Array.isArray(this.projectAllList)
      ? this.projectAllList.slice().sort(
        (a, b) => new Date(b.updatedTimeStamp).getTime() - new Date(a.updatedTimeStamp).getTime()
      )
      : [];
  }

  getDisplayedAssignees(item: any): { name: string; imageUrl?: string }[] {
    const assignees = item.assignee || [];
    return assignees.slice(0, this.maxToShow).map((a: any) => ({
      name: a?.name || 'Unknown User',
      imageUrl: a?.imageUrl || undefined,
    }));
  }

  getExtraAssigneeCount(item: any): number {
    const assignees = item.assignee || [];
    return assignees.length - this.maxToShow;
  }
  getAssigneeNames(assignees: any[]): string {
    if (!assignees || assignees.length === 0) return 'No Assignee';
    return assignees.map(a => a.name).join(', ');
  }
  getInitial(name: string): string {
    return name?.charAt(0).toUpperCase() || '';
  }

  @ViewChildren('menuWrapper') menuWrappers!: QueryList<ElementRef>;

  toggleMenu(index: number) {
    this.activeMenu = this.activeMenu === index ? -1 : index;
  }

  @HostListener('document:click', ['$event.target'])
  onClickOutside(target: HTMLElement) {
    const clickedInside = this.menuWrappers.some(
      wrapper => wrapper.nativeElement.contains(target)
    );

    if (!clickedInside) {
      this.activeMenu = -1;
    }
  }
  currentDate: Date = new Date();
  getTimeIcon(): string {
    const hour = this.currentDate.getHours();
    if (hour >= 6 && hour < 12) {
      return 'fas fa-sun'; // Morning
    } else if (hour >= 12 && hour < 18) {
      return 'fas fa-cloud-sun'; // Afternoon
    } else if (hour >= 18 && hour < 21) {
      return 'fas fa-cloud-moon'; // Evening
    } else {
      return 'fas fa-moon'; // Night
    }
  }
  // selectIssue(item: any): void {
  //   if (!item.exist) return;
  //   this.matDialog.open(DetailWorkitemComponent, {
  //     width: '54%',
  //     height: '100%',
  //     panelClass: 'view-metal-dialog-container',
  //     data: { item, home: 'HOME' }
  //   });
  // }

  isProjectMember(project: any): boolean {
    
    const staffId = localStorage.getItem('staffId');
    const bool = project.members?.some((member: any) => member.id === staffId) || false;
    return bool;
  }

  goToWorkItem(res: any) {
    
    if (this.isProjectMember(res)) {
      this.router.navigate(['admin/work-management/work-item'], {
        queryParams: { projectId: res.id, }
      });
    } else {
      this.projectService.openSnack("Please join the project to see details", "Ok");
    }
  }

  projectId: any;
  projectData: any;
  detailWorkitem(item: any) {
    this.projectId = item.project.id;
    if (item) {
      const dialogRef =this.matDialog.open(DetailWorkitemComponent, {
        width: '45%',
        height: '100%',
        panelClass: 'custom-dialog',
        position: { top: '0', right: '0' },
        data: { item , projectData:{projectId : this.projectId} }
      });
      dialogRef.afterClosed().subscribe(res => {

        
      });
    } else {
      console.warn('Tried to open dialog with undefined item');
    }
    
    
  }

  clickFunction(item:any){

    if (item.type === 'PROJECT') {
      this.goToWorkItem(item);
    } else if (item.type === 'WORKITEM') {
      this.detailWorkitem(item);
    }else{
      this.navigateToPage(item);
    }
  }

  UpdateStickesAPI(sticky:any) {
     let staffId = localStorage.getItem(StorageKeys.STAFF_ID);
    const randomColor = this.stickyColors[Math.floor(Math.random() * this.stickyColors.length)];
    const today = new Date();
    const createdAt = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

    let payload = {
      id: sticky.id,
      text: sticky.text,
      color: sticky.color,
      createdAt: sticky.createdAt,
      staffId:staffId

    }

    this.projectService.CreateSticky(payload, this.homeId).subscribe((res: any) => {
      this.response = res.data;
      console.log('response creation', this.response)


      const modalElement = document.getElementById('exampleModalCenter');
      if (modalElement) {
        modalElement.style.display = 'none';
        modalElement.classList.remove('show');
        document.body.classList.remove('modal-open');

        const backdrop = document.querySelector('.modal-backdrop');
        if (backdrop) {
          backdrop.remove();
        }
      }

    }
    )

  }


  onStickyKeyDown(event: KeyboardEvent, sticky: any): void {
  if (event.key === 'Enter' && event.ctrlKey) {
    event.preventDefault();
    
    const target = event.target as HTMLElement;
    const updatedText = target.innerHTML.trim();
    sticky.text = updatedText;
     
    console.info('sticky event::',event);
    console.info('sticky sticky::',sticky);
    this.UpdateStickesAPI(sticky);
  }
}



showEmojiPicker: boolean = false;
selectedEmoji: string = '';
toggleEmojiPicker(stickyIndex: number) {
    // Set the focused sticky to the one where emoji button was clicked
    this.currentFocusedSticky = stickyIndex;
    
    // Toggle the emoji picker
    this.showEmojiPicker = !this.showEmojiPicker;
    
    // If opening the picker, focus the content area to maintain cursor position
    if (this.showEmojiPicker) {
      setTimeout(() => {
        const contentArea = document.getElementById(`sticky-content-${stickyIndex}`);
        if (contentArea) {
          contentArea.focus();
        }
      }, 0);
    }
  }





@HostListener('document:click', ['$event'])
onDocumentClick(event: MouseEvent) {
  const target = event.target as HTMLElement;
  if (!target.closest('.emoji-picker-container') && !target.closest('.fa-smile') && !target.closest('emoji-mart')) {
    this.showEmojiPicker = false;
  }
}



navigateToPage(data:any){
  this.router.navigate(['admin/work-management/pages/view-page'], {
    queryParams: { pageId: data?.id }
  });
}
}



