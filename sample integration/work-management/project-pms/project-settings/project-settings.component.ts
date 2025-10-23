import { Component, Inject, OnInit, Optional } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { WorkManagementService } from '../../work-management.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-project-settings',
  templateUrl: './project-settings.component.html',
  styleUrls: ['./project-settings.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    MatIconModule,
    MatButtonModule,
    MatSlideToggleModule
  ]
})
export class ProjectSettingsComponent implements OnInit {

  constructor(
    private dialogRef: MatDialogRef<ProjectSettingsComponent>,
    private projectService:WorkManagementService,
        private router : Router,
    @Optional() @Inject(MAT_DIALOG_DATA) public data: any,
  ) {}

  ngOnInit(): void {
   this.projectResponse = this.data;
  }

isTrackingEnabled:boolean=true;
isIntakeEnabled:boolean=true;
isPageEnabled:boolean=true;
isViewEnabled:boolean=true;
isModuleEnabled:boolean=true;
isFeatureEnabled:boolean=true;
projectResponse:any;


updateValues(){

}
  onClose(): void {
    this.dialogRef.close();
  }
  
  openProject(): void {
    this.dialogRef.close('open');
    this.goToWorkItem();

  }
  goToWorkItem(){
    this.router.navigate(['admin/work-management/work-item'],{
   queryParams: { projectId:this.projectResponse.id,}
});
  
  }


  onCheckboxChange(event: Event, feature: any) {
  const inputElement = event.target as HTMLInputElement;
  const isChecked = inputElement.checked;
  this.updateFeature(feature, isChecked);
}

    updateFeature(feature:any,isActive:boolean) {
    this.projectService.updateProjectFeature(this.projectResponse.id,isActive,feature).subscribe(
      (res: any) => {
        this.projectService.openSnack("status updated successfully", "Ok"); 
      }
    )
  }

}
