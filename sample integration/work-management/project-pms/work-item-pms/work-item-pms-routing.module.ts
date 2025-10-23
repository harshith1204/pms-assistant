import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ListWorkitemComponent } from './list-workitem/list-workitem.component';

const routes: Routes = [
  {
    path:'',
    component: ListWorkitemComponent
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class WorkItemPmsRoutingModule { }
