import { Component, Inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { WorkManagementService } from '../../../work-management.service';
import { error } from 'console';
import { min } from 'moment';

@Component({
  selector: 'app-add-estimation',
  templateUrl: './add-estimation.component.html',
  styleUrls: ['./add-estimation.component.scss']
})
export class AddEstimationComponent {
  constructor(public dialogRef: MatDialogRef<AddEstimationComponent>,
        private projectService: WorkManagementService,
          @Inject(MAT_DIALOG_DATA) public data: any,
          private snackBar: MatSnackBar
      
  ){

  }

  ngOnInit(){
    this.projectId = this.data.projectId;
    if (this.data && this.data.mode === 'EDIT') {
      this.mode = 'EDIT';
      this.showWizard = false;
      this.showSwitch = false;
    }
  }

  showStepTwo = false;
  showWizard = true; 
  showSwitch = false; 

  points: { id: number; value: number; isEditing?: boolean; editValue?: number; isNew?: boolean; isDeleting?: boolean; reassignToId?: number | null }[] = [];
  times: { id: number; minutes: number; isEditing?: boolean; editHours?: number; editMinutes?: number; editMode?: 'minutes' | 'hm'; isNew?: boolean; isDeleting?: boolean; reassignToId?: number | null }[] = [];
  categories: { id: number; value: string; isEditing?: boolean; editValue?: string; isNew?: boolean; isDeleting?: boolean; reassignToId?: number | null }[] = [];

  estimateType: 'POINTS' | 'TIME' | 'CATEGORY' = 'POINTS';
  private idSeq = 1;
  mode: 'CREATE' | 'EDIT' = 'CREATE';
  currentEstimateSystemLabel: string = '';
  availableNewTypes: Array<'POINTS' | 'TIME' | 'CATEGORY'> = [];
  newEstimateType: 'POINTS' | 'TIME' | 'CATEGORY' | null = null;
  switchSourceItems: Array<{ hours?: number; minutes?: number; text?: string; value?: number }> = [];
  switchTargets: Array<{ hours?: number; minutes?: number; text?: string; value?: number }> = [];
  oldEstimate:any;
  newEstimate:any;
  oldValue:any;

  onEstimateTypeChange(type: 'POINTS' | 'TIME' | 'CATEGORY') {
    this.estimateType = type;
  }

  onCustomClick() {
    if (this.estimateType === 'POINTS') {
      this.points = [1, 2].map(v => ({ id: this.idSeq++, value: v }));
      this.estimatedList = this.points.map(p => p.value.toString());
    } else if (this.estimateType === 'TIME') {
      this.times = [
        { id: this.idSeq++, minutes: 1, isEditing: true, editHours: 0, editMinutes: 1, editMode: 'minutes', isNew: true }
      ];
      this.estimatedList = this.times.map(t => {
        const hr = Math.floor(t.minutes / 60);  
        const min = t.minutes % 60;
        return {
          hr: hr.toString(),
          min: min.toString().padStart(2, "0")
        };
      });
    } else if (this.estimateType === 'CATEGORY') {
      this.categories = [
        { id: this.idSeq++, value: '', isEditing: true, editValue: '', isNew: true }
      ];
      this.estimatedList = this.categories.map(c => c.value.toString());
    }
    this.showStepTwo = true;
  }

  onFibonacciClick() {
    this.estimateType = 'POINTS';
    this.points = [1, 2, 3, 5, 8, 13].map(v => ({ id: this.idSeq++, value: v }));
    this.estimatedList = this.points.map(p =>  p.value.toString());
    this.showStepTwo = true;
  }

  onLinearClick() {
    this.estimateType = 'POINTS';
    this.points = [1, 2, 3, 4, 5, 6].map(v => ({ id: this.idSeq++, value: v }));
    this.estimatedList = this.points.map(p =>  p.value.toString());
    this.showStepTwo = true;
  }

  onSquaresClick() {
    this.estimateType = 'POINTS';
    this.points = [1, 4, 9, 16, 25, 36].map(v => ({ id: this.idSeq++, value: v }));
    this.estimatedList = this.points.map(p => p.value.toString());
    this.showStepTwo = true;
  }

  onHoursClick() {
    this.estimateType = 'TIME';
    const minutesList = [60, 120, 180, 240, 330, 390];
    this.times = minutesList.map(m => ({ id: this.idSeq++, minutes: m }));
    this.estimatedList = this.times.map(t => {
      const hr = Math.floor(t.minutes / 60);  
      const min = t.minutes % 60;
      return {
        hr: hr.toString(),
        min: min.toString().padStart(2, "0")
      };
    });
    this.showStepTwo = true;
  }

  onCategoriesClick(){
    this.estimateType = 'CATEGORY';
    this.categories = ['Easy', 'Medium', 'Hard', 'Very Hard'].map((v, i) => ({ id: this.idSeq++, value: v, isEditing: false, editValue: v }));
    this.estimatedList = this.categories.map(c => c.value.toString());
    this.showStepTwo = true;
  }

  goBack() {
    this.showStepTwo = false;
  }

  onCancel() {
    this.dialogRef.close({
      created: false
    })
  }
  onCreate(){
    this.dialogRef.close({
      created: true
    });
  }

  addPoint() {
  this.points.push({ id: this.idSeq++, value: 0, isEditing: false, editValue: undefined, isNew: true });
  }

  startEditPoint(p: { id: number; value: number; isEditing?: boolean; editValue?: number; isNew?: boolean }) {
    p.isEditing = true;
    p.editValue = p.value;
  }

  editOldValue:any;
  editNewValue:any;
  confirmPoint(p: { id: number; value: number; isEditing?: boolean; editValue?: number; isNew?: boolean }) {
    if (p.editValue == null) {
      this.snackBar.open('Please enter a point value', 'Close', { duration: 1500 });
      return;
    }
    const v = Number(p.editValue);
    if (isNaN(v)) {
      this.snackBar.open('Please enter a valid numeric point', 'Close', { duration: 1500 });
      return;
    }
    this.editOldValue = String(p.value);
    this.editNewValue = String(v);
    p.value = v;
    p.editValue = undefined;
    if (p.isNew) {
      this.addEstimationValue();
      p.isNew = false;
    }
    if (p.isEditing) {
      this.updateEstimationValue();
      p.isEditing = false;
    }
  }

  addEstimationValue(){
    if (this.estimateType === 'POINTS') {
      this.estimatedList = this.points.map(p => String(p.value ?? 0));
    } else if (this.estimateType === 'TIME') {
      this.estimatedList = this.times.map(t => {
        const hr = Math.floor((t.minutes || 0) / 60);
        const min = (t.minutes || 0) % 60;
        return { hr: hr.toString(), min: min.toString().padStart(2, '0') };
      });
    } else if (this.estimateType === 'CATEGORY') {
      this.estimatedList = this.categories.map(c => String(c.value ?? ''));
    }
    this.createEstimate();
  }

  cancelPoint(p: { id: number; value: number; isEditing?: boolean; editValue?: number; isNew?: boolean }) {
    if (p.isNew) {
      this.points = this.points.filter(x => x.id !== p.id);
      return;
    }
    p.isEditing = false;
    p.editValue = undefined;
  }

  deletePoint(p: { id: number }) {
    this.points = this.points.filter(x => x.id !== p.id);
  }

  startDeletePoint(p: { id: number; isDeleting?: boolean; reassignToId?: number | null }) {
    p.isDeleting = true;
    p.reassignToId = null;
  }

  cancelDeletePoint(p: { id: number; isDeleting?: boolean; reassignToId?: number | null }) {
    p.isDeleting = false;
    p.reassignToId = null;
  }

  confirmDeletePoint(p: { id: number; reassignToId?: number | null }) {
    const toDelete = this.points.find(x => x.id === p.id);
    const target = (p.reassignToId != null) ? this.points.find(x => x.id === p.reassignToId) : undefined;
    if (toDelete) {
      this.oldValue = String(toDelete.value ?? '');
      this.newValue = target ? String(target.value ?? '') : null;
    }
    this.points = this.points.filter(x => x.id !== p.id);
    if (toDelete) {
      this.deleteEstimation();
    }
  }

  addTime() {
    this.times.push({ id: this.idSeq++, minutes: 0, isEditing: false, editHours: 0, editMinutes: 0, editMode: 'hm', isNew: true });
  }

  startEditTime(t: { id: number; minutes: number; isEditing?: boolean; editHours?: number; editMinutes?: number; editMode?: 'minutes' | 'hm'; isNew?: boolean }) {
    t.isEditing = true;
    t.editHours = Math.floor(t.minutes / 60);
    t.editMinutes = t.minutes % 60;
    t.editMode = 'hm';
  }

  confirmTime(t: { id: number; minutes: number; isEditing?: boolean; editHours?: number; editMinutes?: number; editMode?: 'minutes' | 'hm'; isNew?: boolean }) {
    const h = t.editMode === 'minutes' ? 0 : (Number(t.editHours) || 0);
    const mRaw = Number(t.editMinutes);
    const m = isNaN(mRaw) ? 0 : mRaw;
    const total = (h * 60) + m;
    const wasNew = !!t.isNew;
    const prevTotal = t.minutes || 0;
    if (!total) {
      this.snackBar.open('Time must be greater than 0', 'Close', { duration: 1500 });
      return;
    }
    const oldHr = Math.floor(prevTotal / 60);
    const oldMin = prevTotal % 60;
    const newHr = Math.floor(total / 60);
    const newMin = total % 60;
    this.editOldValue = { hr: oldHr.toString(), min: oldMin.toString().padStart(2, '0') };
    this.editNewValue = { hr: newHr.toString(), min: newMin.toString().padStart(2, '0') };
    t.minutes = total;
    t.editHours = undefined;
    t.editMinutes = undefined;
    t.editMode = undefined;
    if (t.isNew) {
      this.addEstimationValue();
      t.isNew = false;
    }
    if (t.isEditing) {
      this.updateEstimationValue();
      t.isEditing = false;
    }
  }

  cancelTime(t: { id: number; minutes: number; isEditing?: boolean; editHours?: number; editMinutes?: number; editMode?: 'minutes' | 'hm'; isNew?: boolean }) {
    if (t.isNew) {
      this.times = this.times.filter(x => x.id !== t.id);
      return;
    }
    t.isEditing = false;
    t.editHours = undefined;
    t.editMinutes = undefined;
    t.editMode = undefined;
  }

  deleteTime(t: { id: number }) {
    this.times = this.times.filter(x => x.id !== t.id);
  }

  startDeleteTime(t: { id: number; isDeleting?: boolean; reassignToId?: number | null }) {
    t.isDeleting = true;
    t.reassignToId = null;
  }

  cancelDeleteTime(t: { id: number; isDeleting?: boolean; reassignToId?: number | null }) {
    t.isDeleting = false;
    t.reassignToId = null;
  }

  confirmDeleteTime(t: { id: number; reassignToId?: number | null }) {
    const toDelete = this.times.find(x => x.id === t.id);
    const target = (t.reassignToId != null) ? this.times.find(x => x.id === t.reassignToId) : undefined;
    if (toDelete) {
      const oldHr = Math.floor((toDelete.minutes || 0) / 60);
      const oldMin = (toDelete.minutes || 0) % 60;
      this.oldValue = { hr: oldHr.toString(), min: oldMin.toString().padStart(2, '0') };
      if (target) {
        const newHr = Math.floor((target.minutes || 0) / 60);
        const newMin = (target.minutes || 0) % 60;
        this.newValue = { hr: newHr.toString(), min: newMin.toString().padStart(2, '0') };
      } else {
        this.newValue = null;
      }
    }
    this.times = this.times.filter(x => x.id !== t.id);
    if (toDelete) {
      this.deleteEstimation();
    }
  }

  formatMinutes(total: number): string {
    const h = Math.floor(total / 60);
    const m = total % 60;
    if (h && m) return `${h}h ${m}m`;
    if (h) return `${h}h`;
    return `${m}m`;
  }

  private toMinutes(v: any): number {
    if (v == null) return 0;
    if (typeof v === 'number' && isFinite(v)) return Math.max(0, Math.floor(v));
    if (typeof v === 'string') {
      const n = Number(v);
      if (!isNaN(n)) return Math.max(0, Math.floor(n));
      const hMatch = v.match(/(\d+)\s*h/i);
      const mMatch = v.match(/(\d+)\s*m/i);
      const h = hMatch ? Number(hMatch[1]) : 0;
      const m = mMatch ? Number(mMatch[1]) : 0;
      if (h || m) return h * 60 + m;
      return 0;
    }
    if (typeof v === 'object') {
      const hr = Number((v as any).hr);
      const min = Number((v as any).min);
      const h = isNaN(hr) ? 0 : Math.max(0, Math.floor(hr));
      const m = isNaN(min) ? 0 : Math.max(0, Math.floor(min));
      return h * 60 + m;
    }
    return 0;
  }

  private populateFromEstimate(e: any) {
    if (!e) return;
    const type = String(e.estimateSystem || '').toUpperCase();
    const custom = Array.isArray(e.custom) ? e.custom : [];
    if (type === 'POINTS') {
      this.estimateType = 'POINTS';
      this.points = custom.map((v: any) => ({ id: this.idSeq++, value: Number(v) || 0 }));
      this.estimatedList = this.points.map(p => p.value.toString());
    } else if (type === 'CATEGORY') {
      this.estimateType = 'CATEGORY';
      this.categories = custom.map((v: any) => ({ id: this.idSeq++, value: String(v), isEditing: false, editValue: String(v) }));
      this.estimatedList = this.categories.map(c => c.value.toString());
    } else if (type === 'TIME') {
      this.estimateType = 'TIME';
      this.times = custom.map((v: any) => ({ id: this.idSeq++, minutes: this.toMinutes(v) }));
      this.estimatedList = this.times.map(t => {
        const hr = Math.floor(t.minutes / 60);
        const min = t.minutes % 60;
        return { hr: hr.toString(), min: min.toString().padStart(2, '0') };
      });
    }
  }

  startManageEstimates() {
    this.populateFromEstimate(this.data?.estimate);
    this.mode = 'EDIT';
    this.showWizard = true;
    this.showStepTwo = true;
    this.showSwitch = false;
  }

  startChangeEstimateType() {
    const current = String(this.data?.estimate?.estimateSystem || this.estimateType || '').toUpperCase() as 'POINTS' | 'TIME' | 'CATEGORY';
    this.oldEstimate = current;
    this.currentEstimateSystemLabel = current === 'POINTS' ? 'Points' : current === 'TIME' ? 'Time' : 'Categories';
    const all: Array<'POINTS' | 'TIME' | 'CATEGORY'> = ['POINTS', 'TIME', 'CATEGORY'];
    this.availableNewTypes = all.filter(t => t !== current);
    this.newEstimateType = null;
    this.showWizard = false;
    this.showStepTwo = false;
    this.showSwitch = true;

    const e = this.data?.estimate;
    const src = Array.isArray(e?.custom) ? e.custom : [];
    this.switchSourceItems = (current === 'TIME')
      ? src.map((m: any) => this.formatMinutes(this.toMinutes(m)))
      : src.map((v: any) => String(v));
    this.switchTargets = this.switchSourceItems.map(() => ({}));
  }

  goBackFromSwitch() {
    this.showSwitch = false;
    this.showWizard = false; 
  }

  goBackFromManage() {
    this.showStepTwo = false;
    this.showWizard = false; 
  }

  onNewTypeSelected(val: string) {
    const t = String(val).toUpperCase();
    if (t === 'POINTS' || t === 'TIME' || t === 'CATEGORY') {
      this.newEstimateType = t;
      this.newEstimate = t;
    } else {
      this.newEstimateType = null;
    }
  }

  updateEstimateType() {
    if (!this.newEstimateType) return;
    if (this.newEstimateType === 'POINTS') {
      this.estimateType = 'POINTS';
      this.estimatedList = this.switchTargets.map(t => String(Number(t.value) || 0));
    } else if (this.newEstimateType === 'CATEGORY') {
      this.estimateType = 'CATEGORY';
      this.estimatedList = this.switchTargets.map(t => (t.text ?? '').toString());
    } else if (this.newEstimateType === 'TIME') {
      this.estimateType = 'TIME';
      this.estimatedList = this.switchTargets.map(t => {
        const h = Number(t.hours) || 0;
        const m = Number(t.minutes) || 0;
        return { hr: h.toString(), min: m.toString().padStart(2, '0') };
      });
    }
    // this.createEstimate();
  }

  onDone() {
    if(this.mode!=='EDIT'){
      if (this.estimateType === 'POINTS') {
      this.estimatedList = this.points.map(p => String(p.value ?? 0));
    } else if (this.estimateType === 'TIME') {
      this.estimatedList = this.times.map(t => {
        const hr = Math.floor((t.minutes || 0) / 60);
        const min = (t.minutes || 0) % 60;
        return { hr: hr.toString(), min: min.toString().padStart(2, '0') };
      });
    } else if (this.estimateType === 'CATEGORY') {
      this.estimatedList = this.categories.map(c => String(c.value ?? ''));
    }
    this.createEstimate();
    }else{
      this.dialogRef.close();

    }
  }

  addCategory() {
    this.categories.push({ id: this.idSeq++, value: '', isEditing: false, editValue: '', isNew: true });
  }

  startEditCategory(c: { id: number; value: string; isEditing?: boolean; editValue?: string; isNew?: boolean }) {
    c.isEditing = true;
    c.editValue = c.value;
  }

  confirmCategory(c: { id: number; value: string; isEditing?: boolean; editValue?: string; isNew?: boolean }) {
    const v = (c.editValue ?? '').toString();
    if (!v || !v.trim()) {
      this.snackBar.open('Category cannot be empty', 'Close', { duration: 1500 });
      return;
    }
    const wasNew = !!c.isNew;
    this.editOldValue = String(c.value ?? '');
    this.editNewValue = v.trim();
    c.value = v.trim();
    c.editValue = undefined;
    if(c.isNew){
      this.addEstimationValue();
      c.isNew = false;
    }
    if (c.isEditing) {
      this.updateEstimationValue();
      c.isEditing = false;
    }
    
  }

  cancelCategory(c: { id: number; value: string; isEditing?: boolean; editValue?: string; isNew?: boolean }) {
    if (c.isNew) {
      this.categories = this.categories.filter(x => x.id !== c.id);
      return;
    }
    c.isEditing = false;
    c.editValue = undefined;
  }

  startDeleteCategory(c: { id: number; isDeleting?: boolean; reassignToId?: number | null }) {
    c.isDeleting = true;
    c.reassignToId = null;
  }

  cancelDeleteCategory(c: { id: number; isDeleting?: boolean; reassignToId?: number | null }) {
    c.isDeleting = false;
    c.reassignToId = null;
  }

  confirmDeleteCategory(c: { id: number; reassignToId?: number | null }) {
    const toDelete = this.categories.find(x => x.id === c.id);
    const target = (c.reassignToId != null) ? this.categories.find(x => x.id === c.reassignToId) : undefined;
    if (toDelete) {
      this.oldValue = String(toDelete.value ?? '');
      this.newValue = target ? String(target.value ?? '') : null;
    }
    this.categories = this.categories.filter(x => x.id !== c.id);
    if (toDelete) {
      this.deleteEstimation();
    }
  }

  estimatedList: any=[];
  estimationData: any;
  projectId: any;
  createEstimate(){
    let payload: any = {
      projectId: this.projectId,
      estimateSystem: this.estimateType,
      user:{
        id: localStorage.getItem('staffId'),
        name: localStorage.getItem('staffName')
      },
      custom:this.estimatedList

    };
    this.projectService.addEstimation(payload).subscribe(response => {
      this.estimationData = response;
      this.dialogRef.close();
    },error => {
      console.error('Error creating estimation:', error);
    });
  }

  newEstimatedList:any;
  oldEstimatedList:any;
  changeEstimation() {
    if (!this.newEstimateType) {
      this.snackBar.open('Please select a new estimate system before updating', 'Close', { duration: 1500 });
      return;
    }

    const hasEmptyValues = this.switchTargets.some((target, index) => {
      if (this.newEstimateType === 'TIME') {
        const hours = Number(target?.hours) || 0;
        const minutes = Number(target?.minutes) || 0;
        return hours === 0 && minutes === 0;
      } else if (this.newEstimateType === 'POINTS') {
        const value = Number(target?.value);
        return isNaN(value) || value === 0 || !target?.value;
      } else { // CATEGORY
        const text = String(target?.text || '').trim();
        return text === '' || text === '[object Object]' || !target?.text;
      }
    });

    if (hasEmptyValues) {
      let errorMessage = '';
      if (this.newEstimateType === 'TIME') {
        errorMessage = 'Please provide valid time values (hours and minutes must be greater than 0h 00m)';
      } else if (this.newEstimateType === 'POINTS') {
        errorMessage = 'Please provide valid point values (must be greater than 0)';
      } else {
        errorMessage = 'Please provide valid category names (cannot be empty)';
      }
      this.snackBar.open(errorMessage, 'Close', { duration: 3000 });
      return;
    }

    const len = Math.min(this.switchSourceItems.length, this.switchTargets.length);
    const oldNewValueMap = [] as Array<{ oldValue: any; newValue: any }>;

    for (let i = 0; i < len; i++) {
      const rawOld: any = this.switchSourceItems[i];
      const rawNew: any = this.switchTargets[i] || {};

      let oldValue: any;
      if (this.oldEstimate === 'TIME') {
        const mins = this.toMinutes(rawOld);
        const h = Math.floor(mins / 60);
        const m = mins % 60;
        oldValue = { hr: h.toString(), min: m.toString().padStart(2, '0') };
      } else if (this.oldEstimate === 'POINTS') {
        const v = Number((rawOld as any)?.value ?? rawOld);
        oldValue = String(isNaN(v) ? 0 : v);
      } else { // CATEGORY
        oldValue = String((rawOld as any)?.text ?? rawOld ?? '');
      }

      let newValue: any;
      if (this.newEstimateType === 'TIME') {
        const h = Number(rawNew?.hours) || 0;
        const m = Number(rawNew?.minutes) || 0;
        newValue = { hr: h.toString(), min: m.toString().padStart(2, '0') };
      } else if (this.newEstimateType === 'POINTS') {
        const v = Number(rawNew?.value ?? rawNew) || 0;
        newValue = String(v);
      } else { // CATEGORY
        newValue = String(rawNew?.text ?? rawNew ?? '');
      }

      oldNewValueMap.push({ oldValue, newValue });
    }

    let payload: any = {
      projectId: this.projectId,
      oldEstimation: this.oldEstimate,
      newEstimation: this.newEstimateType,
      updatedBy: {
        id: localStorage.getItem('staffId'),
        name: localStorage.getItem('staffName')
      },
      oldNewValueMap

    };
    const data = payload;
    this.projectService.updateEstimation(data).subscribe(response => {
      this.estimationData = response;
      this.dialogRef.close();
    },error => {
      console.error('Error creating estimation:', error);
    });
  }


  newValue:any;
  deleteEstimation(){
    let payload: any = {
      projectId: this.projectId,
      oldValue: this.oldValue || this.editOldValue,
      newValue: this.newValue || this.editNewValue
    };
    const data = payload;
    this.projectService.deleteEstimation(payload).subscribe(response => {
    },error => {
      console.error('Error deleting estimation value:', error);
    });
  }
  updateEstimationValue(){
    let payload: any = {
      projectId: this.projectId,
      oldValue: this.oldValue || this.editOldValue,
      newValue: this.newValue || this.editNewValue
    };
    this.projectService.updateEstimationValue(payload).subscribe(response => {
    },error => {  
      console.error('Error updating estimation value:', error);
    });
  }
}
