import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { EpicRoutingModule } from './epic-routing.module';
import { EpicListingComponent } from './epic-listing/epic-listing.component';

// Angular Material & CDK modules used by the template
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { DragDropModule } from '@angular/cdk/drag-drop';


@NgModule({
  declarations: [
    EpicListingComponent
  ],
  imports: [
    CommonModule,
    FormsModule,
    MatTableModule,
    MatTooltipModule,
    MatMenuModule,
    MatIconModule,
    MatButtonModule,
    DragDropModule,
    EpicRoutingModule
  ]
  ,
  exports: [
    EpicListingComponent
  ]
})
export class EpicModule { }
