import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { integer } from 'aws-sdk/clients/cloudfront';
import { bool } from 'aws-sdk/clients/signer';
import { StorageKeys } from 'src/app/shared-module-files/simpo.constant';
import { environment } from 'src/environments/environment';

@Injectable({
  providedIn: 'root'
})
export class WorkManagementService {

  constructor(
    private http: HttpClient,
    private snackbar: MatSnackBar,
  ) { }

  openSnack(message: any, action: any) {
    this.snackbar.open(message, action, { duration: 1500 });
  }

  generateWorkItemWithAI(payload: { prompt: string; template: { title: string; content: string } }) {
    const url = `${environment.aiTemplateServiceUrl}generate-work-item`;
    return this.http.post(url, payload);
  }

  createProject(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project`, data
    )
  }
  createQuickLink(response: any, homeId: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/home/${homeId}/quick-links`, response
    )
  }
  CreateSticky(response: any, homeId: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/home/${homeId}/stickies`, response
    )
  }
  deleteSticky(homeId: any, stickyId: any) {
    return this.http.delete(
      environment.baseProjectUrl + `project/home/${homeId}/stickies/${stickyId}/delete`
    )
  }
  deleteLink(homeId: any, linkId: any) {
    return this.http.delete(
      environment.baseProjectUrl + `project/home/${homeId}/quick-links/${linkId}/delete`
    )
  }

  getStaff(bId: any) {
    return this.http.get(
      environment.baseUrl + `staff/staff/list/${bId}?page=${0}&size=${1000}`,
    )
  }

  getProjectCycles(bId: any, pId): any {
    return this.http.get(
      environment.baseProjectUrl + `project/cycle/get-all?businessId=${bId}&projectId=${pId}`,
    )
  }


  getProjectModules(data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/module`, data
    )
  }

  getAllProjects(data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project`, data
    )
  }
  getAllProjectsbyMember(data: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/memberId?businessId=${data.businessId}&memberId=${data.memberId}`,
    )
  }
  markAsFavourite(pId: any, isFavourite?: boolean, isArchived?: boolean) {
    let url = `${environment.baseProjectUrl}project/status-project?id=${pId}`;

    if (isFavourite !== undefined) {
      url += `&isFavourite=${isFavourite}`;
    }

    if (isArchived !== undefined) {
      url += `&isArchived=${isArchived}`;
    }

    return this.http.put(url, '');
  }
  markModuleFavourite(moduleId: any, isFavourite?: boolean, isArchived?: boolean) {
    let url = `${environment.baseProjectUrl}project/module/${moduleId}/favourite?isFav=${isFavourite}`;

    if (isFavourite !== undefined) {
      url += `&isFavourite=${isFavourite}`;
    }

    if (isArchived !== undefined) {
      url += `&isArchived=${isArchived}`;
    }

    return this.http.put(url, '');
  }
  markCycleFavourite(cycle: any, isFavourite?: boolean, isArchived?: boolean) {
    let url = `${environment.baseProjectUrl}project/cycle/${cycle}/favourite?isFav=${isFavourite}`;

    if (isFavourite !== undefined) {
      url += `&isFavourite=${isFavourite}`;
    }

    if (isArchived !== undefined) {
      url += `&isArchived=${isArchived}`;
    }

    return this.http.put(url, '');
  }
  markViewFavourite(view: any, isFavourite?: boolean, isArchived?: boolean) {
    let url = `${environment.baseProjectUrl}project/view/${view}/favourite?isFav=${isFavourite}`;


    if (isArchived !== undefined) {
      url += `&isArchived=${isArchived}`;
    }

    return this.http.put(url, '');
  }




  getQuickLinks(bId: any, type: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/get-all/quick-links?businessId=${bId}&type=${type}`,
    )
  }
  getworkItem(workItemId: any,) {
    return this.http.get(
      environment.baseProjectUrl + `project/workItem/user?workItemId=${workItemId}`,
    )
  }
  getHomeProjects(bId: any, project: boolean, workItem: boolean, pages?: boolean) {
    return this.http.get(
      environment.baseProjectUrl + `project/get-all-data?businessId=${bId}&project=${project}&workItem=${workItem}&pages=${pages}`,
    )
  }
  getHomeData(businessId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/home/${businessId}`,
    )
  }
  getAllFav(businessId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/${businessId}/list-fav`,
    )
  }
  WidgetUpdate(data: any) {

    return this.http.put(
      environment.baseProjectUrl + `project/home/widgets-update`, data
    )
  }


  updateProjectFeature(pId: any, isActive: boolean, feature: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/status?id=${pId}&isActive=${isActive}&feature=${feature}`, ''
    )
  }


  getProjectSettingsData(pId: any, bId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/setting?projectId=${pId}&businessId=${bId}`,
    )
  }


  createWorkItem(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/work-item`, data
    )
  }


  inboxComments(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/work-items/comment`, data
    )
  }

  getAllWorkItemsByView(data: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/view/id?viewId=${data}`,
    )
  }
  getAllWorkItems(data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/workItem`, data
    )
  }

  updateProject(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project`, data
    )
  }
  deleteProject(projectId: any) {
    return this.http.delete(
      environment.baseProjectUrl + `project/delete?id=${projectId}`
    )
  }
  addmembersToProject(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/setting`, data
    )
  }

  // createProjectLabel(data: any) {
  //   return this.http.post(
  //     environment.baseProjectUrl + `project/setting`, data
  //   )
  // }
  // createSubState(projectId: any, masterId: any, data: any) {
  //   return this.http.post(
  //     environment.baseProjectUrl + `project/master/state-sub?projectId=${projectId}&masterId=${masterId}`, data
  //   )
  // }
  // deleteSubState(projectId: any, masterId: any, subStateId: any) {
  //   return this.http.delete(
  //     environment.baseProjectUrl + `project/state?projectId=${projectId}&masterStateId=${masterId}&subStateId=${subStateId}`
  //   )
  // }

  // updateSubState(projectId: any, masterId: any, data: any) {
  //   return this.http.post(
  //     environment.baseProjectUrl + `project/master/state-sub?projectId=${projectId}&masterId=${masterId}`, data
  //   )
  // }

  updateLabel(projectId: any, data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/label/update?projectId=${projectId}`, data
    )
  }
  updateWorkItem(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/work-item`, data
    )
  }

  deleteWorkItem(workItemId: any) {
    return this.http.delete(
      environment.baseProjectUrl + `project/workItem?id=${workItemId}`
    )
  }
  delteEpicStatus(epicId:any,id:any,type:any){
    return this.http.delete(
      environment.baseProjectUrl + `project/epic/Delete-epic-status?epicId=${epicId}&id=${id}&type=${type}`
    )
  }
  getUserInbox(mention: boolean) {
    const businessId = localStorage.getItem('businessId');
    const userId = localStorage.getItem('staffId');
    return this.http.get(
      environment.baseProjectUrl + `notification/inbox?businessId=${businessId}&userId=${userId}&mentionsOnly=${mention}`,

    )

  }
  inboxStatus(notificationId: any,) {
    const status = "READ"
    return this.http.put(
      environment.baseProjectUrl + `notification/status-update?notificationId=${notificationId}&status=${status}`, ''

    )
  }
  updateProjectStatus(projectId: any, data: any) {
    return this.http.put(
      environment.baseProjectUrl + `status-project?id=${projectId}&status=${data.status}`, ''
    )
  }
  createModule(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/module`, data
    )
  }
  createView(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/view`, data
    )
  }

  getAllViews(bId: any, pId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/view?businessId=${bId}&projectId=${pId}`,
    )
  }

  getGlobalViews(bId: any,) {
    return this.http.get(
      environment.baseProjectUrl + `project/view?businessId=${bId}`,
    )
  }

  deleteViewById(viewId: any,) {
    return this.http.delete(
      environment.baseProjectUrl + `project/view?id=${viewId}`,
    )
  }

  getAllModules(data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/module`, data
    )
  }
  getWorkitemByModule(moduleId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/module/id?moduleId=${moduleId}`,
    )
  }

  deleteModule(id: any) {
    return this.http.delete(
      environment.baseProjectUrl + `project/module?id=${id}`
    )
  }

  createCycle(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/cycle`, data
    )

  }
  getCycleById(businessId: any, projectId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/cycle/get-all?businessId=${businessId}&projectId=${projectId}`
    )
  }
  getDefaultCycle() {
    return this.http.get(
      environment.baseProjectUrl + `project/default-cycle`
    )
  }
  deleteCycle(cycleId: any) {
    return this.http.delete(
      environment.baseProjectUrl + `project/cycle?id=${cycleId}`
    )
  }

  getWorkitemByCycle(cycleId: string) {
    return this.http.get(
      environment.baseProjectUrl + `project/cycle/id?id=${cycleId}`,
    )
  }
  getAllStates(projectId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/states/${projectId}/states`
    )
  }
  addSubState(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/states/sub-states/add`, data
    )
  }
  updateSubState(data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/states/sub-states/update`, data
    )

  }
  deleteSubState(stateId: string, subStateId: string) {
    return this.http.delete(
      environment.baseProjectUrl + `project/states/${stateId}/sub-states/${subStateId}/delete`
    )
  }
  getAllSubStatesList(projectId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/states/${projectId}/sub-states`
    )
  }

  CreateLabels(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/label`, data
    )
  }
  getAllLabels(projectId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/${projectId}/label`
    )
  }
  deleteLabel(labelId: any) {
    return this.http.delete(
      environment.baseProjectUrl + `project/${labelId}/delete`
    )
  }

  getAllMembers(projectId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/${projectId}/member`
    )
  }
  createMember(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/member/add`, data
    )
  }
    removeMember(memberId: any) {
    return this.http.delete(
      environment.baseProjectUrl + `project/member/{id}/remove?id=${memberId}`
    )
  }

  updateDefaultAssignee(projectId: any, data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/${projectId}/default-assignee/add`, data
    )
  }
  updateLead(projectId: any, data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/${projectId}/lead/update`, data
    )
  }

  activeCycleAnalytics(projectId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/cycle/${projectId}/active-analytics`
    )
  }

  createSubWorkItem(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/add-sub-work-item`, data
    )
  }

  getSubWorkItemByParentId(parentId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/${parentId}/user`
    )
  }

  removeSubWorkitem(parentId: string, childId: string) {
    return this.http.delete(
      environment.baseProjectUrl + `project/${parentId}/remove-sub?childId=${childId}`
    )
  }

  addCommentWorkItem(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `project/work-items/comment`, data
    )
  }

  getTimelineData(workitemId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/work-items/${workitemId}/timeline`
    )
  }
  createPage(data: any) {
    return this.http.post(
      environment.baseProjectUrl + `page`, data
    )
  }
  getAllPages(pId: any,data: any) {
    return this.http.put(
      environment.baseProjectUrl + `page/${pId}`,data
    )
  }
  deletePage(pId: any) {
    return this.http.delete(
      environment.baseProjectUrl + `page/${pId}`
    )
  }
  getPageDetailsById(pId: any) {
    return this.http.get(
      environment.baseProjectUrl + `page/detail/${pId}`,
    )
  }
  markFavPage(pId: any, isFavourite?: boolean) {
    return this.http.put(
      environment.baseProjectUrl + `page/${pId}/favourite?isFav=${isFavourite}`, ''

    )
  }
  lockUnlockPage(pId: any, isLocked?: boolean) {
    return this.http.put(
      environment.baseProjectUrl + `page/${pId}/lock-unlock?isLocked=${isLocked}`, ''

    )
  }

  getYourWorkData(memberId: any, businessId: any, projectId?: any) {
    let url = environment.baseProjectUrl + `your-work/overview/${memberId}?businessId=${businessId}`;
    if (projectId) {
      url += `&projectId=${projectId}`;
    }
    return this.http.get(url);
  }
  
  getYourWorkCreated(memberId: any, businessId: any, projectId?: any) {
    let url = environment.baseProjectUrl + `your-work/created/${memberId}?businessId=${businessId}`;
    if (projectId) {
      url += `&projectId=${projectId}`;
    }
    return this.http.get(url);
  }
  
  getYourWorkAssigned(memberId: any, businessId: any, projectId?: any) {
    let url = environment.baseProjectUrl + `your-work/assigned/${memberId}?businessId=${businessId}`;
    if (projectId) {
      url += `&projectId=${projectId}`;
    }
    return this.http.get(url);
  }
  
  getYourWorkSubscribed(memberId: any, businessId: any, projectId?: any) {
    let url = environment.baseProjectUrl + `your-work/subscribed/${memberId}?businessId=${businessId}`;
    if (projectId) {
      url += `&projectId=${projectId}`;
    }
    return this.http.get(url);
  }
  
  getYourWorkActivity(memberId: any, businessId: any, projectId?: any) {
    let url = environment.baseProjectUrl + `your-work/activity/${memberId}?businessId=${businessId}`;
    if (projectId) {
      url += `&projectId=${projectId}`;
    }
    return this.http.get(url);
  }
  getYourProjectSummary(memberId: any,businessId:any) {
    return this.http.get(
      environment.baseProjectUrl + `your-work/project-wise-summary/${memberId}?businessId=${businessId}`,
    )
  }
  removefav(id: any, type: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/remove-favourites?id=${id}&type=${type}`, ''
    )
  }

  updateWorkItemState(data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/work-item/update-sub-state`, data
    )
  }

  markDefaultState(projectId: string, subStateId: string) {
    return this.http.put(
      environment.baseProjectUrl + `project/${projectId}/mark-default/${subStateId}`, ''
    )
  }

  addAttachment(workitemId: any, data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/work-item/${workitemId}/add-attachment`, data
    )
  }

   addEpicAttachment(workitemId: any, data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/epic/epic/add-attachment?epicId=${workitemId}`, data
    )
  }
  removeAttachment(workitemId: any, attachmentId: any) {
    return this.http.delete(
      environment.baseProjectUrl + `project/work-item/${workitemId}/remove-attachment/${attachmentId}`
    )
  }

  updateWorkitemFields(workitemId: any, data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/work-item/${workitemId}/update/function`, data
    )
  }
  projectFilter(data: any){
    return this.http.put(
      environment.baseProjectUrl + `project/filter`, data
    )
  }
  markNotificationAsRead(notificationId: any) {
    return this.http.put(
      environment.baseProjectUrl + `notification/mark-read?notificationId=${notificationId}`, ''
    );
  }
  markNotificationAsArchived(notificationId: any) {
    return this.http.put(
      environment.baseProjectUrl + `notification/mark-archived?notificationId=${notificationId}`, ''
    )
  }
  markNotificationAsUnarchived(notificationId: any) {
    return this.http.put(
      environment.baseProjectUrl + `notification/mark-archived?notificationId=${notificationId}&isArchive=false`, ''
    );
  }
  markNotificationAsSnoozed(notificationId: any) {
    return this.http.put(
      environment.baseProjectUrl + `notification/mark-snoozed?notificationId=${notificationId}`, ''
    );
  }
  getArchivedNotifications(businessId:any,userId:any) {
    return this.http.get(
      environment.baseProjectUrl + `notification/archived?businessId=${businessId}&userId=${userId}`,
    );
  }
  markAllNotificationsAsRead(businessId:any,userId:any) {
    return this.http.put(
      environment.baseProjectUrl + `notification/mark-all-read?businessId=${businessId}&staffId=${userId}`, ''
    );
  }

  getProjectMemberDetails(projectId: any, userId: any) {
    return this.http.get(
      environment.baseProjectUrl + `project/project-member?projectId=${projectId}&staffId=${userId}`
    );
  }

  saveLayout(projectId: any, staffId: any, layout: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/save-layout?projectId=${projectId}&staffId=${staffId}&layout=${layout}`, ''
    )
  }
  logWork(workitemId: any, data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/work-item/${workitemId}/work-log`, data
    );
  }

  addEstimation(data:any){
    return this.http.post(
      environment.baseProjectUrl + `project/estimations`, data
    );
  }
  getEstimation(projectId:any){
    return this.http.get(
      environment.baseProjectUrl + `project/${projectId}/estimation`
    );
  }
  updateEstimation(data:any){
    return this.http.put(
      environment.baseProjectUrl + `project/change-estimation-type`, data
    );
  }
  deleteEstimation(data:any){
    // Angular HttpClient.delete doesn't accept body in older versions; use request('DELETE', ...) to include payload
    return this.http.request('DELETE',
      environment.baseProjectUrl + `project/delete-estimation-type-value`,
      { body: data }
    );
  }
  updateEstimationValue(data:any){
    return this.http.put(
      environment.baseProjectUrl + `project/update-estimation-type-value`, data
    );
  }

  getFavByMemberId(memberId:any){
    const businessId = localStorage.getItem("businessId");
    return this.http.get(
      environment.baseProjectUrl + `project/get-favData/${memberId}/${businessId}`,
    );
  }

  addFavProject(data:any){
    return this.http.put(
      environment.baseProjectUrl + `project/add-favourite`, data
    );
  }
  removeFavProject(favId:any){
    return this.http.delete(
      environment.baseProjectUrl + `project/remove-favourite/${favId}`
    );
  }

  createEpic(data:any){
    return this.http.post(
      environment.baseProjectUrl + `project/epic/create-epic`, data
    );
  }

  getEpicListing(data:any){
    return this.http.put(
      environment.baseProjectUrl + `project/epic/get-epic`, data
    );
  }

  addTrack(data:any){
    return this.http.put(
      environment.baseProjectUrl + `project/epic/add-epic-status`, data
    );
  }

    getAllEpicProperties(projectId:any){
    return this.http.get(
      environment.baseProjectUrl + `project/epic/getAll-property?projectId=${projectId}`
    );
  }

     createEPicProperty(data:any){
    return this.http.put(
      environment.baseProjectUrl + `project/epic/create-epic-property`, data
    );
  }
   deleteEpicProperty(data:any){
    return this.http.delete(
      environment.baseProjectUrl + `project/epic/delete-epic-property?propertyId=${data}`,
    );
  }
 
  
  addWorkitem(data:any){
    return this.http.post(
      environment.baseProjectUrl + 'project/epic/add-work-item',data
    )
  }
  getEpicWorkitemList(EpicId:any){
    return this.http.get(
      environment.baseProjectUrl + `project/epic/${EpicId}/user`
    )
  }

  removeWorkitem(EpicId:any,workItemId:any){
    return this.http.delete(
      environment.baseProjectUrl + `project/epic/${EpicId}/remove-workitem?childId=${workItemId}`
    )
  }

    updateEpicCustomProperties(EpicId:any,data:any){
    return this.http.put(
      environment.baseProjectUrl + `project/epic/update/customProperty?epicId=${EpicId}`,data
    )
  }

   updateEpicFields(epicId: any, data: any) {
    return this.http.put(
      environment.baseProjectUrl + `project/epic/epic/${epicId}/update`, data
    )
  }

   removeEpicAttachment(workitemId: any, attachmentId: any) {
    return this.http.delete(
      environment.baseProjectUrl + `project/epic/remove-attachment?epicId=${workitemId}&attachmentId=${attachmentId}`
    )
  }

    deleteEpic(workItemId: any) {
    return this.http.delete(
      environment.baseProjectUrl + `project/epic/delete-epic?id=${workItemId}`
    )
  }

  generateWithAiSurprise(data:any){
    return this.http.post(
      environment.aiTemplateServiceUrl + 'generate-work-item-surprise-me', data
    );

  }

  viewById(projectId:any, viewId:any){
    return this.http.get(
      environment.baseProjectUrl + `project/get-fav-view/${projectId}/${viewId}`
    )
  }
}