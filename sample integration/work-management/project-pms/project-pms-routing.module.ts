import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ProjectPmsComponent } from './project-pms/project-pms.component';

const routes: Routes = [
  {
    path: '',
    component: ProjectPmsComponent
  },
  {
    path: 'settings',
    loadChildren: () =>
      import('./setting-pms/setting-pms.module').then(m => m.SettingPmsModule)
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class ProjectPmsRoutingModule { }
