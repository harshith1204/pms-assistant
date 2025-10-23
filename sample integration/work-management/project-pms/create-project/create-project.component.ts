import { Component, Inject, Optional } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialog, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ProjectSettingsComponent } from '../project-settings/project-settings.component';
import { WorkManagementService } from '../../work-management.service';
import { ImageUploadService } from 'src/app/master-config-components/master/screens/locations/image-upload.service';
import { StorageKeys } from 'src/app/shared-module-files/simpo.constant';
import { EventEmmiterService } from '../../../../../services/event-emmiter.service';
import { PickerModule } from '@ctrl/ngx-emoji-mart';

@Component({
  selector: 'app-create-project',
  templateUrl: './create-project.component.html',
  styleUrls: ['./create-project.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    MatFormFieldModule,
    MatSelectModule,
    MatIconModule,
    MatButtonModule,
    FormsModule,
    PickerModule,
  ]
})
export class CreateProjectComponent {
  staffList: any;
  file: any;
   imgLoader : boolean = false;
   buttonLoader : boolean = false;
  imgUrl: any;

  defaultImage: string = 'https://d2yx15pncgmu63.cloudfront.net/prod-images/524681c1750191737292Website-Design-Background-Feb-09-2022-03-13-55-73-AM.webp';
 imagePreview: string | ArrayBuffer | null = null;
 
  constructor(
    private dialogRef: MatDialogRef<CreateProjectComponent>,
    private dialog: MatDialog,
     private imageUploadService: ImageUploadService,
    private projectService:WorkManagementService,
    private eventEmitter: EventEmmiterService,
   @Optional() @Inject(MAT_DIALOG_DATA) public data: any,
  ) {}

  ngOnInit(){
 this.staffList = this.data;
 this.accessType = 'PUBLIC';

  }

   bDetails: any;
  businessName: any;
  projectName:any;
  businessId: any;
  projectId:any;
  ProjectDesription:any;
  accessType:String = '';
  selectedLead:any;
  selectedLeadId:any;

  private isProjectIdManuallyEdited = false;

  onClose(): void {
    this.dialogRef.close();
  }

  openSettingsDialog(res:any){
    this.dialogRef.close();
    this.dialog.open(ProjectSettingsComponent, {
      width: '600px',
      disableClose: true,
      panelClass: 'settings-modal',
      data:res
    });
  }

  getstaff(){
    
  }
  response:any;

  getSelectedLead() {
  this.selectedLead = this.staffList.find(lead => lead.id === this.selectedLeadId);
}
  updateProjectList() {
    this.eventEmitter.projectListupdate.emit({
      view: true
    })
  }

  projectCreationAPI(){
      this.buttonLoader = true;
      let staffId = window.localStorage.getItem('staffId')
      let staffName= window.localStorage.getItem('staffName')
     this.getSelectedLead();
    let bDetails = window.localStorage.getItem('bDetails') || ''
    if (bDetails) {
      this.bDetails = JSON.parse(bDetails)
      this.businessName = this.bDetails.name;
      this.businessId = this.bDetails?.id || '';
    }

    let payload = {
      projectDisplayId: this.projectId,
      business: { id: this.businessId, name: this.businessName },
      name: this.projectName,
      description: this.ProjectDesription,
      imageUrl: this.imagePreview !== null ? this.imagePreview : this.defaultImage ,
      icon: this.selectedEmoji || '😊',
      access: this.accessType.toUpperCase(),
      status: 'NOT_STARTED',
      leadMail: this.selectedLead ? this.selectedLead.contact.email : '',
      lead: this.selectedLead
    ? { id: this.selectedLead.id, name: this.selectedLead.name }
    : null,
      defaultAsignee: { id: '', name: '' },
      createdBy: { id: staffId, name: staffName },
      active: true,
    }
   
  
  if(payload.name && payload.projectDisplayId){
this.projectService.createProject(payload).subscribe((res: any) => {
      this.response = res.data;
      // this.openSettingsDialog(this.response);
      this.buttonLoader = false;
      this.onClose();
      
      this.updateProjectList();
      

    }, (error: any) => {
      this.buttonLoader = false;
      console.error('Error creating project:', error);
      this.projectService.openSnack('Error creating project', 'Ok');
    })
  }else{
    this.buttonLoader = false;
    this.projectService.openSnack('Please add mandatory details to create your project','Ok')
  }
    
  }

  loadNavData() {
    
  }


  async updatePostImage(ev: Event) {
  const input = ev.target as HTMLInputElement;
  if (input.files && input.files.length > 0) {
    const file = input.files[0];
    this.file = file;
    this.imgLoader = true;

    try {
    this.imgUrl = await this.imageUploadService.uploadSEOimages(file,'Blogs')
    this.imgUrl = this.imgUrl.Location;
      this.imagePreview = this.imgUrl;
    } catch (error) {
      console.error('Image upload failed:', error);
    }

    this.imgLoader = false;
  }
}

  onProjectNameChange(event: any): void {
    const projectName = event.target.value;
    
    // Only auto-generate if user hasn't manually edited the project ID
    if (!this.isProjectIdManuallyEdited && projectName) {
      // Get first 5 letters, remove spaces and convert to uppercase
      this.projectId = projectName.replace(/\s/g, '').substring(0, 5).toUpperCase();
    }
  }

  onProjectIdFocus(): void {
    // Mark as manually edited when user focuses on the field
    this.isProjectIdManuallyEdited = true;
  }

  onProjectIdChange(): void {
    // Mark as manually edited when user types in the field
    this.isProjectIdManuallyEdited = true;
  }

  showEmojiPicker = false;
  selectedEmoji: string = '';

  toggleEmojiPicker() {
    this.showEmojiPicker = !this.showEmojiPicker;
  }

  addEmoji(event: any) {
    this.selectedEmoji = event.emoji.native; // event.emoji.native contains emoji character
    this.showEmojiPicker = false; // close after selection
    
    // You can also access other properties:
    // event.emoji.id - emoji identifier
    // event.emoji.name - emoji name
    // event.emoji.colons - emoji shortcode like :smile:
  }


}
