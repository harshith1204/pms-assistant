import { Component, EventEmitter, Input, Output, OnInit } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { PopupPmsComponent } from '../../popup-pms/popup-pms.component';
import { WorkItemTemplatesService, WorkItemTemplate } from './work-item-templates.service';
import { WorkManagementService } from '../../../work-management.service';

interface AiGeneratedTemplatePayload {
  title?: string;
  name?: string;
  description?: string;
  content?: string;
  labels?: string[];
  estimatedTime?: number;
  durationInMinutes?: number;
  state?: { id?: string; name?: string } | string;
  [key: string]: any;
}


@Component({
  selector: 'app-work-item-templates',
  templateUrl: './work-item-templates.component.html',
  styleUrls: ['./work-item-templates.component.scss']
})
export class WorkItemTemplatesComponent implements OnInit {

  @Input() projectId: string = '';
  @Input() projectData: any;
  @Input() showAsModal: boolean = false;
  @Output() templateSelected = new EventEmitter<{ template: WorkItemTemplate, prompt: string }>();
  @Output() closeModal = new EventEmitter<void>();

  selectedTemplate: WorkItemTemplate | null = null;
  userPrompt: string = '';
  showPromptInput: boolean = false;
  templates: WorkItemTemplate[] = [];
  filteredTemplates: WorkItemTemplate[] = [];

  constructor(
    private matDialog: MatDialog,
    private templatesService: WorkItemTemplatesService,
    private workService: WorkManagementService
  ) { }

  ngOnInit(): void {
    this.loadTemplates();
  }


  loadTemplates(): void {
    this.templatesService.getTemplates().subscribe(templates => {
      this.templates = templates;
      this.filteredTemplates = [...this.templates];
    });
  }

  selectTemplate(template: WorkItemTemplate): void {
    this.selectedTemplate = template;
    this.showPromptInput = true;
  }

  // search and categories removed per UI simplification

  useTemplate(): void {
    if (!this.selectedTemplate) {
      return;
    }

    // Process template with user prompt using the service
    const processedTemplate = this.templatesService.processTemplateWithPrompt(
      this.selectedTemplate,
      this.userPrompt
    );

    // Emit the selected template with the processed content
    this.templateSelected.emit({
      template: processedTemplate,
      prompt: this.userPrompt
    });

    if (this.showAsModal) {
      this.closeModal.emit();
    }
  }


  cancelTemplate(): void {
    this.selectedTemplate = null;
    this.showPromptInput = false;
    this.userPrompt = '';
  }

  onGenerateWithAI(): void {
    if (!this.selectedTemplate || !this.userPrompt.trim()) {
      return;
    }

    const payload = {
      prompt: this.userPrompt,
      template: {
        title: this.selectedTemplate.title,
        content: this.selectedTemplate.content
      }
    };

    this.workService.generateWorkItemWithAI(payload).subscribe({
      next: (res: any) => {
        const parsed = this.extractGeneratedTemplate(res, this.selectedTemplate as WorkItemTemplate);
        this.templateSelected.emit({ template: parsed, prompt: this.userPrompt });
        if (this.showAsModal) {
          this.closeModal.emit();
        }
      },
      error: (err) => {
        console.error('AI generation failed', err);
        this.workService.openSnack('AI generation failed. Using template instead.', 'Ok');
        const processedTemplate = this.templatesService.processTemplateWithPrompt(
          this.selectedTemplate as WorkItemTemplate,
          this.userPrompt
        );
        this.templateSelected.emit({ template: processedTemplate, prompt: this.userPrompt });
        if (this.showAsModal) {
          this.closeModal.emit();
        }
      }
    });
  }

  private extractGeneratedTemplate(res: any, fallback: WorkItemTemplate): WorkItemTemplate {
    const payload = this.mergeGeneratedPayload(res);

    const titleCandidates = [
      payload.title,
      payload.name,
      typeof res?.title === 'string' ? res.title : undefined,
      fallback.title
    ];

    const descriptionCandidates = [
      payload.description,
      payload.content,
      typeof res?.description === 'string' ? res.description : undefined,
      typeof res?.content === 'string' ? res.content : undefined,
      fallback.content
    ];

    const selectedTitle = titleCandidates.find(value => typeof value === 'string' && value.trim().length > 0) || fallback.title;
    const selectedDescription = descriptionCandidates.find(value => typeof value === 'string' && value.trim().length > 0) || fallback.content;
    const selectedState = typeof payload.state === 'object'
      ? payload.state?.name
      : payload.state;

    return {
      ...fallback,
      title: selectedTitle,
      content: this.normalizeDescription(selectedDescription),
      name: payload.name || fallback.name,
      labels: Array.isArray(payload.labels) ? payload.labels : fallback.labels,
      estimatedTime: payload.estimatedTime || payload.durationInMinutes || fallback.estimatedTime,
      state: selectedState || fallback.state
    };
  }

  private mergeGeneratedPayload(res: any): AiGeneratedTemplatePayload {
    const buckets: Array<Record<string, any> | null> = [
      this.tryParseJson(res),
      this.tryParseJson(res?.data),
      this.tryParseJson(res?.response),
      this.tryParseJson(res?.result),
      this.tryParseJson(res?.title),
      this.tryParseJson(res?.description),
      this.tryParseJson(res?.content)
    ];

    return buckets
      .filter((bucket): bucket is Record<string, any> => !!bucket && typeof bucket === 'object')
      .reduce((acc, bucket) => ({ ...acc, ...bucket }), {} as AiGeneratedTemplatePayload);
  }

  private tryParseJson(raw: any): Record<string, any> | null {
    if (!raw) {
      return null;
    }

    if (typeof raw === 'object') {
      return raw;
    }

    if (typeof raw !== 'string') {
      return null;
    }

    const trimmed = raw.trim();
    if (!trimmed) {
      return null;
    }

    const candidates: string[] = [];

    const fenceMatch = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i);
    if (fenceMatch) {
      candidates.push(fenceMatch[1]);
    }

    candidates.push(trimmed);

    const start = trimmed.indexOf('{');
    const end = trimmed.lastIndexOf('}');
    if (start !== -1 && end !== -1 && end > start) {
      candidates.push(trimmed.substring(start, end + 1));
    }

    for (const candidate of candidates) {
      try {
        return JSON.parse(candidate);
      } catch {
        // continue trying next candidate
      }
    }

    return null;
  }

  private normalizeDescription(raw: any): string {
    if (raw === null || raw === undefined) {
      return '';
    }

    if (typeof raw === 'string') {
      return raw;
    }

    try {
      return JSON.stringify(raw);
    } catch {
      return String(raw);
    }
  }

  getButtonPosition(event: MouseEvent, dialogWidth: number = 200, dialogHeight: number = 200): { top: string, right: string } {
    const button = event.currentTarget as HTMLElement;
    const buttonRect = button.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    const viewportWidth = window.innerWidth;
    const margin = 10;

    const spaceBelow = viewportHeight - buttonRect.bottom - margin;
    const spaceAbove = buttonRect.top - margin;
    const spaceRight = viewportWidth - buttonRect.right - margin;
    const spaceLeft = buttonRect.left - margin;

    if (viewportWidth < 768) {
      return {
        top: '50%',
        right: '50%'
      };
    }

    let top: number;
    if (spaceBelow >= dialogHeight || (spaceBelow < dialogHeight && spaceAbove < dialogHeight)) {
      top = buttonRect.bottom + window.scrollY;
    } else {
      top = buttonRect.top + window.scrollY - dialogHeight;
    }

    let right: number;
    if (spaceRight >= dialogWidth || (spaceRight < dialogWidth && spaceLeft < dialogWidth)) {
      right = window.innerWidth - buttonRect.right + window.scrollX;
    } else {
      right = window.innerWidth - buttonRect.left + window.scrollX;
    }

    top = Math.max(margin, Math.min(top, viewportHeight - dialogHeight - margin + window.scrollY));
    right = Math.max(margin, Math.min(right, viewportWidth - dialogWidth - margin + window.scrollX));

    return {
      top: top + 'px',
      right: right + 'px'
    };
  }

  openTemplateDialog(event: MouseEvent): void {
    const position = this.getButtonPosition(event, window.innerWidth * 0.5, window.innerHeight * 0.5);
    const dialogRef = this.matDialog.open(PopupPmsComponent, {
      width: '50%',
      height: 'fit-content',
      position: { top: '10vh', right: position.right },
      data: { status: 'TEMPLATES', templates: this.templates, projectData: this.projectData }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result && result.template) {
        this.selectTemplate(result.template);
      }
    });
  }

  closeTemplatesModal(): void {
    this.closeModal.emit();
  }
}
