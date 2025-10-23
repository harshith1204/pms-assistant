import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { DraftPmsRoutingModule } from './draft-pms-routing.module';
import { DraftPmsComponent } from './draft-pms/draft-pms.component';


@NgModule({
  declarations: [
    DraftPmsComponent
  ],
  imports: [
    CommonModule,
    DraftPmsRoutingModule
  ]
})
export class DraftPmsModule { }
