import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ListCyclesComponent } from './list-cycles/list-cycles.component';
import { CycleWorkitemsComponent } from './cycle-workitems/cycle-workitems.component';

const routes: Routes = [
  {
    path: '',
    component: ListCyclesComponent
  },
  {
    path: 'cycle-workitems',
    component: CycleWorkitemsComponent
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class CyclesPmsRoutingModule { }
