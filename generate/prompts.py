# Page Type Prompt Dictionary - Business-focused prompts for each template type

PAGE_TYPE_PROMPTS = {
    'PROJECT': """
**Project Management Context:**
- Focus on project lifecycle, deliverables, and strategic objectives
- Include KPIs, milestones, risk assessment, and team performance metrics
- Structure for executive decision-making and stakeholder communication
- Adapt content based on specific project template: Status Reports, Risk Registers, or OKR Summaries

**Key Elements to Include (use ONLY provided facts):**
- Executive Summary with project status and key achievements
- KPI Dashboard with measurable metrics and progress indicators
- Milestone Timeline with completion status and upcoming deadlines
- Risk Register with impact assessment and mitigation strategies (for Risk Register template)
- OKR Framework with objectives, key results, and progress tracking (for OKR Summary template)
- Team Performance metrics and resource allocation insights
- Budget Tracking summary and financial performance indicators
- Critical Path Analysis and dependency mapping

**Business Standards:**
- Use humanized, conversational language that feels natural and approachable while maintaining professionalism
- Ground all content in the provided request/context; do not invent metrics, dates, owners, or financials. Avoid placeholder tokens like "TBD". When information is missing, write neutral, grounded prose (e.g., describe approach or options) and include a brief "Questions for Stakeholders" section only if essential.
- Maintain professional yet warm tone suitable for executive reporting that builds trust and clarity
- Include success criteria and measurable outcomes only when supplied; otherwise omit them or phrase as general approaches; do not insert placeholders
- Adapt tone and focus based on template type: more analytical for Risk Registers, more strategic for OKR Summaries
""",

    'TASK': """
**Task Management Context:**
- Focus on specific work items, deliverables, and action-oriented outcomes
- Provide detailed breakdown of requirements and execution steps
- Structure for clear task ownership and accountability

**Key Elements to Include (do NOT assume unknowns):**
- Task Overview with clear objectives and success criteria
- Detailed Requirements breakdown with acceptance criteria
- Step-by-Step Execution Plan with dependencies and prerequisites
- Resource Requirements including skills, tools, and time estimates
- Deliverables Specification with quality standards and formats
- Risk Assessment for potential blockers and mitigation strategies
- Success Metrics and completion validation criteria

**Business Standards:**
- Use humanized, conversational language that's easy to understand and follow
- Add details only if present in input; otherwise keep language neutral without placeholders. Optionally add up to 3 clarifying questions when essential.
- Structure for easy progress tracking and status updates that feel collaborative and supportive
- Maintain professional yet approachable tone appropriate for technical teams
""",

    'MEETING': """
**Meeting Management Context:**
- Focus on structured discussion, decision-making, and action tracking
- Capture agenda items, outcomes, and follow-up requirements
- Structure for effective meeting facilitation and documentation

**Key Elements to Include (stay within provided scope):**
- Meeting Overview with purpose, objectives, and expected outcomes
- Participant List with roles and responsibilities
- Structured Agenda with time allocations and discussion topics
- Key Discussion Points with decisions and rationale
- Action Items with clear ownership, deadlines, and deliverables
- Decision Log with outcomes and supporting information
- Follow-up Requirements and next steps

**Business Standards:**
- Use humanized, conversational language
- Only document participants, decisions, and actions if provided or obvious from the request; otherwise keep neutral, grounded language without placeholders. Optionally include clarifying questions if essential.
- Structure for easy reference and follow-up tracking
- Maintain professional yet conversational tone
""",

    'DOCUMENTATION': """
**Documentation Context:**
- Focus on knowledge transfer, process documentation, and reference materials
- Provide clear explanations, procedures, and guidelines
- Structure for easy comprehension and future reference
- Adapt content for different documentation types: General Documentation or Release Notes

**Key Elements to Include (use grounded generalizations when unknown):**
- Document Purpose and scope definition
- Target Audience identification and knowledge prerequisites
- Step-by-Step Instructions or procedures with clear workflows
- Key Concepts and terminology definitions
- Best Practices and guidelines for implementation
- Release Highlights, changes, and version information (for Release Notes template)
- Troubleshooting section with common issues and solutions
- Reference Materials and additional resources

**Business Standards:**
- Use humanized, conversational language
- Only state facts present in the request/context; avoid placeholder tokens. Prefer concise, grounded guidance; optionally include a short questions list when needed.
- Structure for logical flow and easy navigation
- Maintain professional yet approachable tone appropriate for technical documentation
- For Release Notes: Avoid inventing metrics or dates; if not provided, summarize changes qualitatively or omit numeric metrics
""",

    'KB': """
**Knowledge Base Context:**
- Focus on quick access information, frequently asked questions, and problem-solving
- Provide concise, searchable content for immediate reference
- Structure for rapid information retrieval and self-service

**Key Elements to Include (grounded responses only):**
- Question-Answer Format for common inquiries
- Quick Reference Guides for standard procedures
- Troubleshooting Steps for common technical issues
- Best Practices and tips for efficient workflows
- Glossary of Terms for quick definitions
- Related Articles and cross-references

**Business Standards:**
- Use humanized, conversational language that's friendly and reassuring
- Ground answers in provided information only; if steps or data are missing, avoid placeholders and provide generally applicable guidance. Optionally add 1–3 clarifying questions only if needed.
- Structure for easy browsing and information discovery
- Maintain helpful, supportive tone for user assistance
"""
}

