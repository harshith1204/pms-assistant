import { Component, Inject, OnInit, Optional } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { WorkManagementService } from '../../../work-management.service';
import { PageStreamingService } from './page-streaming.service';
import { buildPageEnvelope, ContextEnvelope } from './context-envelope';

@Component({
  selector: 'app-create-pages-template',
  templateUrl: './create-pages-template.component.html',
  styleUrls: ['./create-pages-template.component.scss']
})
export class CreatePagesTemplateComponent implements OnInit {
  projectId: string = '';
  projectData: any;
  selectedTemplate: any = null;
  selectedPageType: 'PROJECT' | 'TASK' | 'MEETING' | 'DOCUMENTATION' | 'KB' | '' = '';
  userPrompt: string = '';
  templates: any[] = [];
  isGenerating: boolean = false;
  contextEnvelope: ContextEnvelope | null = null;

  constructor(
    private dialogRef: MatDialogRef<CreatePagesTemplateComponent>,
    private projectService: WorkManagementService,
    private streamingService: PageStreamingService,
    @Optional() @Inject(MAT_DIALOG_DATA) public data: any
  ) {
    this.projectData = data?.projectData;
    this.projectId = this.projectData?.projectId;

    // Build context envelope for this page
    if (this.projectData) {
      this.contextEnvelope = buildPageEnvelope({
        tenantId: localStorage.getItem('businessId') || '',
        pageId: data?.pageId || '',
        projectId: this.projectId,
        meta: {
          template: data?.template || 'documentation',
          projectId: this.projectId
        }
      });
    }
  }

  ngOnInit(): void {
    this.loadPageTemplates();
  }

  loadPageTemplates(): void {
    // Provide business templates that map to page types
    this.templates = [
      { id: 'project_status', name: 'Project Status', icon: '📊', color: '#3B82F6', pageType: 'PROJECT', description: 'Executive summary with KPIs, milestones, risks' },
      { id: 'task_spec', name: 'Task Spec', icon: '📝', color: '#10B981', pageType: 'TASK', description: 'Detailed task breakdown, acceptance criteria, next steps' },
      { id: 'meeting_notes', name: 'Meeting Notes', icon: '📅', color: '#06B6D4', pageType: 'MEETING', description: 'Agenda, decisions, action items, owners, due dates' },
      { id: 'documentation', name: 'Documentation', icon: '📚', color: '#8B5CF6', pageType: 'DOCUMENTATION', description: 'How-to, concepts, references for internal knowledge' },
      { id: 'knowledge_base', name: 'Knowledge Base', icon: '💡', color: '#F59E0B', pageType: 'KB', description: 'FAQ, troubleshooting, guides for quick answers' },
      { id: 'release_notes', name: 'Release Notes', icon: '🚀', color: '#EF4444', pageType: 'DOCUMENTATION', description: 'Version highlights, changes, fixes, known issues' },
      { id: 'risk_register', name: 'Risk Register', icon: '⚠️', color: '#F97316', pageType: 'PROJECT', description: 'Risks, likelihood, impact, owner, mitigation' },
      { id: 'okr_summary', name: 'OKR Summary', icon: '🎯', color: '#22C55E', pageType: 'PROJECT', description: 'Objectives, key results, progress, next steps' }
    ];
  }

  selectTemplate(t: any): void {
    this.selectedTemplate = t;
    this.selectedPageType = t?.pageType || '';
  }

  generateWithAI(): void {
    if (!this.userPrompt.trim()) {
      this.projectService.openSnack('Please provide a business-focused prompt for content generation.', 'Ok');
      return;
    }

    if (this.userPrompt.length > 3000) {
      this.projectService.openSnack('Please keep your prompt under 3000 characters for optimal content generation.', 'Ok');
      return;
    }

    // Context validation removed - allowing all prompts
    this.isGenerating = true;

    // Rebuild context envelope with current projectId and selected template
    const contextEnvelope = buildPageEnvelope({
      tenantId: localStorage.getItem('businessId') || '',
      pageId: this.data?.pageId || '',
      projectId: this.projectId,
      meta: {
        template: this.data?.template || 'documentation',
        projectId: this.projectId,
        pageType: this.selectedPageType || undefined
      }
    });

    const payload = {
      context: contextEnvelope,
      template: {
        title: 'Dynamic Content Generation',
        content: 'Generate structured content based on user prompt'
      },
      prompt: this.userPrompt,
      pageId: this.data?.pageId || '',
      projectId: this.projectId,
      tenantId: localStorage.getItem('businessId') || ''
    };

    // Use non-streaming generation
    this.streamingService.generatePageContent(payload).subscribe({
      next: (response: { blocks: any[] }) => {
        this.isGenerating = false;
        this.projectService.openSnack('Content generated successfully!', 'Ok');

        // Close with generated blocks
        this.dialogRef.close({
          blocks: response.blocks,
          prompt: this.userPrompt
        });
      },
      error: (err) => {
        this.isGenerating = false;
        console.error('Content generation failed:', err);
        this.projectService.openSnack('AI generation failed. Please try again.', 'Ok');
      }
    });
  }

  // Method removed - only streaming is used now

  closeModal(): void {
    this.dialogRef.close();
  }
}
