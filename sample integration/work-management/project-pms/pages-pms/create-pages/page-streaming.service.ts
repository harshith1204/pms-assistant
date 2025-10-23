import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, Subject } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { environment } from 'src/environments/environment';
import { ContextEnvelope, buildPageEnvelope } from './context-envelope';

@Injectable({
  providedIn: 'root'
})
export class PageStreamingService {
  private streamingSubject = new Subject<string>();

  constructor(private http: HttpClient) {}

  // Frontend method that calls Groq API directly with context management
  generatePageContent(payload: {
    tenantId?: string;
    pageId?: string;
    projectId?: string;
    template: { title: string; content: string };
    prompt: string;
    meta?: any;
    context?: ContextEnvelope;
  }): Observable<{ blocks: any[] }> {

    // Use provided context envelope or build one from payload
    const contextEnvelope = payload.context || buildPageEnvelope({
      tenantId: payload.tenantId || '',
      pageId: payload.pageId || '',
      projectId: payload.projectId || '',
      meta: payload.meta || {}
    });

    // Context validation removed - allowing all prompts

    // Enhanced payload with context envelope for Groq API
    const requestPayload = {
      context: contextEnvelope,
      template: payload.template,
      prompt: payload.prompt,
      pageId: payload.pageId || '',
      projectId: payload.projectId || '',
      tenantId: payload.tenantId || ''
    };

    // Use HttpClient for regular API call instead of streaming
    const headers = new HttpHeaders({
      'Content-Type': 'application/json'
    });

    return this.http.get<{ blocks: any[] }>(
      `${environment.aiTemplateServiceUrl}stream-page-content`,
      {
        headers,
        params: {
          data: JSON.stringify(requestPayload)
        }
      }
    ).pipe(
      catchError(error => {
        console.error('Page generation error:', error);
        throw error;
      })
    );
  }

  // Method removed - only streaming is used now

  // Get streaming updates as observable
  getStreamingUpdates(): Observable<string> {
    return this.streamingSubject.asObservable();
  }

  // Basic context validation (removed strict keyword checking)
  validateContextScope(prompt: string, context: ContextEnvelope): { valid: boolean; reason?: string } {
    // Validation removed - allowing all prompts
    return { valid: true };
  }

  // Apply redactions based on privacy settings (client-side processing for immediate feedback)
  applyPrivacyRedactions(content: string, privacy: ContextEnvelope['privacy']): string {
    let redactedContent = content;

    privacy.redactions.forEach(redaction => {
      switch (redaction) {
        case 'EMAIL':
          redactedContent = redactedContent.replace(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g, '[EMAIL REDACTED]');
          break;
        case 'PHONE':
          redactedContent = redactedContent.replace(/\+?[\d\s\-\(\)]{10,}/g, '[PHONE REDACTED]');
          break;
        case 'API_KEY':
          redactedContent = redactedContent.replace(/[A-Za-z0-9]{32,}/g, '[API_KEY REDACTED]');
          break;
        case 'ACCOUNT_NAME':
          // This would need more sophisticated logic based on your data structure
          break;
      }
    });

    return redactedContent;
  }
}
