import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { FeatureEpicRoutingModule } from './feature-epic-routing.module';
import { ListFeatureComponent } from './list-feature/list-feature.component';
import { CreateFeatureComponent } from './create-feature/create-feature.component';


@NgModule({
  declarations: [
    ListFeatureComponent,
    CreateFeatureComponent
  ],
  imports: [
    CommonModule,
    FeatureEpicRoutingModule
  ]
})
export class FeatureEpicModule { }
