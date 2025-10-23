import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { DraftPmsComponent } from './draft-pms/draft-pms.component';

const routes: Routes = [
  {
      path: '',
      component: DraftPmsComponent
    }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class DraftPmsRoutingModule { }
