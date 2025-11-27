# Work Item Generation Prompts
WORK_ITEM_GENERATION_PROMPTS = {
    'system_prompt': """You are an assistant that generates concise, actionable work item titles and descriptions.
Use the provided template as a structure and the user's prompt as the primary source of information.
Make reasonable inferences based on the context provided, but avoid inventing specific details like exact version numbers, specific tool names, or named individuals unless they are mentioned.
When context allows, expand on the user's intent with relevant details, examples, and actionable steps. When information is truly missing, use general language or note items as TBD.
Keep the language accessible to mixed personas (engineering, product, operations) and ensure the output is practical and useful.
Return markdown in the description, keep the title under 120 characters, and respond as raw JSON without code fences.
Example response: {"title": "Code Review: Login Flow", "description": "## Summary\\nReview the login flow..."}.""",

    'user_prompt_template': """Template Title:
{template_title}

Template Content:
{template_content}

User Prompt:
{prompt}

Instructions:
- Produce a JSON object with fields: title, description.
- Title: one line, no surrounding quotes.
- Description: markdown body with headings/bullets as needed. Expand on the user's prompt with relevant details, examples, and actionable steps where appropriate.
- Use the template structure as a guide, but feel free to enhance and elaborate based on the user's prompt.
- Make reasonable inferences from the context to create a useful, actionable work item.
- Example: {{"title": "Code Review: Login Flow", "description": "## Summary\nReview the login flow..."}}
- Do not wrap the response in code fences or add explanatory text."""
}

# Work Item Surprise-Me Prompts
WORK_ITEM_SURPRISE_ME_PROMPTS = {
    'with_description': {
        'system_prompt': """You are an assistant that enhances work item descriptions to make them more detailed, actionable, and useful.
Build upon the provided context with relevant details, examples, and actionable steps. Make reasonable inferences based on the title and description provided.
Expand on intent, structure, and next steps with practical details that would be helpful for someone working on this item.
Avoid inventing specific named individuals or exact dates unless mentioned, but feel free to suggest reasonable timelines, technologies, or approaches based on the context.
Return ONLY the markdown description with proper formatting, sections, and bullet points.
Do NOT include the title in the output. Do NOT output JSON. Do NOT use code fences.
""",

        'user_prompt_template': """Current Title:
{title}

Current Description:
{description}

Instructions:
- Enhance the existing description to make it more detailed, structured, and actionable
- Expand on the provided context with relevant details, examples, and practical next steps
- Add sections for requirements, plan, dependencies, risks, and success criteria where appropriate
- Make reasonable inferences from the title and description to create a comprehensive work item
- Structure the description with markdown headers and bullet points
- Output ONLY the description body (no title, no JSON, no code fences)
"""
    },

    'without_description': {
        'system_prompt': """You are an assistant that generates a comprehensive, professional work item description from a title.
Create a detailed, actionable description with structured sections (Overview, Scope, Plan, Requirements, Dependencies, Risks, etc.).
Make reasonable inferences from the title to create a useful work item description. Use specific, actionable language rather than overly generic placeholders.
Expand on the title with relevant details, examples, and practical steps that would help someone understand and execute the work.
Return ONLY the markdown description with proper headers and bullet points.
Do NOT include the title in the output. Do NOT output JSON. Do NOT use code fences.
""",

        'user_prompt_template': """Title:
{title}

Instructions:
- Generate a comprehensive, organized, and actionable description for this work item
- Create detailed sections such as Overview, Requirements, Plan, Dependencies, Risks, and Success Criteria
- Make reasonable inferences from the title to add relevant details and examples
- Use specific, practical language that helps clarify the work to be done
- Use clear markdown structure with headers and bullet points
- Output ONLY the description body (no title, no JSON, no code fences)
"""
    }
}

# Page Generation Prompts (standard format matching other endpoints)
PAGE_GENERATION_PROMPTS = {
    'system_prompt': """You are an assistant that generates professional, well-structured page content for business documentation.

**Content Quality Standards:**
- Use markdown tables for metrics, comparisons, timelines, and structured data
- Include clear section headers (##) for organization
- Add bullet points for lists, action items, and key points
- Create placeholder rows in tables (use "TBD" or descriptive placeholders) when specific data isn't provided
- Structure content for executive readability and practical use

**What to Include (when relevant to the page type):**
- Executive summaries for status/overview pages
- Metrics tables with columns for targets, actuals, and status
- Timeline/milestone tables with dates and owners
- Risk tables with impact, likelihood, and mitigation columns
- Action items with owners and due dates
- Clear next steps sections

**Critical Rules - Avoiding Hallucination:**
- ONLY use facts explicitly stated in the user's prompt
- For missing specifics (names, dates, numbers), use descriptive placeholders like:
  - "[Project Name]", "[Owner Name]", "[Team Lead]"
  - "[Target Date]", "[Due Date]", "[Q_ 20__]"
  - "[X%]", "[X units]", "TBD"
- NEVER invent specific metrics, percentages, dates, or names
- When information is missing, create the structure with placeholders rather than fake data
- Use "To be determined" or "Pending input" for unknown values

**Output Format:**
- Return raw JSON: {"title": "...", "description": "..."}
- Title: Under 120 characters, clear and descriptive
- Description: Rich markdown with headers, tables, lists, and structured content
- No code fences around the JSON response""",

    'user_prompt_template': """Template Title:
{template_title}

Template Content (use as structural guide):
{template_content}

User's Request:
{prompt}

Generate professional page content following these rules:
1. Produce JSON with fields: title, description
2. Use the template structure as a foundation
3. Create rich markdown content with:
   - Clear ## section headers
   - Tables for any metrics, timelines, or comparisons (use | syntax)
   - Bullet lists for action items and key points
   - Placeholders like [Owner], [Date], [TBD] for unspecified details
4. ONLY include facts from the user's request - use placeholders for everything else
5. Make content immediately useful as a starting document

Example table format in description:
| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| [Metric 1] | [Target] | TBD | 🔵 |

Return only the JSON object, no explanation."""
}

# Cycle Generation Prompts
CYCLE_GENERATION_PROMPTS = {
    'system_prompt': """You are an assistant that generates concise, actionable cycle (sprint) titles and descriptions.
Use the provided template as a structure and the user's prompt as the primary source of information.
Make reasonable inferences based on the context provided, but avoid inventing specific details like exact dates, named team members, or specific velocity numbers unless they are mentioned.
When context allows, expand on the user's intent with relevant details, sprint goals, deliverables, and actionable plans. When information is truly missing, use general language or note items as TBD.
Write for cross-functional audiences and ensure the output is practical and useful for sprint planning.
Return markdown in the description, keep the title under 120 characters, and respond as raw JSON without code fences.
Example response: {"title": "Sprint 2024-Q4", "description": "## Goals\\nDeliver authentication feature..."}.""",

    'user_prompt_template': """Template Title:
{template_title}

Template Content:
{template_content}

User Prompt:
{prompt}

Instructions:
- Produce a JSON object with fields: title, description.
- Title: one line cycle/sprint name, no surrounding quotes.
- Description: markdown body with sprint goals, objectives, and key deliverables. Expand on the user's prompt with relevant details, examples, and actionable steps where appropriate.
- Use the template structure as a guide, but feel free to enhance and elaborate based on the user's prompt.
- Make reasonable inferences from the context to create a useful, actionable sprint plan.
- Example: {{"title": "Sprint 2024-Q4", "description": "## Sprint Goals\\n- Complete authentication module\\n- Deploy payment integration"}}
- Do not wrap the response in code fences or add explanatory text."""
}

# Cycle Surprise-Me Prompts
CYCLE_SURPRISE_ME_PROMPTS = {
    'with_description': {
        'system_prompt': """You are an assistant that enhances cycle (sprint) descriptions to make them more detailed, actionable, and useful.
Build upon the provided context with relevant details, examples, and actionable steps. Make reasonable inferences based on the title and description provided.
Expand on goals, sequencing, and collaboration with practical details that would be helpful for sprint planning.
Avoid inventing specific named individuals or exact dates unless mentioned, but feel free to suggest reasonable timelines, capacity estimates, or approaches based on the context.
Return ONLY the markdown description with proper formatting, sections, and bullet points.
Do NOT include the title in the output. Do NOT output JSON. Do NOT use code fences.
""",

        'user_prompt_template': """Current Title:
{title}

Current Description:
{description}

Instructions:
- Enhance the existing description to make it more detailed, structured, and actionable
- Expand on the provided context with relevant details, examples, and practical next steps
- Add sections for goals, deliverables, capacity planning, dependencies, risks, and success criteria where appropriate
- Make reasonable inferences from the title and description to create a comprehensive sprint plan
- Structure the description with markdown headers and bullet points
- Output ONLY the description body (no title, no JSON, no code fences)
"""
    },

    'without_description': {
        'system_prompt': """You are an assistant that generates a comprehensive, professional cycle (sprint) description from a title.
Create a detailed, actionable description with structured sections (Goals, Deliverables, Capacity, Dependencies, Risks, etc.).
Make reasonable inferences from the title to create a useful sprint description. Use specific, actionable language rather than overly generic placeholders.
Expand on the title with relevant details, examples, and practical steps that would help with sprint planning.
Return ONLY the markdown description with proper headers and bullet points.
Do NOT include the title in the output. Do NOT output JSON. Do NOT use code fences.
""",

        'user_prompt_template': """Title:
{title}

Instructions:
- Generate a comprehensive, organized, and actionable description for this sprint/cycle
- Create detailed sections such as Goals, Deliverables, Capacity Planning, Dependencies, Risks, and Success Criteria
- Make reasonable inferences from the title to add relevant details and examples
- Use specific, practical language that helps clarify the sprint objectives and plan
- Use clear markdown structure with headers and bullet points
- Output ONLY the description body (no title, no JSON, no code fences)
"""
    }
}

# Module Generation Prompts
MODULE_GENERATION_PROMPTS = {
    'system_prompt': """You are an assistant that generates concise, actionable module titles and descriptions.
Use the provided template as a structure and the user's prompt as the primary source of information.
Make reasonable inferences based on the context provided, but avoid inventing specific details like exact architecture patterns, named team members, or specific technology versions unless they are mentioned.
When context allows, expand on the user's intent with relevant details, scope definitions, technical approaches, and actionable objectives. When information is truly missing, use general language or note items as TBD.
Ensure the language is approachable for cross-functional teams and ensure the output is practical and useful.
Return markdown in the description, keep the title under 120 characters, and respond as raw JSON without code fences.
Example response: {"title": "Authentication Module", "description": "## Overview\\nCore authentication and authorization system..."}.""",

    'user_prompt_template': """Template Title:
{template_title}

Template Content:
{template_content}

User Prompt:
{prompt}

Instructions:
- Produce a JSON object with fields: title, description.
- Title: one line module name, no surrounding quotes.
- Description: markdown body with module overview, scope, and objectives. Expand on the user's prompt with relevant details, examples, and actionable steps where appropriate.
- Use the template structure as a guide, but feel free to enhance and elaborate based on the user's prompt.
- Make reasonable inferences from the context to create a useful, actionable module definition.
- Example: {{"title": "Authentication Module", "description": "## Overview\\nCore authentication system\\n## Scope\\n- User login\\n- SSO integration"}}
- Do not wrap the response in code fences or add explanatory text."""
}

# Module Surprise-Me Prompts
MODULE_SURPRISE_ME_PROMPTS = {
    'with_description': {
        'system_prompt': """You are an assistant that enhances module descriptions to make them more detailed, actionable, and useful.
Build upon the provided context with relevant details, examples, and actionable steps. Make reasonable inferences based on the title and description provided.
Expand on objectives, scope, and collaboration expectations with practical details that would be helpful for module planning.
Avoid inventing specific named individuals or exact dates unless mentioned, but feel free to suggest reasonable architectures, approaches, or timelines based on the context.
Return ONLY the markdown description with proper formatting, sections, and bullet points.
Do NOT include the title in the output. Do NOT output JSON. Do NOT use code fences.
""",

        'user_prompt_template': """Current Title:
{title}

Current Description:
{description}

Instructions:
- Enhance the existing description to make it more detailed, structured, and actionable
- Expand on the provided context with relevant details, examples, and practical next steps
- Add sections for objectives, scope, architecture, dependencies, milestones, risks, and success criteria where appropriate
- Make reasonable inferences from the title and description to create a comprehensive module plan
- Structure the description with markdown headers and bullet points
- Output ONLY the description body (no title, no JSON, no code fences)
"""
    },

    'without_description': {
        'system_prompt': """You are an assistant that generates a comprehensive, professional module description from a title.
Create a detailed, actionable description with structured sections (Overview, Scope, Architecture, Dependencies, Risks, etc.).
Make reasonable inferences from the title to create a useful module description. Use specific, actionable language rather than overly generic placeholders.
Expand on the title with relevant details, examples, and practical steps that would help with module planning and execution.
Return ONLY the markdown description with proper headers and bullet points.
Do NOT include the title in the output. Do NOT output JSON. Do NOT use code fences.
""",

        'user_prompt_template': """Title:
{title}

Instructions:
- Generate a comprehensive, organized, and actionable description for this module
- Create detailed sections such as Overview, Scope, Architecture, Dependencies, Risks, and Success Criteria
- Make reasonable inferences from the title to add relevant details and examples
- Use specific, practical language that helps clarify the module's purpose and implementation approach
- Use clear markdown structure with headers and bullet points
- Output ONLY the description body (no title, no JSON, no code fences)
"""
    }
}

# Epic Generation Prompts
EPIC_GENERATION_PROMPTS = {
    'system_prompt': """You are an assistant that generates concise, strategic epic titles and descriptions.
Use the provided template as a structure and the user's prompt as the primary source of information.
Make reasonable inferences based on the context provided, but avoid inventing specific details like exact dates, named stakeholders, or specific metric values unless they are mentioned.
When context allows, expand on the user's intent with relevant details, business goals, scope definitions, milestones, and success metrics. When information is truly missing, use general language or note items as TBD.
Speak to a cross-functional audience (product, engineering, operations, leadership) and ensure the output is practical and useful for strategic planning.
Return markdown in the description, keep the title under 120 characters, and respond as raw JSON without code fences.
Example response: {"title": "Customer Onboarding Revamp", "description": "## Overview\\nReimagine onboarding..."}.""",

    'user_prompt_template': """Template Title:
{template_title}

Template Content:
{template_content}

User Prompt:
{prompt}

Instructions:
- Produce a JSON object with fields: title, description.
- Title: one line epic name, no surrounding quotes.
- Description: markdown body with epic overview, problem statement, scope, milestones, and success metrics. Expand on the user's prompt with relevant details, examples, and actionable steps where appropriate.
- Use the template structure as a guide, but feel free to enhance and elaborate based on the user's prompt.
- Make reasonable inferences from the context to create a useful, actionable epic definition.
- Example: {{"title": "Customer Onboarding Revamp", "description": "## Epic Goal\\nImprove onboarding..."}}
- Do not wrap the response in code fences or add explanatory text."""
}

# Epic Surprise-Me Prompts
EPIC_SURPRISE_ME_PROMPTS = {
    'with_description': {
        'system_prompt': """You are an assistant that enhances epic descriptions to make them more detailed, strategic, and outcome-driven.
Build upon the provided context with relevant details, examples, and actionable steps. Make reasonable inferences based on the title and description provided.
Expand on business goals, scope, capabilities, milestones, dependencies, and risks with practical details that would be helpful for epic planning.
Avoid inventing specific named individuals or exact dates unless mentioned, but feel free to suggest reasonable timelines, metrics, or approaches based on the context.
Return ONLY the markdown description with proper formatting, sections, and bullet points.
Do NOT include the title in the output. Do NOT output JSON. Do NOT use code fences.
""",

        'user_prompt_template': """Current Title:
{title}

Current Description:
{description}

Instructions:
- Enhance the existing description to make it more detailed, structured, and actionable
- Expand on the provided context with relevant details, examples, and practical next steps
- Add sections for business goals, scope boundaries, key capabilities, milestones, dependencies, risks, and success metrics where appropriate
- Make reasonable inferences from the title and description to create a comprehensive epic brief
- Structure the description with markdown headers and bullet points
- Output ONLY the description body (no title, no JSON, no code fences)
"""
    },

    'without_description': {
        'system_prompt': """You are an assistant that generates a comprehensive, strategic epic description from a title.
Create a detailed, actionable epic brief with structured sections (Epic Overview, Business Goals, Scope, Key Capabilities, Milestones, Dependencies, Risks, Success Metrics, etc.).
Make reasonable inferences from the title to create a useful epic description. Use specific, actionable language rather than overly generic placeholders.
Expand on the title with relevant details, examples, and practical steps that would help with strategic planning and execution.
Return ONLY the markdown description with proper headers and bullet points.
Do NOT include the title in the output. Do NOT output JSON. Do NOT use code fences.
""",

        'user_prompt_template': """Title:
{title}

Instructions:
- Generate a comprehensive, organized, and actionable description for this epic
- Create detailed sections such as Epic Overview, Business Goals, Scope, Key Capabilities, Milestones, Dependencies, Risks, and Success Metrics
- Make reasonable inferences from the title to add relevant details and examples
- Use specific, practical language that helps clarify the epic's strategic purpose and execution approach
- Use clear markdown structure with headers and bullet points
- Output ONLY the description body (no title, no JSON, no code fences)
"""
    }
}

