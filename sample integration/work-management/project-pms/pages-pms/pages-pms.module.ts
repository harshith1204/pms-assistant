import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';

import { PagesPmsRoutingModule } from './pages-pms-routing.module';
// import { ListPagesComponent } from './list-pages/list-pages.component';
import { CreatePagesComponent } from './create-pages/create-pages.component';
import { CreatePagesTemplateComponent } from './create-pages/create-pages-template.component';
import { ConstantMaterialModule } from 'src/app/material_module/constant-material.module';
import { ViewPageComponent } from './view-page/view-page.component';


@NgModule({
  declarations: [
    // ListPagesComponent,
    CreatePagesComponent,
    CreatePagesTemplateComponent,
    ViewPageComponent
  ],
  imports: [
    CommonModule,
    FormsModule,
    HttpClientModule,
    PagesPmsRoutingModule,
    ConstantMaterialModule
  ]
})
export class PagesPmsModule { }
