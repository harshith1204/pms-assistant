import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { WorkItemPmsRoutingModule } from './work-item-pms-routing.module';
import { ListWorkitemComponent } from './list-workitem/list-workitem.component';
import { MatTableModule } from '@angular/material/table';
import { CreateWorkitemComponent } from './create-workitem/create-workitem.component';
import { DetailWorkitemComponent } from './detail-workitem/detail-workitem.component';
import { WorkItemTemplatesComponent } from './work-item-templates/work-item-templates.component';
import { QuillModule } from 'ngx-quill';
import { FormsModule } from '@angular/forms';
import { MatNativeDateModule } from '@angular/material/core';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { DragDropModule } from '@angular/cdk/drag-drop';
import { ListCyclesComponent } from '../cycles-pms/list-cycles/list-cycles.component';
import { ListModulesComponent } from '../modules-pms/list-modules/list-modules.component';
import { ListPagesComponent } from '../pages-pms/list-pages/list-pages.component';
import { ListProjectviewComponent } from '../project-views-pms/list-projectview/list-projectview.component';
import { ModuleWorkitemsComponent } from '../modules-pms/module-workitems/module-workitems.component';
import { MatMenuModule } from '@angular/material/menu';
import { CycleWorkitemsComponent } from '../cycles-pms/cycle-workitems/cycle-workitems.component';
import { CrmCommonModule } from '../../../crm/crm-common/crm-common.module';
import { MatTooltip, MatTooltipModule } from '@angular/material/tooltip';
import { EpicModule } from '../epic/epic.module';
import { MatSelectModule } from '@angular/material/select';
import { MatOptionModule } from '@angular/material/core';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';



@NgModule({
  declarations: [
    ListWorkitemComponent,
    CreateWorkitemComponent,
    DetailWorkitemComponent,
    WorkItemTemplatesComponent,
    ListCyclesComponent,
    ListModulesComponent,
    ListPagesComponent,
    ListProjectviewComponent,
    ModuleWorkitemsComponent,
  CycleWorkitemsComponent




  ],
  imports: [
    CommonModule,
    MatIconModule,
    MatTableModule,
    MatTooltipModule,
    EpicModule,
    WorkItemPmsRoutingModule,
    MatSelectModule,
    MatOptionModule,
     MatSlideToggleModule,
    QuillModule.forRoot({
      modules: {
        syntax: false,
        toolbar: false
      }
    }),
    FormsModule,
     MatDatepickerModule,
    MatFormFieldModule,
    MatInputModule,
    MatNativeDateModule,
    DragDropModule,
    MatMenuModule,
    CrmCommonModule
  ]
})
export class WorkItemPmsModule { }
