import { Component, HostListener } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { CreateWorkitemComponent } from '../../work-item-pms/create-workitem/create-workitem.component';
import { ActivatedRoute } from '@angular/router';

@Component({
  selector: 'app-intake-pms',
  templateUrl: './intake-pms.component.html',
  styleUrls: ['./intake-pms.component.scss']
})
export class IntakePmsComponent {
  workItems = [
    {
      id: 'AVK-2',
      description: 'uhu',
      date: 'Jun 26, 2025'
    },
    {
      id: 'AVK-1',
      description: 'asdas',
      date: 'Jun 26, 2025'
    }
  ];

  constructor(private matDialog: MatDialog, private route: ActivatedRoute) {}

  ngOnInit() {
    this.route.queryParams.subscribe(params => {
      this.projectId = params['projectId'];
      
    });
  }

  screenWidth: any;
  projectId: any;
  response: any;
  @HostListener('window:resize', ['$event'])
  getScreenSize(event?: any) {
    this.screenWidth = window.innerWidth;
  }

  activeTab: string = 'Open';
  tabs: string[] = ['Open', 'Closed'];

  switchTab(tab: string): void {
    this.activeTab = tab;
  }

  createTempWorkItem(): void {
    const dialogConfig = {
      width: this.screenWidth > 992 ? '50%' : '55%',
      height: '66vh',
      maxWidth: '100vw',
      position: { top: '10vh' },
      data: { projectId: this.projectId, pending: 'PENDING' }
    };

    const dialog = this.matDialog.open(CreateWorkitemComponent, dialogConfig);
  }

  selectedWorkItem: any = null;
  editorContent: string = '';
  editorConfig = {
    toolbar: [
      ['bold', 'italic', 'underline'],
      ['link'],
      [{ 'list': 'ordered'}, { 'list': 'bullet' }],
      ['clean']
    ]
  };

  selectWorkItem(item: any): void {
    this.selectedWorkItem = item;
  }

  submitComment() {
    if (this.editorContent.trim()) {
      
      this.editorContent = ''; // Clear the editor
    }
  }

  acceptWorkItem(): void {
    if (this.selectedWorkItem) {
      // Handle accept logic
      
    }
  }

  declineWorkItem(): void {
    if (this.selectedWorkItem) {
      // Handle decline logic
      
    }
  }
}
