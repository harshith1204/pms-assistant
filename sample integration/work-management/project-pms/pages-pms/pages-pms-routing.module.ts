import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ListPagesComponent } from './list-pages/list-pages.component';
import { ViewPageComponent } from './view-page/view-page.component';
import { CreatePagesComponent } from './create-pages/create-pages.component';

const routes: Routes = [
  {
    path: '',
    component: ListPagesComponent
  },
  {
    path: 'view-page',
    component: ViewPageComponent
  },
  {
    path: 'create-pages',
    component: CreatePagesComponent
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class PagesPmsRoutingModule { }
