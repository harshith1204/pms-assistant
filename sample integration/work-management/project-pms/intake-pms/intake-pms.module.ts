import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ConstantMaterialModule } from 'src/app/material_module/constant-material.module';
import { IntakePmsRoutingModule } from './intake-pms-routing.module';
import { IntakePmsComponent } from './intake-pms/intake-pms.component';
import { QuillModule } from 'ngx-quill';
import { FormsModule } from '@angular/forms';


@NgModule({
  declarations: [
    IntakePmsComponent
  ],
  imports: [
    CommonModule,
    IntakePmsRoutingModule,
    ConstantMaterialModule,
    QuillModule.forRoot(),
    FormsModule
  ]
})
export class IntakePmsModule { }
