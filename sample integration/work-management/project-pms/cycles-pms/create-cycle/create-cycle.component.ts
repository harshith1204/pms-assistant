import { Component, Inject, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { WorkManagementService } from '../../../work-management.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { start } from 'repl';

@Component({
  selector: 'app-create-cycle',
  templateUrl: './create-cycle.component.html',
  styleUrls: ['./create-cycle.component.scss']
})
export class CreateCycleComponent implements OnInit {
  cycleForm: FormGroup = this.fb.group({
    title: ['', Validators.required],
    description: [''],
    dateRange: [null]
  });

  constructor(private fb: FormBuilder,
    private projectService: WorkManagementService,
    private snackbar: MatSnackBar,
    @Inject(MAT_DIALOG_DATA) public data: any,
    private dialogRef: MatDialogRef<CreateCycleComponent>) { }

    projectId: any;
    businessId: any;
    startDate: Date | null = null;
    endDate: Date | null = null;
    isLoading: boolean = false;

  ngOnInit() {
    
    this.projectId = this.data?.data?.projectId;
    this.businessId = localStorage.getItem('businessId');
    if (this.data?.cycle) {
      this.cycleForm.patchValue({
        title: this.data.cycle.title,
        description: this.data.cycle.description,
      });
      this.startDate = this.data.cycle.startDate ? new Date(this.data.cycle.startDate) : null;
      this.endDate = this.data.cycle.endDate ? new Date(this.data.cycle.endDate) : null;
      this.cycleForm.patchValue({ dateRange: { start: this.startDate, end: this.endDate } });
    }

  }

  private isValidDate(date: any): boolean {
    if (!date) return false;
    
    if (typeof date === 'string') {
      date = new Date(date);
    }
    
    return date instanceof Date && !isNaN(date.getTime());
  }

  onSubmit() {
    if (this.cycleForm.valid) {
      
    }
  }

  onCancel() {
    this.dialogRef.close();
  }

  createCycle() {
    if (this.isLoading) return;
    
    this.isLoading = true;
    
    let payload :any= {
      projectId: this.projectId,
      businessId: this.businessId,
      title: this.cycleForm.value.title,
      description: this.cycleForm.value.description,
      startDate: this.cycleForm.value.dateRange?.start,
      endDate: this.cycleForm.value.dateRange?.end
      
    };
    if(this.data.edit=true){
      payload.id = this.data?.cycle?.id;
    }
    
    this.projectService.createCycle(payload).subscribe({
      next: (response: any) => {
        this.isLoading = false;
        this.snackbar.open('Cycle created successfully', 'Close' , { duration: 1000 });
        this.dialogRef.close();
      },
      error: (error: any) => {
        console.error('Error creating cycle:', error);
        this.isLoading = false;
        this.snackbar.open('Failed to create cycle', 'Close', { duration: 1000 });
        this.dialogRef.close();
      }

    });
  }

  getDateRangeText(): string {
    if (this.startDate && this.endDate) {
      try {
        const startStr = this.startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        const endStr = this.endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        return `${startStr} → ${endStr}`;
      } catch (error) {
        console.error('Date formatting error:', error);
        return 'Start date → End date';
      }
    }
    return 'Start date → End date';
  }
  clearDateRange(event: Event) {
    event.stopPropagation();
    this.startDate = null;
    this.endDate = null;
    this.cycleForm.patchValue({ dateRange: null });
  }

  changeData() {
    if (this.startDate && this.endDate && this.isValidDate(this.startDate) && this.isValidDate(this.endDate)) {
      this.cycleForm.patchValue({
        dateRange: {
          start: this.startDate,
          end: this.endDate
        }
      });
    }
  }
}
