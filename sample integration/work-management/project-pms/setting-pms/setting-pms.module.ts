import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { SettingPmsRoutingModule } from './setting-pms-routing.module';
import { SettingPmsComponent } from './setting-pms/setting-pms.component';
import { ConstantMaterialModule } from 'src/app/material_module/constant-material.module';

// Material Imports
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatOptionModule } from '@angular/material/core';
import { MatIconModule } from '@angular/material/icon';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { AddEstimationComponent } from './add-estimation/add-estimation.component';
import { PickerModule } from '@ctrl/ngx-emoji-mart';

@NgModule({
  declarations: [
    SettingPmsComponent,
    AddEstimationComponent
  ],
  imports: [
    CommonModule,
    FormsModule,
    SettingPmsRoutingModule,
    ConstantMaterialModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatOptionModule,
    MatIconModule,
    MatSlideToggleModule,
    MatTableModule,
    MatButtonModule,
    PickerModule,
  ]
})
export class SettingPmsModule { }
