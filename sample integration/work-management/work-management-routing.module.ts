import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { CreatePagesComponent } from './project-pms/pages-pms/create-pages/create-pages.component';
import { ModulesPmsModule } from './project-pms/modules-pms/modules-pms.module';
import { ViewPageComponent } from './project-pms/pages-pms/view-page/view-page.component';

const routes: Routes = [
  {
    path: 'home',
    loadChildren: () =>
      import('./home-pms/home-pms.module').then(m => m.HomePMSModule)
  },
  {
    path: 'inbox',
    loadChildren: () =>
      import('./inbox-pms/inbox-pms.module').then(m => m.InboxPmsModule)
  },
  {
    path: 'projects',
    loadChildren: () =>
      import('./project-pms/project-pms.module').then(m => m.ProjectPmsModule)
  },
  {
    path: 'views',
    loadChildren: () =>
      import('./views-pms/views-pms.module').then(m => m.ViewsPmsModule)
  },
  {
    path: 'analytics',
    loadChildren: () =>
      import('./analytics-pms/analytics-pms.module').then(m => m.AnalyticsPmsModule)
  },
  {
    path: 'drafts',
    loadChildren: () =>
      import('./draft-pms/draft-pms.module').then(m => m.DraftPmsModule)
  },
  {
    path: 'your-work',
    loadChildren: () =>
      import('./your-work-pms/your-work-pms.module').then(m => m.YourWorkPmsModule)
  },
  {
    path: 'archives',
    loadChildren: () =>
      import('./archives-pms/archives-pms.module').then(m => m.ArchivesPmsModule)
  },
  {
    path: 'settings-pms',
    loadChildren: () =>
      import('./project-pms/setting-pms/setting-pms.module').then(m => m.SettingPmsModule)
  },
  {
    path: 'pages',
    loadChildren: () =>
      import('./project-pms/pages-pms/pages-pms.module').then(m => m.PagesPmsModule)
  },
  {
    path: 'projectViews',
    loadChildren: () =>
      import('./project-pms/project-views-pms/project-views-pms.module').then(m => m.ProjectViewsPmsModule)
  },
  {
    path: 'intake',
    loadChildren: () =>
      import('./project-pms/intake-pms/intake-pms.module').then(m => m.IntakePmsModule)
  },
  {
    path: 'modules',
    loadChildren: () =>
      import('./project-pms/modules-pms/modules-pms.module').then(m => m.ModulesPmsModule)
  },
  {
    path: 'cycles',
    loadChildren: () =>
      import('./project-pms/cycles-pms/cycles-pms.module').then(m => m.CyclesPmsModule)
  },
  {
    path: 'create-page',
    component: CreatePagesComponent
  },
   {
    path: 'view-page',
    component: CreatePagesComponent
  },
  {
    path: 'work-item',
    loadChildren: () =>
      import('./project-pms/work-item-pms/work-item-pms.module').then(m => m.WorkItemPmsModule)
  }

];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class WorkManagementRoutingModule { }
