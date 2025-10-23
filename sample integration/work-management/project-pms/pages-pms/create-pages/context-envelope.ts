// ContextEnvelope.ts - Based on the provided taxonomy
export type PageType =
  | 'PROJECT' | 'TASK' | 'MEETING' | 'DOCUMENTATION' | 'KB';

export interface ContextEnvelope {
  tenantId: string;
  page: {
    type: PageType;
    id: string;
    title?: string;
    parent?: { type: PageType; id: string }[]; // inheritance chain
  };
  subject: { // the "who/what"
    projectId?: string;
    userIds?: string[];
    businessId?: string;
  };
  timeScope: {
    start?: string; // ISO
    end?: string;   // ISO
    relative?: 'PROJECT_LIFETIME' | 'LAST_90D' | 'LAST_30D';
  };
  retrieval: {
    must: Array<{ key: string; op: 'eq'|'in'|'range'; value: any }>; // e.g., projectId eq X, tenantId eq T
    should?: Array<{ key: string; op: 'eq'|'in'; value: any }>;
    deny?: Array<{ key: string; op: 'eq'|'in'; value: any }>;
    sourcesWhitelist?: string[]; // indices/collections/doc types
    maxSnippets: number; // e.g., 12
  };
  privacy: {
    pii: 'none'|'low'|'high';
    redactions: ('EMAIL'|'PHONE'|'API_KEY'|'ACCOUNT_NAME')[];
    crossTenant: false;
  };
}

// Page classification function
export function classifyPage(meta: { template?: string; labels?: string[]; path?: string; projectId?: string }): PageType {
  if (meta.labels?.includes('meeting') || meta.template === 'meeting-notes') return 'MEETING';
  if (meta.labels?.includes('documentation') || meta.template === 'project-documentation') return 'DOCUMENTATION';
  if (meta.labels?.includes('kb') || meta.template === 'technical-guide') return 'KB';
  if (meta.projectId && meta.template === 'task') return 'TASK';
  if (meta.projectId) return 'PROJECT';
  return 'DOCUMENTATION'; // default for general pages
}

// Build context envelope for pages
export function buildPageEnvelope(input: { tenantId: string; pageId: string; projectId: string; meta: any }): ContextEnvelope {
  const explicitType = (input.meta && (input.meta.pageType as PageType)) || undefined;
  const type = explicitType || classifyPage(input.meta);
  const base: ContextEnvelope = {
    tenantId: input.tenantId,
    page: { type, id: input.pageId },
    subject: { projectId: input.projectId, businessId: input.tenantId },
    timeScope: { relative: 'LAST_90D' }, // Default time scope
    retrieval: {
      must: [
        { key: 'tenantId', op: 'eq', value: input.tenantId },
        { key: 'projectId', op: 'eq', value: input.projectId }
      ],
      maxSnippets: 8
    },
    privacy: { pii: 'low', redactions: [], crossTenant: false }
  };

  switch (type) {
    case 'PROJECT':
      return {
        ...base,
        timeScope: { relative: 'PROJECT_LIFETIME' },
        retrieval: {
          must: [
            { key: 'tenantId', op: 'eq', value: input.tenantId },
            { key: 'projectId', op: 'eq', value: input.projectId }
          ],
          sourcesWhitelist: ['pages', 'workitems', 'decisions', 'meetings'],
          maxSnippets: 10
        }
      };
    case 'TASK':
      return {
        ...base,
        timeScope: { relative: 'LAST_90D' },
        retrieval: {
          must: [
            { key: 'tenantId', op: 'eq', value: input.tenantId },
            { key: 'pageId', op: 'eq', value: input.pageId }
          ],
          sourcesWhitelist: ['pages', 'workitems', 'comments'],
          maxSnippets: 8
        }
      };
    case 'MEETING':
      return {
        ...base,
        timeScope: { relative: 'LAST_30D' },
        retrieval: {
          must: [
            { key: 'tenantId', op: 'eq', value: input.tenantId },
            { key: 'projectId', op: 'eq', value: input.projectId }
          ],
          sourcesWhitelist: ['meetings', 'decisions'],
          maxSnippets: 6
        }
      };
    case 'DOCUMENTATION':
      return {
        ...base,
        timeScope: { relative: 'LAST_90D' },
        retrieval: {
          must: [
            { key: 'tenantId', op: 'eq', value: input.tenantId },
            { key: 'projectId', op: 'eq', value: input.projectId }
          ],
          sourcesWhitelist: ['pages', 'documents', 'guides'],
          maxSnippets: 12
        }
      };
    case 'KB':
      return {
        ...base,
        timeScope: { relative: 'LAST_90D' },
        retrieval: {
          must: [
            { key: 'tenantId', op: 'eq', value: input.tenantId }
          ],
          sourcesWhitelist: ['kb_articles', 'guides'],
          maxSnippets: 15
        }
      };
    default:
      return {
        ...base,
        timeScope: { relative: 'LAST_90D' },
        retrieval: {
          must: [
            { key: 'tenantId', op: 'eq', value: input.tenantId },
            { key: 'projectId', op: 'eq', value: input.projectId }
          ],
          maxSnippets: 8
        }
      };
  }
}
