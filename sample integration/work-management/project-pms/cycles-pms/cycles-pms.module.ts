import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatNativeDateModule } from '@angular/material/core';

import { CyclesPmsRoutingModule } from './cycles-pms-routing.module';
// import { ListCyclesComponent } from './list-cycles/list-cycles.component';
import { CreateCycleComponent } from './create-cycle/create-cycle.component';
import { CrmCommonModule } from '../../../crm/crm-common/crm-common.module';


@NgModule({
  declarations: [
    // ListCyclesComponent,
    CreateCycleComponent,
  ],
  imports: [
    CommonModule,
    ReactiveFormsModule,
    CyclesPmsRoutingModule,
    MatDatepickerModule,
    MatFormFieldModule,
    MatInputModule,
    MatNativeDateModule,
    FormsModule,
    CrmCommonModule
  ]
})
export class CyclesPmsModule { }
