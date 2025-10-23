import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ListModulesComponent } from './list-modules/list-modules.component';
import { ModuleWorkitemsComponent } from './module-workitems/module-workitems.component';

const routes: Routes = [
  {
    path: '',
    component: ListModulesComponent
  },
  {
    path: 'module-workitem',
    component: ModuleWorkitemsComponent
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class ModulesPmsRoutingModule { }
