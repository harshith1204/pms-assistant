import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { HomePMSRoutingModule } from './home-pms-routing.module';
import { HomePmsComponent } from './home-pms/home-pms.component';
import { ConstantMaterialModule } from 'src/app/material_module/constant-material.module';
import { PickerModule } from '@ctrl/ngx-emoji-mart';


@NgModule({
  declarations: [
    HomePmsComponent
  ],
  imports: [
    CommonModule,
    HomePMSRoutingModule,
    ConstantMaterialModule,
    PickerModule
  ]
})
export class HomePMSModule { }
