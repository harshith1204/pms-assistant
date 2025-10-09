# Page Type Prompt Dictionary - Business-focused prompts for each template type

PAGE_TYPE_PROMPTS = {
    'PROJECT': """
**Project Management Context:**
- Focus on project lifecycle, deliverables, and strategic objectives
- Include KPIs, milestones, risk assessment, and team performance metrics
- Structure for executive decision-making and stakeholder communication
- Adapt content based on specific project template: Status Reports, Risk Registers, or OKR Summaries

**Key Elements to Include:**
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
- Present data-driven insights with actionable recommendations in an engaging, readable format
- Maintain professional yet warm tone suitable for executive reporting that builds trust and clarity
- Include success criteria and measurable outcomes for each section with clear, relatable explanations
- Adapt tone and focus based on template type: more analytical for Risk Registers, more strategic for OKR Summaries
""",

    'TASK': """
**Task Management Context:**
- Focus on specific work items, deliverables, and action-oriented outcomes
- Provide detailed breakdown of requirements and execution steps
- Structure for clear task ownership and accountability

**Key Elements to Include:**
- Task Overview with clear objectives and success criteria
- Detailed Requirements breakdown with acceptance criteria
- Step-by-Step Execution Plan with dependencies and prerequisites
- Resource Requirements including skills, tools, and time estimates
- Deliverables Specification with quality standards and formats
- Risk Assessment for potential blockers and mitigation strategies
- Success Metrics and completion validation criteria

**Business Standards:**
- Use humanized, conversational language that's easy to understand and follow, like explaining to a colleague
- Include measurable outcomes and quality checkpoints with practical, relatable examples
- Structure for easy progress tracking and status updates that feel collaborative and supportive
- Maintain professional yet approachable tone appropriate for technical teams that encourages clarity
""",

    'MEETING': """
**Meeting Management Context:**
- Focus on structured discussion, decision-making, and action tracking
- Capture agenda items, outcomes, and follow-up requirements
- Structure for effective meeting facilitation and documentation

**Key Elements to Include:**
- Meeting Overview with purpose, objectives, and expected outcomes
- Participant List with roles and responsibilities
- Structured Agenda with time allocations and discussion topics
- Key Discussion Points with decisions and rationale
- Action Items with clear ownership, deadlines, and deliverables
- Decision Log with outcomes and supporting information
- Follow-up Requirements and next steps

**Business Standards:**
- Use humanized, conversational language that captures the natural flow of discussion and decisions
- Include specific decisions and assigned responsibilities with context that makes sense to participants
- Structure for easy reference and follow-up tracking that feels like a natural meeting summary
- Maintain professional yet conversational tone suitable for organizational records that people actually read
""",

    'DOCUMENTATION': """
**Documentation Context:**
- Focus on knowledge transfer, process documentation, and reference materials
- Provide clear explanations, procedures, and guidelines
- Structure for easy comprehension and future reference
- Adapt content for different documentation types: General Documentation or Release Notes

**Key Elements to Include:**
- Document Purpose and scope definition
- Target Audience identification and knowledge prerequisites
- Step-by-Step Instructions or procedures with clear workflows
- Key Concepts and terminology definitions
- Best Practices and guidelines for implementation
- Release Highlights, changes, and version information (for Release Notes template)
- Troubleshooting section with common issues and solutions
- Reference Materials and additional resources

**Business Standards:**
- Use humanized, conversational language that explains concepts like you're teaching a friend or colleague
- Include visual aids, diagrams, and screenshots where helpful with friendly, practical guidance
- Structure for logical flow and easy navigation that feels intuitive and user-friendly
- Maintain professional yet approachable tone appropriate for technical documentation that invites learning
- For Release Notes: Use engaging, highlight-focused language that celebrates achievements and improvements
""",

    'KB': """
**Knowledge Base Context:**
- Focus on quick access information, frequently asked questions, and problem-solving
- Provide concise, searchable content for immediate reference
- Structure for rapid information retrieval and self-service

**Key Elements to Include:**
- Question-Answer Format for common inquiries
- Quick Reference Guides for standard procedures
- Troubleshooting Steps for common technical issues
- Best Practices and tips for efficient workflows
- Glossary of Terms for quick definitions
- Related Articles and cross-references

**Business Standards:**
- Use humanized, conversational language that's friendly and reassuring, like helping a colleague in need
- Include search-friendly keywords and clear categorization that makes finding information effortless
- Structure for easy browsing and information discovery that feels like natural conversation
- Maintain helpful, supportive tone for user assistance that builds confidence and reduces frustration
"""
}
