import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatIconModule } from '@angular/material/icon';
import { FormsModule } from '@angular/forms';
import { MatRadioModule } from '@angular/material/radio';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { ProjectPmsRoutingModule } from './project-pms-routing.module';
import { ProjectPmsComponent } from './project-pms/project-pms.component';
import { CreateProjectComponent } from './create-project/create-project.component';
import { FilterPmsComponent } from './filter-pms/filter-pms.component';
import { DisplayPmsComponent } from './display-pms/display-pms.component';
import { PopupPmsComponent } from './popup-pms/popup-pms.component';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatButtonModule } from '@angular/material/button';
import { CrmCommonModule } from '../../crm/crm-common/crm-common.module';
import { PickerModule } from '@ctrl/ngx-emoji-mart';




@NgModule({
  declarations: [
    ProjectPmsComponent,
    FilterPmsComponent,
    DisplayPmsComponent,
    PopupPmsComponent,
  ],
  imports: [
    CommonModule,
    ProjectPmsRoutingModule,
    CreateProjectComponent,
    MatExpansionModule,
    MatCheckboxModule,
    MatIconModule,
    FormsModule,
    MatRadioModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatFormFieldModule,
    MatInputModule,
    MatTooltipModule,
    MatSelectModule,
    MatButtonModule,
    CrmCommonModule,
    FormsModule,
    PickerModule,

  ]
})
export class ProjectPmsModule { }
