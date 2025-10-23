import { Component, Inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialog, MatDialogRef } from '@angular/material/dialog';
import { WorkManagementService } from '../../../work-management.service';
import { FilterPmsComponent } from '../../filter-pms/filter-pms.component';
import { DisplayPmsComponent } from '../../display-pms/display-pms.component';

@Component({
  selector: 'app-create-projectview',
  templateUrl: './create-projectview.component.html',
  styleUrls: ['./create-projectview.component.scss']
})
export class CreateProjectviewComponent {
  title: string = '';
  description: string = '';
  isEditMode: boolean = false;
  viewId: any = null;

  filters: { [key: string]: any[] } = {};

  filterGroups: { key: string, value: any[] }[] = [];
  filtersPayload: any;

  constructor(
    private dialogRef: MatDialogRef<CreateProjectviewComponent>,
    @Inject(MAT_DIALOG_DATA) public data: any,
    private matDialog: MatDialog,
    private projectService: WorkManagementService
  ) {}

  ngOnInit() {
    if (this.data?.edit && this.data?.view) {
      this.isEditMode = true;
      this.loadViewData();
    }
    this.updateFilterGroups();
  }

  onCancel() {
    this.dialogRef.close();
  }

  loadViewData() {
    const viewData = this.data.view;
    this.viewId = viewData.view?.id || viewData.id;
    this.title = viewData.view?.title || viewData.title || '';
    this.description = viewData.view?.description || viewData.description || '';
    
    if (viewData.appliedFilter) {
      const filterPayload = viewData.appliedFilter;
      this.filtersPayload = filterPayload;
      this.updateFiltersFromPayload(filterPayload);
    }
  }

 createView() {
  const businessId = localStorage.getItem('businessId');
  const projectId = this.data?.data?.projectId;
  const staffId = window.localStorage.getItem('staffId');
  const staffName = window.localStorage.getItem('staffName')

  // Construct the full payload
  const payload = {
    ...this.filtersPayload, 
    title: this.title.trim(),
    description: this.description.trim(),
    business: { id: businessId,name:'' },
    project: { id: projectId ,name:''}
  };

  // Add ID if we are editing (similar to create-module component)
  if (this.isEditMode && this.viewId) {
    payload.id = this.viewId;
  }

  this.projectService.createView(payload).subscribe(
    (response: any) => {
      const message = this.isEditMode ? "Project view updated successfully" : "Project view created successfully";
      this.projectService.openSnack(message, "Ok");
      this.dialogRef.close(response);
    },
    (error: any) => {
      const errorMessage = this.isEditMode ? 'Error updating project view:' : 'Error creating project view:';
      console.error(errorMessage, error);
    }
  );
}


  openFilterMenu() {
    const dialogRef = this.matDialog.open(FilterPmsComponent, {
      width: '20%',
      height: '67%',
      data: { screen: 'WORK_ITEM', projectData: this.data.data ,selectedFilters: this.filters },
      position: { top: '21vh', right: '60vh' },
    });

    dialogRef.componentInstance.dataChanged.subscribe((cleanedPayload: any) => {
      this.updateFiltersFromPayload(cleanedPayload);
    this.filtersPayload = cleanedPayload;
    
    
    });
  }

  openDisplay() {
    this.matDialog.open(DisplayPmsComponent, {
      width: '25%',
      height: '67%',
      position: { top: '21vh', right: '44vh' },
    });
  }

  updateFiltersFromPayload(payload: any) {
  
    this.filters = {}; // Clear previous selections

    if (payload.state) {
      this.filters['State'] = payload.state.map((s: any) => s.name);
    }

    if (payload.priority) {
      this.filters['Priority'] = payload.priority;
    }

    if (payload.assignee) {
      this.filters['Assignees'] = payload.assignee.map((s: any) => ({
        name: s.name,
        avatar: this.getInitials(s.name)
      }));
    }

    if (payload.label) {
      this.filters['Labels'] = payload.label.map((s: any) => s.name);
    }

    if (payload.modules) {
      this.filters['Modules'] = payload.modules.map((s: any) => s.name);
    }

    if (payload.cycle) {
      this.filters['Cycles'] = payload.cycle.map((s: any) => s.name);
    }

    if (payload.lead) {
      this.filters['Lead'] = payload.lead.map((s: any) => s.name);
    }

    if (payload.createbBy) {
      this.filters['Created By'] = payload.createbBy.map((s: any) => s.name);
    }

    this.updateFilterGroups();
  }

  updateFilterGroups() {
    this.filterGroups = Object.entries(this.filters)
      .filter(([_, value]) => Array.isArray(value) && value.length > 0)
      .map(([key, value]) => ({ key, value }));
  }

  removeFilter(key: string, item: any): void {
    const index = this.filters[key].findIndex((x: any) =>
      typeof x === 'object' ? x.name === item.name : x === item
    );
    if (index > -1) {
      this.filters[key].splice(index, 1);
    }
    this.updateFilterGroups();
  }

  clearAll(): void {
    for (let key in this.filters) {
      this.filters[key] = [];
    }
    this.updateFilterGroups();
  }

getInitials(name: string): string {
  return name?.trim().charAt(0).toUpperCase() || '';
}

}
