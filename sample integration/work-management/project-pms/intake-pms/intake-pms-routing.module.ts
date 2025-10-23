import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { IntakePmsComponent } from './intake-pms/intake-pms.component';

const routes: Routes = [
  {
    path: '',
    component: IntakePmsComponent
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class IntakePmsRoutingModule { }
