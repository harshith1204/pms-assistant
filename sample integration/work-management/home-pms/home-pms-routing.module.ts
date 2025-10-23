import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { HomePmsComponent } from './home-pms/home-pms.component';

const routes: Routes = [
  {
    path: '',
    component: HomePmsComponent
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class HomePMSRoutingModule { }
