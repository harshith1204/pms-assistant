import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { SettingPmsComponent } from './setting-pms/setting-pms.component';

const routes: Routes = [
  {
    path: '',
    component: SettingPmsComponent
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class SettingPmsRoutingModule { }
