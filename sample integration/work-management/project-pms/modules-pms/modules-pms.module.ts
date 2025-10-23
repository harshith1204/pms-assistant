import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatNativeDateModule } from '@angular/material/core';

import { ModulesPmsRoutingModule } from './modules-pms-routing.module';
// import { ListModulesComponent } from './list-modules/list-modules.component';
import { CreateModuleComponent } from './create-module/create-module.component';
import { MatMenuModule } from '@angular/material/menu';
import { CrmCommonModule } from '../../../crm/crm-common/crm-common.module';

@NgModule({
  declarations: [
    // ListModulesComponent,
    CreateModuleComponent
  ],
  imports: [
    CommonModule,
    ReactiveFormsModule,
    FormsModule,
    MatDatepickerModule,
    MatFormFieldModule,
    MatInputModule,
    MatNativeDateModule,
    ModulesPmsRoutingModule,
    MatMenuModule,
    CrmCommonModule
  ]
})
export class ModulesPmsModule { }
