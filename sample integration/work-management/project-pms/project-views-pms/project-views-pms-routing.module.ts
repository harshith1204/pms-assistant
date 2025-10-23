import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ListProjectviewComponent } from './list-projectview/list-projectview.component';

const routes: Routes = [
  {
    path: '',
    component: ListProjectviewComponent
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class ProjectViewsPmsRoutingModule { }
