import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { environment } from 'src/environments/environment';

export interface WorkItemTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  title: string;
  content: string;
  estimatedTime?: number;
  labels: string[];
  state?: string;
  icon: string;
  color: string;
}

export interface TemplateCategory {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
}

@Injectable({
  providedIn: 'root'
})
export class WorkItemTemplatesService {

  private readonly defaultTemplates: WorkItemTemplate[] = [
    {
      id: 'bug-fix',
      name: 'Bug Fix',
      description: 'Report and fix software bugs',
      category: 'Development',
      title: 'Fix [Bug Description]',
      content: '## Bug Description\n[Describe the bug in detail]\n\n## Steps to Reproduce\n1. [Step 1]\n2. [Step 2]\n3. [Step 3]\n\n## Expected Behavior\n[What should happen]\n\n## Actual Behavior\n[What actually happens]\n\n## Environment\n- Browser:\n- OS:\n- Version:\n\n## Additional Context\n[Any additional information]',
      estimatedTime: 60,
      labels: ['bug', 'fix'],
      state: 'In Progress',
      icon: '🐛',
      color: '#dc2626'
    },
    {
      id: 'feature-request',
      name: 'Feature Request',
      description: 'New feature implementation',
      category: 'Development',
      title: 'Implement [Feature Name]',
      content: '## Feature Overview\n[Brief description of the feature]\n\n## Requirements\n- [Requirement 1]\n- [Requirement 2]\n- [Requirement 3]\n\n## Acceptance Criteria\n- [Criteria 1]\n- [Criteria 2]\n- [Criteria 3]\n\n## Technical Details\n[Technical implementation details]\n\n## Dependencies\n- [Dependency 1]\n- [Dependency 2]',
      estimatedTime: 240,
      labels: ['feature', 'enhancement'],
      state: 'Backlog',
      icon: '✨',
      color: '#16a34a'
    },
    {
      id: 'task',
      name: 'General Task',
      description: 'General work item or task',
      category: 'General',
      title: 'Complete [Task Description]',
      content: '## Task Description\n[Describe what needs to be done]\n\n## Objectives\n- [Objective 1]\n- [Objective 2]\n- [Objective 3]\n\n## Deliverables\n- [Deliverable 1]\n- [Deliverable 2]\n\n## Notes\n[Any additional notes or context]',
      estimatedTime: 120,
      labels: ['task'],
      state: 'Todo',
      icon: '📝',
      color: '#2563eb'
    },
    {
      id: 'documentation',
      name: 'Documentation',
      description: 'Create or update documentation',
      category: 'Documentation',
      title: 'Document [Topic]',
      content: '## Documentation Topic\n[What needs to be documented]\n\n## Purpose\n[Why this documentation is needed]\n\n## Target Audience\n- [Audience 1]\n- [Audience 2]\n\n## Content Outline\n1. [Section 1]\n2. [Section 2]\n3. [Section 3]\n\n## References\n- [Reference 1]\n- [Reference 2]\n\n## Review Checklist\n- [ ] Content is accurate\n- [ ] Examples are clear\n- [ ] Formatting is consistent\n- [ ] Links are working',
      estimatedTime: 90,
      labels: ['documentation', 'docs'],
      state: 'Backlog',
      icon: '📚',
      color: '#7c3aed'
    },
    {
      id: 'research',
      name: 'Research Task',
      description: 'Research and analysis work',
      category: 'Research',
      title: 'Research [Topic]',
      content: '## Research Topic\n[What needs to be researched]\n\n## Research Questions\n- [Question 1]\n- [Question 2]\n- [Question 3]\n\n## Research Methods\n- [Method 1]\n- [Method 2]\n\n## Expected Outcomes\n- [Outcome 1]\n- [Outcome 2]\n\n## Resources\n- [Resource 1]\n- [Resource 2]\n\n## Timeline\n- [Milestone 1]: [Date]\n- [Milestone 2]: [Date]',
      estimatedTime: 180,
      labels: ['research', 'analysis'],
      state: 'Backlog',
      icon: '🔍',
      color: '#ea580c'
    },
    {
      id: 'review',
      name: 'Code Review',
      description: 'Review code changes',
      category: 'Review',
      title: 'Review [Component/Module]',
      content: '## Code Review\n[Component or module to review]\n\n## Files to Review\n- [File 1]\n- [File 2]\n- [File 3]\n\n## Focus Areas\n- [Focus 1]\n- [Focus 2]\n- [Focus 3]\n\n## Checklist\n- [ ] Code follows best practices\n- [ ] Tests are included\n- [ ] Documentation is updated\n- [ ] Performance considerations\n- [ ] Security considerations\n\n## Comments\n[Any specific comments or concerns]',
      estimatedTime: 30,
      labels: ['review', 'code-review'],
      state: 'In Progress',
      icon: '👀',
      color: '#0891b2'
    },
    {
      id: 'spike',
      name: 'Technical Spike',
      description: 'Investigate technical feasibility',
      category: 'Development',
      title: 'Spike: [Technical Investigation]',
      content: '## Technical Spike\n[What needs to be investigated]\n\n## Investigation Goals\n- [Goal 1]\n- [Goal 2]\n- [Goal 3]\n\n## Research Questions\n- [Question 1]\n- [Question 2]\n- [Question 3]\n\n## Approach\n1. [Step 1]\n2. [Step 2]\n3. [Step 3]\n\n## Expected Time\n[Time estimate]\n\n## Success Criteria\n- [Criteria 1]\n- [Criteria 2]\n\n## Risks\n- [Risk 1]\n- [Risk 2]\n\n## Findings\n[Document findings here]\n\n## Recommendations\n- [Recommendation 1]\n- [Recommendation 2]',
      estimatedTime: 120,
      labels: ['spike', 'technical', 'investigation'],
      state: 'In Progress',
      icon: '🔬',
      color: '#c2410c'
    }
  ];

  constructor(private http: HttpClient) { }

  /**
   * Get all available work item templates
   */
  getTemplates(): Observable<WorkItemTemplate[]> {
    return of(this.defaultTemplates);
  }

  /**
   * Get templates by category
   */
  getTemplatesByCategory(category: string): Observable<WorkItemTemplate[]> {
    if (category === 'All') {
      return of(this.defaultTemplates);
    }

    const filteredTemplates = this.defaultTemplates.filter(
      template => template.category === category
    );
    return of(filteredTemplates);
  }

  /**
   * Search templates by query
   */
  searchTemplates(query: string): Observable<WorkItemTemplate[]> {
    if (!query.trim()) {
      return of(this.defaultTemplates);
    }

    const searchLower = query.toLowerCase();
    const filteredTemplates = this.defaultTemplates.filter(template =>
      template.name.toLowerCase().includes(searchLower) ||
      template.description.toLowerCase().includes(searchLower) ||
      template.category.toLowerCase().includes(searchLower) ||
      template.labels.some(label => label.toLowerCase().includes(searchLower))
    );

    return of(filteredTemplates);
  }

  /**
   * Get template by ID
   */
  getTemplateById(id: string): Observable<WorkItemTemplate | null> {
    const template = this.defaultTemplates.find(t => t.id === id);
    return of(template || null);
  }

  /**
   * Get template categories
   */
  getCategories(): Observable<TemplateCategory[]> {
    const categories: TemplateCategory[] = [
      { id: 'All', name: 'All Templates', description: 'All available templates', icon: '📋', color: '#6b7280' },
      { id: 'Development', name: 'Development', description: 'Development and coding tasks', icon: '💻', color: '#16a34a' },
      { id: 'General', name: 'General', description: 'General purpose tasks', icon: '📝', color: '#2563eb' },
      { id: 'Documentation', name: 'Documentation', description: 'Documentation and writing tasks', icon: '📚', color: '#7c3aed' },
      { id: 'Research', name: 'Research', description: 'Research and analysis tasks', icon: '🔍', color: '#ea580c' },
      { id: 'Review', name: 'Review', description: 'Review and approval tasks', icon: '👀', color: '#0891b2' }
    ];

    return of(categories);
  }

  /**
   * Process template with user prompt
   */
  processTemplateWithPrompt(template: WorkItemTemplate, prompt: string): WorkItemTemplate {
    if (!prompt.trim()) {
      return template;
    }

    // Simple placeholder replacement - can be enhanced with more sophisticated logic
    let processedTitle = template.title;
    let processedContent = template.content;

    // Replace common placeholders
    const placeholders = ['[Task Description]', '[Feature Name]', '[Bug Description]', '[Topic]', '[Component/Module]', '[Technical Investigation]'];

    placeholders.forEach(placeholder => {
      processedTitle = processedTitle.replace(placeholder, prompt);
      processedContent = processedContent.replace(placeholder, prompt);
    });

    // Replace any remaining bracketed placeholders with the prompt
    processedTitle = processedTitle.replace(/\[.*?\]/g, prompt);
    processedContent = processedContent.replace(/\[.*?\]/g, prompt);

    return {
      ...template,
      title: processedTitle,
      content: processedContent
    };
  }

  /**
   * Validate template data
   */
  validateTemplate(template: Partial<WorkItemTemplate>): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!template.name || template.name.trim().length === 0) {
      errors.push('Template name is required');
    }

    if (!template.description || template.description.trim().length === 0) {
      errors.push('Template description is required');
    }

    if (!template.category || template.category.trim().length === 0) {
      errors.push('Template category is required');
    }

    if (!template.title || template.title.trim().length === 0) {
      errors.push('Template title is required');
    }

    if (!template.content || template.content.trim().length === 0) {
      errors.push('Template content is required');
    }

    // priority validation removed

    if (!template.icon || template.icon.trim().length === 0) {
      errors.push('Template icon is required');
    }

    if (!template.color || template.color.trim().length === 0) {
      errors.push('Template color is required');
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }

  /**
   * Create a new custom template
   */
  createCustomTemplate(templateData: Omit<WorkItemTemplate, 'id'>): Observable<WorkItemTemplate> {
    const validation = this.validateTemplate(templateData);

    if (!validation.isValid) {
      throw new Error(`Template validation failed: ${validation.errors.join(', ')}`);
    }

    const newTemplate: WorkItemTemplate = {
      ...templateData,
      id: this.generateTemplateId(),
      labels: templateData.labels || []
    };

    // In a real application, this would make an API call to save the template
    // For now, we'll just return it as if it was saved
    console.log('Custom template created:', newTemplate);

    return of(newTemplate);
  }

  /**
   * Generate a unique ID for a template
   */
  private generateTemplateId(): string {
    const timestamp = Date.now();
    const random = Math.floor(Math.random() * 1000);
    return `custom-${timestamp}-${random}`;
  }
}
