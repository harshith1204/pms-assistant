import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogModule } from '@angular/material/dialog';
import { FormsModule } from '@angular/forms';

// import { ListProjectviewComponent } from './list-projectview/list-projectview.component';
import { CreateProjectviewComponent } from './create-projectview/create-projectview.component';
import { ProjectViewsPmsRoutingModule } from './project-views-pms-routing.module';

@NgModule({
  declarations: [
    // ListProjectviewComponent,
    CreateProjectviewComponent
  ],
  imports: [
    CommonModule,
    FormsModule,
    ProjectViewsPmsRoutingModule,
    MatDialogModule
  ],
})
export class ProjectViewsPmsModule { }

