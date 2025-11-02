import json
import re
from typing import List, Dict, Any, Optional, Tuple
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

import os
from dotenv import load_dotenv
load_dotenv()

from .prompts import (
    WORK_ITEM_TEMPLATE_PROMPT,
    PAGE_TEMPLATE_PROMPT,
    CYCLE_TEMPLATE_PROMPT,
    MODULE_TEMPLATE_PROMPT,
    EPIC_TEMPLATE_PROMPT
)

SCENARIO_LIBRARY: Dict[str, List[Dict[str, Any]]] = {
    "work_item": [
        {
            "key": "legacy-refactor",
            "id_prefix": "work-item-legacy-refactor",
            "name": "Legacy Refactor Work Item",
            "emoji": "??",
            "default_priority": "High",
            "description": "Modernize outdated code and align it with current standards.",
            "title_label": "Legacy Refactor: [Component or Domain]",
            "keywords": ["legacy", "refactor", "tech debt", "cleanup", "modernize", "rewrite"],
            "sections": [
                {"heading": "Scope Baseline", "todo": "Identify legacy components to refactor"},
                {"heading": "Impacted Areas", "todo": "List services, modules, or user flows affected"},
                {"heading": "Refactor Checklist", "todo": "Outline modernization tasks and acceptance criteria"},
                {"heading": "Risk Controls", "todo": "Document safeguards, backups, and review steps"},
                {"heading": "Validation Steps", "todo": "Specify tests, benchmarks, and approval gates"},
            ],
        },
        {
            "key": "performance-optimization",
            "id_prefix": "work-item-performance-optimization",
            "name": "Performance Optimization Work Item",
            "emoji": "?",
            "default_priority": "High",
            "description": "Reduce latency or resource usage for a targeted capability.",
            "title_label": "Performance Optimization: [Service or Flow]",
            "keywords": ["performance", "latency", "throughput", "optimiz", "tuning", "slowness", "speed"],
            "sections": [
                {"heading": "Performance Issue Summary", "todo": "Capture baseline metrics and pain points"},
                {"heading": "Target Metrics", "todo": "Define desired performance thresholds"},
                {"heading": "Optimization Plan", "todo": "List tuning or refactor activities"},
                {"heading": "Benchmark Strategy", "todo": "Describe measurement approach and tools"},
                {"heading": "Rollout & Monitoring", "todo": "Plan deployment, observation, and rollback cues"},
            ],
        },
        {
            "key": "test-coverage",
            "id_prefix": "work-item-test-coverage",
            "name": "Test Coverage Expansion Work Item",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Increase automated confidence in risky areas of the codebase.",
            "title_label": "Test Coverage Expansion: [Area or Suite]",
            "keywords": ["test", "coverage", "qa", "automation", "unit", "integration", "regression"],
            "sections": [
                {"heading": "Coverage Gap", "todo": "Document current gaps and defect history"},
                {"heading": "Test Design", "todo": "Outline planned test types and scenarios"},
                {"heading": "Environments & Data", "todo": "Specify datasets, fixtures, and platform needs"},
                {"heading": "Success Criteria", "todo": "Define pass thresholds and reporting expectations"},
                {"heading": "Follow-up Tasks", "todo": "Capture ownership, timelines, and next checks"},
            ],
        },
        {
            "key": "security-hardening",
            "id_prefix": "work-item-security-hardening",
            "name": "Security Hardening Work Item",
            "emoji": "??",
            "default_priority": "High",
            "description": "Patch vulnerabilities and reinforce defenses for sensitive surfaces.",
            "title_label": "Security Hardening: [Surface or Service]",
            "keywords": ["security", "vulnerability", "cve", "penetration", "compliance", "hardening"],
            "sections": [
                {"heading": "Vulnerability Summary", "todo": "Record issues, CVEs, or audit findings"},
                {"heading": "Attack Surface", "todo": "Map affected components and entry points"},
                {"heading": "Mitigation Actions", "todo": "Detail fixes, configuration changes, or tooling updates"},
                {"heading": "Validation Steps", "todo": "Describe testing, scanning, and sign-off procedures"},
                {"heading": "Compliance Notes", "todo": "Capture regulatory, policy, or documentation needs"},
            ],
        },
        {
            "key": "dependency-upgrade",
            "id_prefix": "work-item-dependency-upgrade",
            "name": "Dependency Upgrade Work Item",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Update libraries, frameworks, or tooling safely.",
            "title_label": "Dependency Upgrade: [Package or Stack]",
            "keywords": ["dependency", "upgrade", "library", "package", "version", "framework"],
            "sections": [
                {"heading": "Upgrade Scope", "todo": "List dependencies and versions to change"},
                {"heading": "Breaking Changes", "todo": "Note incompatibilities and mitigation steps"},
                {"heading": "Validation Plan", "todo": "Plan automated and manual testing coverage"},
                {"heading": "Deployment Steps", "todo": "Outline rollout approach and sequencing"},
                {"heading": "Post-Upgrade Monitoring", "todo": "Define dashboards, alerts, and rollback triggers"},
            ],
        },
        {
            "key": "database-optimization",
            "id_prefix": "work-item-database-optimization",
            "name": "Database Optimization Work Item",
            "emoji": "???",
            "default_priority": "Medium",
            "description": "Improve data access patterns and storage performance.",
            "title_label": "Database Optimization: [Table or Query]",
            "keywords": ["database", "query", "sql", "index", "storage", "latency"],
            "sections": [
                {"heading": "Current Bottleneck", "todo": "Describe slow queries or capacity constraints"},
                {"heading": "Target Improvement", "todo": "Define measurable goals and SLAs"},
                {"heading": "Planned Changes", "todo": "Detail schema, index, or query adjustments"},
                {"heading": "Testing Strategy", "todo": "Plan sampling, load testing, and validation steps"},
                {"heading": "Monitoring Signals", "todo": "Track metrics, alerts, and follow-up reviews"},
            ],
        },
        {
            "key": "documentation-cleanup",
            "id_prefix": "work-item-documentation-cleanup",
            "name": "Documentation Cleanup Work Item",
            "emoji": "??",
            "default_priority": "Low",
            "description": "Refresh onboarding or operational knowledge bases.",
            "title_label": "Documentation Cleanup: [Guide or Area]",
            "keywords": ["documentation", "docs", "knowledge", "guide", "playbook", "runbook"],
            "sections": [
                {"heading": "Current Issues", "todo": "List outdated sections and known gaps"},
                {"heading": "Target Audience", "todo": "Describe who relies on this documentation"},
                {"heading": "Update Tasks", "todo": "Outline rewrite, review, and approval steps"},
                {"heading": "Review & Approval", "todo": "Assign reviewers and acceptance criteria"},
                {"heading": "Publishing Plan", "todo": "Plan release, communication, and follow-ups"},
            ],
        },
        {
            "key": "pipeline-maintenance",
            "id_prefix": "work-item-pipeline-maintenance",
            "name": "Build Pipeline Maintenance Work Item",
            "emoji": "???",
            "default_priority": "Medium",
            "description": "Stabilize CI/CD workflows and supporting tooling.",
            "title_label": "Pipeline Maintenance: [Pipeline or Stage]",
            "keywords": ["pipeline", "ci", "cd", "build", "deploy", "workflow"],
            "sections": [
                {"heading": "Pipeline Baseline", "todo": "Capture current state, failures, and SLAs"},
                {"heading": "Pain Points", "todo": "Detail flakiness, bottlenecks, or missing guardrails"},
                {"heading": "Remediation Tasks", "todo": "List fixes, improvements, or tooling updates"},
                {"heading": "Verification Strategy", "todo": "Define dry runs, test plans, and validation gates"},
                {"heading": "Success Signals", "todo": "Track metrics, alerts, and follow-up checkpoints"},
            ],
        },
    ],
    "page": [
        {
            "key": "project-status",
            "id_prefix": "page-project-status",
            "name": "Project Status Page",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Executive snapshot of progress, KPIs, and risks.",
            "title_label": "Project Status: [Project or Program]",
            "keywords": ["status", "summary", "progress", "executive", "kpi", "dashboard"],
            "sections": [
                {"heading": "Summary Highlights", "todo": "Capture overall status and headline updates"},
                {"heading": "KPI Dashboard", "todo": "List critical metrics and current values"},
                {"heading": "Milestones & Deliverables", "todo": "Detail upcoming and completed milestones"},
                {"heading": "Risks & Blockers", "todo": "Document risks, blockers, and mitigation owners"},
                {"heading": "Decisions & Approvals", "todo": "Record pending or completed decisions"},
                {"heading": "Next Actions", "todo": "Outline immediate follow-ups and owners"},
            ],
        },
        {
            "key": "task-specification",
            "id_prefix": "page-task-specification",
            "name": "Task Specification Page",
            "emoji": "??",
            "default_priority": "High",
            "description": "Detailed breakdown of a single feature or task.",
            "title_label": "Task Specification: [Task or Feature]",
            "keywords": ["spec", "specification", "task", "feature", "requirement", "acceptance"],
            "sections": [
                {"heading": "Task Overview", "todo": "Describe the purpose and scope"},
                {"heading": "Requirements", "todo": "List functional and non-functional needs"},
                {"heading": "Dependencies", "todo": "Identify cross-team or technical dependencies"},
                {"heading": "Implementation Notes", "todo": "Capture design, architecture, or constraints"},
                {"heading": "Testing Strategy", "todo": "Define validation approach and coverage"},
                {"heading": "Rollout Plan", "todo": "Outline release plan, comms, and guardrails"},
            ],
        },
        {
            "key": "meeting-notes",
            "id_prefix": "page-meeting-notes",
            "name": "Meeting Notes Page",
            "emoji": "??",
            "default_priority": "Low",
            "description": "Capture agenda, outcomes, and follow-ups.",
            "title_label": "Meeting Notes: [Meeting Name]",
            "keywords": ["meeting", "notes", "agenda", "discussion", "minutes"],
            "sections": [
                {"heading": "Meeting Overview", "todo": "State purpose, date, and facilitator"},
                {"heading": "Attendees & Roles", "todo": "List participants and responsibilities"},
                {"heading": "Agenda Topics", "todo": "Record topics covered"},
                {"heading": "Discussion Notes", "todo": "Summarize key points and insights"},
                {"heading": "Decisions Made", "todo": "Capture outcomes and rationales"},
                {"heading": "Action Items", "todo": "Log tasks, owners, and due dates"},
            ],
        },
        {
            "key": "documentation-hub",
            "id_prefix": "page-documentation-hub",
            "name": "Documentation Hub Page",
            "emoji": "??",
            "default_priority": "Low",
            "description": "Reference documentation or how-to guide.",
            "title_label": "Documentation Hub: [Topic or System]",
            "keywords": ["documentation", "guide", "how-to", "reference", "manual"],
            "sections": [
                {"heading": "Purpose & Scope", "todo": "Explain what this documentation covers"},
                {"heading": "Target Audience", "todo": "Describe who should use this resource"},
                {"heading": "Content Structure", "todo": "Outline sections or navigation"},
                {"heading": "Key Procedures", "todo": "Detail critical processes or steps"},
                {"heading": "Resources & Links", "todo": "List supporting materials and references"},
                {"heading": "Review Cadence", "todo": "Define update frequency and owners"},
            ],
        },
        {
            "key": "knowledge-base",
            "id_prefix": "page-knowledge-base",
            "name": "Knowledge Base Article",
            "emoji": "??",
            "default_priority": "Low",
            "description": "Self-service troubleshooting or FAQ.",
            "title_label": "Knowledge Base: [Topic or Issue]",
            "keywords": ["knowledge", "faq", "troubleshoot", "support", "article"],
            "sections": [
                {"heading": "Audience & Use Case", "todo": "Identify who encounters this issue"},
                {"heading": "Problem Statement", "todo": "Describe symptoms or triggers"},
                {"heading": "Resolution Steps", "todo": "Enumerate steps to resolve the issue"},
                {"heading": "Troubleshooting Tips", "todo": "Provide variations, warnings, or checks"},
                {"heading": "Escalation Path", "todo": "Define next steps if unresolved"},
                {"heading": "Revision History", "todo": "Track updates and authors"},
            ],
        },
        {
            "key": "release-notes",
            "id_prefix": "page-release-notes",
            "name": "Release Notes Page",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Communicate release changes and impacts.",
            "title_label": "Release Notes: [Version or Date]",
            "keywords": ["release", "notes", "version", "launch", "changelog"],
            "sections": [
                {"heading": "Release Overview", "todo": "Summarize release scope and goals"},
                {"heading": "Feature Highlights", "todo": "Highlight marquee additions"},
                {"heading": "Fixes & Improvements", "todo": "List resolved issues or enhancements"},
                {"heading": "Known Issues", "todo": "Document existing limitations"},
                {"heading": "Upgrade Guidance", "todo": "Provide rollout or upgrade instructions"},
                {"heading": "Support Contacts", "todo": "Note support channels and ownership"},
            ],
        },
        {
            "key": "risk-register",
            "id_prefix": "page-risk-register",
            "name": "Risk Register Page",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Track risks, mitigations, and ownership.",
            "title_label": "Risk Register: [Program or Team]",
            "keywords": ["risk", "mitigation", "register", "blocker", "issue"],
            "sections": [
                {"heading": "Risk Overview", "todo": "Summarize risk posture and scope"},
                {"heading": "High Impact Risks", "todo": "List top risks with impact ratings"},
                {"heading": "Mitigation Strategies", "todo": "Capture plans to reduce likelihood or impact"},
                {"heading": "Owners & Deadlines", "todo": "Assign responsibilities and timelines"},
                {"heading": "Monitoring Activities", "todo": "Describe tracking, triggers, and reviews"},
                {"heading": "Notes & Updates", "todo": "Record latest updates or decisions"},
            ],
        },
        {
            "key": "okr-summary",
            "id_prefix": "page-okr-summary",
            "name": "OKR Summary Page",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Summarize objectives, key results, and progress.",
            "title_label": "OKR Summary: [Cycle or Team]",
            "keywords": ["okr", "objective", "key result", "progress", "goal"],
            "sections": [
                {"heading": "Objective Overview", "todo": "Describe the objective and intent"},
                {"heading": "Key Results & Metrics", "todo": "List KRs with targets and actuals"},
                {"heading": "Progress Updates", "todo": "Highlight achievements and blockers"},
                {"heading": "Supporting Initiatives", "todo": "Outline projects contributing to the KRs"},
                {"heading": "Risks & Blockers", "todo": "Call out threats to completion"},
                {"heading": "Next Steps", "todo": "Detail upcoming work and owners"},
            ],
        },
    ],
    "cycle": [
        {
            "key": "foundational-development",
            "id_prefix": "cycle-foundational-development",
            "name": "Foundational Development Cycle",
            "emoji": "???",
            "default_priority": "High",
            "description": "Establish core infrastructure, tooling, and architecture baselines.",
            "title_label": "Foundational Cycle: [Cycle Name]",
            "keywords": ["foundation", "setup", "bootstrap", "infrastructure", "baseline"],
            "sections": [
                {"heading": "Cycle Mission", "todo": "Capture the foundational objectives and scope"},
                {"heading": "Technical Foundations", "todo": "List platforms, services, or components to establish"},
                {"heading": "Environment Setup", "todo": "Define environments, tooling, and access requirements"},
                {"heading": "Planned Deliverables", "todo": "Enumerate artifacts or capabilities due by cycle end"},
                {"heading": "Risk Watchlist", "todo": "Surface key risks, blockers, and mitigations"},
                {"heading": "Exit Criteria", "todo": "Document measurable completion checks"},
            ],
        },
        {
            "key": "feature-delivery",
            "id_prefix": "cycle-feature-delivery",
            "name": "Feature Delivery Cycle",
            "emoji": "??",
            "default_priority": "High",
            "description": "Deliver scoped user-facing functionality end to end.",
            "title_label": "Feature Cycle: [Cycle Name]",
            "keywords": ["feature", "delivery", "sprint", "ship", "story"],
            "sections": [
                {"heading": "Feature Goals", "todo": "Summarize user problems and desired outcomes"},
                {"heading": "Backlog Scope", "todo": "List prioritized work items in scope"},
                {"heading": "Design Alignment", "todo": "Note design, product, and stakeholder agreements"},
                {"heading": "Build Plan", "todo": "Lay out implementation phases and owners"},
                {"heading": "QA Strategy", "todo": "Define testing coverage and acceptance criteria"},
                {"heading": "Demo & Release Prep", "todo": "Plan demonstrations, launch tasks, and documentation"},
            ],
        },
        {
            "key": "stabilization-testing",
            "id_prefix": "cycle-stabilization-testing",
            "name": "Stabilization & Testing Cycle",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Drive quality, regression coverage, and bug resolution.",
            "title_label": "Stabilization Cycle: [Cycle Name]",
            "keywords": ["stabilization", "testing", "qa", "regression", "bug"],
            "sections": [
                {"heading": "Stability Objectives", "todo": "Capture quality goals and targeted issue areas"},
                {"heading": "Regression Scope", "todo": "List products, flows, or platforms in coverage"},
                {"heading": "Bug Triage Plan", "todo": "Define severity handling and prioritization rules"},
                {"heading": "Test Coverage Plan", "todo": "Outline manual and automated validation approach"},
                {"heading": "Release Readiness", "todo": "Summarize exit gates, sign-offs, and documentation"},
                {"heading": "Post-Cycle Monitoring", "todo": "Define follow-up metrics and observation windows"},
            ],
        },
        {
            "key": "performance-optimization",
            "id_prefix": "cycle-performance-optimization",
            "name": "Performance Optimization Cycle",
            "emoji": "?",
            "default_priority": "High",
            "description": "Improve speed, reliability, and efficiency for target workloads.",
            "title_label": "Performance Cycle: [Cycle Name]",
            "keywords": ["performance", "latency", "reliability", "optimization", "scalability"],
            "sections": [
                {"heading": "Performance Targets", "todo": "Specify baseline pain points and target metrics"},
                {"heading": "Profiling Plan", "todo": "Describe tooling, sampling approach, and owners"},
                {"heading": "Optimization Tasks", "todo": "List workstreams and expected impact"},
                {"heading": "Validation Strategy", "todo": "Note benchmarks, load tests, and acceptance criteria"},
                {"heading": "Risk Management", "todo": "Outline rollback plans and dependency constraints"},
                {"heading": "Reporting Cadence", "todo": "Plan status syncs, dashboards, and stakeholders"},
            ],
        },
        {
            "key": "integration-alignment",
            "id_prefix": "cycle-integration-alignment",
            "name": "Integration & Alignment Cycle",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Synchronize modules, teams, and code branches.",
            "title_label": "Integration Cycle: [Cycle Name]",
            "keywords": ["integration", "alignment", "merge", "sync", "coordination"],
            "sections": [
                {"heading": "Integration Goals", "todo": "Clarify integration outcomes and KPIs"},
                {"heading": "Stakeholders & Teams", "todo": "Identify partner teams and communication channels"},
                {"heading": "Coordination Activities", "todo": "Plan sync meetings, checkpoints, and tooling"},
                {"heading": "Merge & Deployment Plan", "todo": "Outline sequencing, environment usage, and safeguards"},
                {"heading": "Dependencies & Risks", "todo": "Capture upstream/downstream constraints"},
                {"heading": "Communication Plan", "todo": "Detail update cadence and artifact sharing"},
            ],
        },
        {
            "key": "feedback-iteration",
            "id_prefix": "cycle-feedback-iteration",
            "name": "Feedback & Iteration Cycle",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Apply stakeholder and user insights to refine deliverables.",
            "title_label": "Iteration Cycle: [Cycle Name]",
            "keywords": ["feedback", "iteration", "refine", "review", "retro"],
            "sections": [
                {"heading": "Feedback Sources", "todo": "List channels, surveys, or research inputs"},
                {"heading": "Prioritized Insights", "todo": "Capture themes and decisions for this cycle"},
                {"heading": "Iteration Plan", "todo": "Outline updates, owners, and timelines"},
                {"heading": "Validation Activities", "todo": "Plan usability tests, pilots, or beta reviews"},
                {"heading": "Stakeholder Updates", "todo": "Define update cadence and audiences"},
                {"heading": "Lessons Learned", "todo": "Note retrospective focus areas"},
            ],
        },
        {
            "key": "security-hardening",
            "id_prefix": "cycle-security-hardening",
            "name": "Security & Hardening Cycle",
            "emoji": "??",
            "default_priority": "High",
            "description": "Address vulnerabilities and improve defenses.",
            "title_label": "Security Cycle: [Cycle Name]",
            "keywords": ["security", "hardening", "vulnerability", "patch", "risk"],
            "sections": [
                {"heading": "Threat Landscape", "todo": "Summarize findings, pen-test results, or alerts"},
                {"heading": "Hardening Tasks", "todo": "Detail remediations, patches, and configurations"},
                {"heading": "Validation Tests", "todo": "Note scans, penetration tests, and code reviews"},
                {"heading": "Compliance Checks", "todo": "Map standards, attestations, or documentation"},
                {"heading": "Incident Preparedness", "todo": "Outline playbooks, drills, or runbooks"},
                {"heading": "Sign-off Requirements", "todo": "Capture approvals and evidence submissions"},
            ],
        },
        {
            "key": "release-preparation",
            "id_prefix": "cycle-release-preparation",
            "name": "Deployment / Release Preparation Cycle",
            "emoji": "??",
            "default_priority": "High",
            "description": "Finalize launch readiness with validation and communication.",
            "title_label": "Release Prep Cycle: [Cycle Name]",
            "keywords": ["release", "deployment", "launch", "go-live", "rollout"],
            "sections": [
                {"heading": "Release Scope", "todo": "Enumerate features and fixes targeted for launch"},
                {"heading": "Readiness Checklist", "todo": "Track docs, training, and approvals needed"},
                {"heading": "Rollout Plan", "todo": "Define launch sequencing, environments, and ownership"},
                {"heading": "Communication Timeline", "todo": "Plan announcements and stakeholder updates"},
                {"heading": "Contingency Plan", "todo": "Describe rollback, hotfix, and support strategies"},
                {"heading": "Final Validation", "todo": "List final tests, sign-offs, and monitoring setup"},
            ],
        },
    ],
    "module": [
        {
            "key": "core-functional",
            "id_prefix": "module-core-functional",
            "name": "Core Functional Module",
            "emoji": "??",
            "default_priority": "High",
            "description": "Deliver a central capability that powers critical system value.",
            "title_label": "Module: [Core Capability]",
            "keywords": ["core", "platform", "foundation", "backbone", "primary"],
            "sections": [
                {"heading": "Mission & Scope", "todo": "Summarize the core problem this module solves"},
                {"heading": "Core Capabilities", "todo": "Enumerate essential features and responsibilities"},
                {"heading": "Primary Personas", "todo": "Identify roles or systems depending on this module"},
                {"heading": "Critical Flows", "todo": "Describe key user or data journeys"},
                {"heading": "Dependencies", "todo": "List upstream/downstream modules or services"},
                {"heading": "Operational Constraints", "todo": "Capture SLAs, compliance, or scaling limits"},
            ],
        },
        {
            "key": "supportive-utility",
            "id_prefix": "module-supportive-utility",
            "name": "Supportive / Utility Module",
            "emoji": "???",
            "default_priority": "Medium",
            "description": "Provide enabling services that other modules rely on.",
            "title_label": "Module: [Utility Service]",
            "keywords": ["utility", "logging", "notification", "shared", "support"],
            "sections": [
                {"heading": "Purpose & Services", "todo": "Explain the utility offered and primary functions"},
                {"heading": "Dependent Modules", "todo": "List consumers and integration expectations"},
                {"heading": "Integration Points", "todo": "Detail APIs, hooks, or messaging contracts"},
                {"heading": "Operational Constraints", "todo": "Document performance, cost, or scaling limits"},
                {"heading": "Reliability & SLAs", "todo": "Capture uptime, alerting, and escalation paths"},
                {"heading": "Maintenance Tasks", "todo": "Outline routine upkeep and ownership"},
            ],
        },
        {
            "key": "data-management",
            "id_prefix": "module-data-management",
            "name": "Data Management Module",
            "emoji": "???",
            "default_priority": "High",
            "description": "Govern how data is collected, stored, processed, and surfaced.",
            "title_label": "Module: [Data Domain]",
            "keywords": ["data", "pipeline", "warehouse", "ingestion", "analytics"],
            "sections": [
                {"heading": "Data Domains", "todo": "Define datasets and business entities covered"},
                {"heading": "Sources & Ingestion", "todo": "Describe inbound feeds, cadence, and validation"},
                {"heading": "Storage Strategy", "todo": "Specify databases, schemas, and retention"},
                {"heading": "Processing Pipelines", "todo": "Summarize transformations, jobs, and tooling"},
                {"heading": "Governance & Quality", "todo": "List stewardship, quality checks, and audits"},
                {"heading": "Access Patterns", "todo": "Detail query, API, or analytics consumption"},
            ],
        },
        {
            "key": "configuration-settings",
            "id_prefix": "module-configuration-settings",
            "name": "Configuration & Settings Module",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Manage customization, preferences, and policy controls.",
            "title_label": "Module: [Configuration Area]",
            "keywords": ["config", "settings", "preference", "toggle", "feature flag"],
            "sections": [
                {"heading": "Personalization Goals", "todo": "Capture why users need configuration flexibility"},
                {"heading": "Configurable Elements", "todo": "List settings, toggles, or feature flags"},
                {"heading": "Permission Model", "todo": "Describe roles, scopes, and constraints"},
                {"heading": "UX Touchpoints", "todo": "Note interfaces where configuration is applied"},
                {"heading": "Audit & Rollback", "todo": "Document change history and rollback strategy"},
                {"heading": "Dependencies", "todo": "Highlight services reacting to configuration changes"},
            ],
        },
        {
            "key": "communication-interaction",
            "id_prefix": "module-communication-interaction",
            "name": "Communication / Interaction Module",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Support user-to-system and user-to-user messaging flows.",
            "title_label": "Module: [Channel or Interface]",
            "keywords": ["communication", "interaction", "messaging", "chat", "notification"],
            "sections": [
                {"heading": "Interaction Goals", "todo": "State the communication outcomes or objectives"},
                {"heading": "Channels & Interfaces", "todo": "List UI surfaces, APIs, or connectors"},
                {"heading": "Message Lifecycle", "todo": "Describe drafting, delivery, and archival steps"},
                {"heading": "Triggers & Events", "todo": "Capture events initiating notifications or messages"},
                {"heading": "Compliance & Privacy", "todo": "Note regulatory needs and data retention"},
                {"heading": "Success Metrics", "todo": "Define engagement or reliability measures"},
            ],
        },
        {
            "key": "automation-workflow",
            "id_prefix": "module-automation-workflow",
            "name": "Automation / Workflow Module",
            "emoji": "??",
            "default_priority": "High",
            "description": "Orchestrate processes that streamline operational steps.",
            "title_label": "Module: [Workflow Name]",
            "keywords": ["automation", "workflow", "orchestrator", "process", "bot"],
            "sections": [
                {"heading": "Workflow Overview", "todo": "Summarize the process and desired outcome"},
                {"heading": "Triggers & Inputs", "todo": "List events or data starting the workflow"},
                {"heading": "Task Orchestration", "todo": "Describe automation steps and decision points"},
                {"heading": "Exception Handling", "todo": "Document fallback paths and manual interventions"},
                {"heading": "Audit & Logging", "todo": "Capture traceability, logging, and storage"},
                {"heading": "Success Metrics", "todo": "Define throughput, accuracy, or time savings"},
            ],
        },
        {
            "key": "monitoring-analytics",
            "id_prefix": "module-monitoring-analytics",
            "name": "Monitoring / Analytics Module",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Provide visibility into system and business performance.",
            "title_label": "Module: [Monitoring Scope]",
            "keywords": ["monitoring", "analytics", "dashboard", "observability", "metrics"],
            "sections": [
                {"heading": "Observability Scope", "todo": "Highlight domains and KPIs tracked"},
                {"heading": "Data Sources", "todo": "Enumerate telemetry, logs, and integrations"},
                {"heading": "Visualization Strategy", "todo": "Describe dashboards, reports, or alerts"},
                {"heading": "Alerting & Thresholds", "todo": "Capture alert logic, severity, and routing"},
                {"heading": "KPIs", "todo": "List metrics, formulas, and targets"},
                {"heading": "Continuous Improvement", "todo": "Plan reviews, backlog, and evolution cadence"},
            ],
        },
        {
            "key": "security-compliance",
            "id_prefix": "module-security-compliance",
            "name": "Security / Compliance Module",
            "emoji": "??",
            "default_priority": "High",
            "description": "Protect data, enforce policies, and support audits.",
            "title_label": "Module: [Protection Scope]",
            "keywords": ["security", "compliance", "policy", "governance", "access"],
            "sections": [
                {"heading": "Security Objectives", "todo": "State confidentiality, integrity, or availability goals"},
                {"heading": "Control Framework", "todo": "Map required standards and control families"},
                {"heading": "Access Model", "todo": "Define authentication, authorization, and roles"},
                {"heading": "Monitoring & Alerts", "todo": "Describe threat detection and response tooling"},
                {"heading": "Incident Response", "todo": "Outline escalation paths and playbooks"},
                {"heading": "Compliance Evidence", "todo": "List reports, attestations, and audit artifacts"},
            ],
        },
    ],
    "epic": [
        {
            "key": "foundational-system",
            "id_prefix": "epic-foundational-system",
            "name": "Foundational System Epic",
            "emoji": "???",
            "default_priority": "High",
            "description": "Build or refactor platform foundations to unlock future capabilities.",
            "title_label": "Epic: [Foundation Initiative]",
            "keywords": ["foundation", "platform", "infrastructure", "core", "refactor"],
            "sections": [
                {"heading": "Vision Statement", "todo": "Describe the long-term platform vision"},
                {"heading": "Strategic Outcomes", "todo": "List measurable results this epic will enable"},
                {"heading": "Architecture Scope", "todo": "Outline systems, services, or layers impacted"},
                {"heading": "Milestones & Phases", "todo": "Break down phases with target timelines"},
                {"heading": "Risk Mitigation", "todo": "Capture technical, resource, and timeline risks"},
                {"heading": "Success Metrics", "todo": "Define signals that prove the foundation is working"},
            ],
        },
        {
            "key": "experience-improvement",
            "id_prefix": "epic-experience-improvement",
            "name": "Experience Improvement Epic",
            "emoji": "?",
            "default_priority": "Medium",
            "description": "Elevate usability, accessibility, and overall satisfaction.",
            "title_label": "Epic: [Experience Initiative]",
            "keywords": ["experience", "ux", "design", "usability", "delight"],
            "sections": [
                {"heading": "Experience Goals", "todo": "Summarize desired user outcomes"},
                {"heading": "Target Segments", "todo": "Identify personas or user cohorts affected"},
                {"heading": "Journey Pain Points", "todo": "Document issues discovered in research or feedback"},
                {"heading": "Design & Content Strategy", "todo": "Outline UX, UI, and messaging approaches"},
                {"heading": "Launch Plan", "todo": "Capture beta, rollout, and training plans"},
                {"heading": "Measurement Framework", "todo": "Define KPIs, surveys, or analytics dashboards"},
            ],
        },
        {
            "key": "scalability-performance",
            "id_prefix": "epic-scalability-performance",
            "name": "Scalability & Performance Epic",
            "emoji": "?",
            "default_priority": "High",
            "description": "Improve system capacity, responsiveness, and stability.",
            "title_label": "Epic: [Performance Initiative]",
            "keywords": ["scalability", "performance", "latency", "capacity", "speed"],
            "sections": [
                {"heading": "Capacity Challenges", "todo": "Describe growth signals or performance incidents"},
                {"heading": "Performance Targets", "todo": "Set target SLAs, throughput, or latency"},
                {"heading": "Technical Approach", "todo": "Summarize architecture, refactors, or tooling"},
                {"heading": "Workstreams", "todo": "Break down coordinated engineering tracks"},
                {"heading": "Risk Management", "todo": "Capture mitigation plans and constraints"},
                {"heading": "Validation Plan", "todo": "Outline benchmarking, load, and resiliency tests"},
            ],
        },
        {
            "key": "security-compliance",
            "id_prefix": "epic-security-compliance",
            "name": "Security & Compliance Epic",
            "emoji": "??",
            "default_priority": "High",
            "description": "Address risk mitigation, policy enforcement, and regulatory adherence.",
            "title_label": "Epic: [Security or Compliance Goal]",
            "keywords": ["security", "compliance", "risk", "policy", "audit"],
            "sections": [
                {"heading": "Compliance Drivers", "todo": "List regulations, standards, or commitments"},
                {"heading": "Scope & Controls", "todo": "Define systems, data, and control families"},
                {"heading": "Implementation Plan", "todo": "Outline workstreams, owners, and timelines"},
                {"heading": "Risk Register", "todo": "Capture threats, impacts, and mitigation owners"},
                {"heading": "Audit Evidence", "todo": "Document artifacts, reports, or attestations"},
                {"heading": "Ongoing Monitoring", "todo": "Describe continuous assurance and alerting"},
            ],
        },
        {
            "key": "operational-efficiency",
            "id_prefix": "epic-operational-efficiency",
            "name": "Operational Efficiency Epic",
            "emoji": "???",
            "default_priority": "Medium",
            "description": "Streamline processes and drive automation across teams.",
            "title_label": "Epic: [Efficiency Initiative]",
            "keywords": ["efficiency", "process", "automation", "workflow", "lean"],
            "sections": [
                {"heading": "Current Inefficiencies", "todo": "Summarize bottlenecks and waste"},
                {"heading": "Automation Opportunities", "todo": "Highlight processes to automate or simplify"},
                {"heading": "Process Changes", "todo": "Detail new flows, RACI updates, or policies"},
                {"heading": "Change Management", "todo": "Plan training, communication, and adoption support"},
                {"heading": "Success Metrics", "todo": "Define productivity, quality, or cost targets"},
                {"heading": "Rollout Plan", "todo": "Map pilot phases and full deployment"},
            ],
        },
        {
            "key": "data-insights",
            "id_prefix": "epic-data-insights",
            "name": "Data & Insights Epic",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Deliver reporting, data quality, or business intelligence improvements.",
            "title_label": "Epic: [Insights Initiative]",
            "keywords": ["data", "insights", "analytics", "reporting", "intelligence"],
            "sections": [
                {"heading": "Intelligence Goals", "todo": "Describe the decisions or insights to unlock"},
                {"heading": "Data Sources", "todo": "List systems, pipelines, and ownership"},
                {"heading": "Analytics Deliverables", "todo": "Detail dashboards, models, or self-serve tools"},
                {"heading": "Enablement Plan", "todo": "Plan training, documentation, and adoption"},
                {"heading": "Governance & Quality", "todo": "Note stewardship, validation, and SLAs"},
                {"heading": "KPIs", "todo": "Define metrics to measure insight effectiveness"},
            ],
        },
        {
            "key": "integration-connectivity",
            "id_prefix": "epic-integration-connectivity",
            "name": "Integration & Connectivity Epic",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Expand interoperability through APIs and connectors.",
            "title_label": "Epic: [Integration Initiative]",
            "keywords": ["integration", "connectivity", "api", "partner", "ecosystem"],
            "sections": [
                {"heading": "Integration Vision", "todo": "Explain the cross-system experience to enable"},
                {"heading": "Systems Involved", "todo": "List upstream, downstream, and third-party systems"},
                {"heading": "API Strategy", "todo": "Outline standards, versioning, and security"},
                {"heading": "Data Contracts", "todo": "Define schemas, mappings, and validation"},
                {"heading": "Testing & Validation", "todo": "Plan integration, contract, and end-to-end tests"},
                {"heading": "Adoption Strategy", "todo": "Capture rollout, partner enablement, and support"},
            ],
        },
        {
            "key": "user-engagement",
            "id_prefix": "epic-user-engagement",
            "name": "User Engagement Epic",
            "emoji": "??",
            "default_priority": "Medium",
            "description": "Drive retention, onboarding, or personalized interaction strategies.",
            "title_label": "Epic: [Engagement Initiative]",
            "keywords": ["engagement", "retention", "onboarding", "personalization", "activation"],
            "sections": [
                {"heading": "Engagement Objectives", "todo": "Define the behavior or sentiment shift desired"},
                {"heading": "Audience Segments", "todo": "Identify cohorts and targeting criteria"},
                {"heading": "Program/Feature Ideas", "todo": "List campaigns, features, or experiments"},
                {"heading": "Personalization Strategy", "todo": "Describe data signals and tailored experiences"},
                {"heading": "Experiment Plan", "todo": "Outline testing approach, cadence, and owners"},
                {"heading": "Success Metrics", "todo": "Capture activation, retention, or satisfaction KPIs"},
            ],
        },
    ],
}

ALLOWED_PRIORITIES = {"high", "medium", "low"}

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("FATAL: GROQ_API_KEY environment variable not set.")

def get_prompt_for_type(prompt_type: str) -> str:
    """Get the appropriate prompt based on template type."""
    prompt_mapping = {
        "work_item": WORK_ITEM_TEMPLATE_PROMPT,
        "page": PAGE_TEMPLATE_PROMPT,
        "cycle": CYCLE_TEMPLATE_PROMPT,
        "module": MODULE_TEMPLATE_PROMPT,
        "epic": EPIC_TEMPLATE_PROMPT,
    }

    # Default to work_item if type not found
    return prompt_mapping.get(prompt_type.lower(), WORK_ITEM_TEMPLATE_PROMPT)

class TemplateGenerator:
    def __init__ (self):
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.1,  # Slightly creative for query understanding
            max_tokens=1024,
            top_p=0.8,
        )

    async def generate_template(self, user_input: str, prompt_type: str = "work_item") -> Dict[str, Any]:
        prompt_key = (prompt_type or "work_item").lower()
        system_prompt = get_prompt_for_type(prompt_key)

        scenario, keyword_hits = self._select_scenario(prompt_key, user_input)
        slug_hint = self._suggest_slug(user_input)
        priority_override = self._extract_priority_override(user_input)
        human_payload = self._build_user_context(
            prompt_key,
            user_input,
            scenario,
            keyword_hits,
            slug_hint,
            priority_override,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_payload),
        ]

        ai_response = await self.llm.ainvoke(messages)
        content = self._clean_model_output(ai_response.content)

        try:
            template = json.loads(content)
            required_keys = {"id", "name", "description", "title", "content", "priority"}
            if not required_keys.issubset(template.keys()):
                return {"error": "Missing required fields in template output."}

            template = self._post_process_template(
                template,
                scenario,
                slug_hint,
                priority_override,
            )
            return template
        except json.JSONDecodeError:
            return {"error": "Failed to parse template. Invalid JSON format."}

    def _clean_model_output(self, content: Optional[str]) -> str:
        if not content:
            return ""
        text = content.strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)
        if text.startswith("```"):
            stripped = text.strip("`\n")
            if stripped.startswith("json\n"):
                stripped = stripped[5:]
            text = stripped
        return text.strip()
    
    def _select_scenario(self, prompt_key: str, user_input: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        scenarios = SCENARIO_LIBRARY.get(prompt_key, [])
        if not scenarios or not user_input:
            return None, []

        text = user_input.lower()
        best_scenario: Optional[Dict[str, Any]] = None
        best_score = -1
        best_hits: List[str] = []

        for scenario in scenarios:
            hits = [kw for kw in scenario.get("keywords", []) if kw and kw in text]
            score = len(hits)
            scenario_name = scenario["name"].lower()
            scenario_key = scenario["key"].lower()
            if scenario_name in text:
                score += 3
            if scenario_key in text:
                score += 2
            if score > best_score:
                best_score = score
                best_scenario = scenario
                best_hits = hits

        if best_score <= 0:
            return None, []

        return best_scenario, best_hits

    def _build_user_context(
        self,
        prompt_key: str,
        user_input: str,
        scenario: Optional[Dict[str, Any]],
        keyword_hits: List[str],
        slug_hint: Optional[str],
        priority_override: Optional[str],
    ) -> str:
        trimmed_input = (user_input or "").strip()
        if not scenario:
            guidance = (
                "User Prompt:\n"
                f"{trimmed_input}\n\n"
                "Guidelines:\n"
                "- Stay within the facts supplied above.\n"
                "- Insert TODO placeholders when information is missing.\n"
                "- Output only the JSON structure requested by the system instructions."
            )
            return guidance

        section_lines = "\n".join(
            f"- {section['heading']}: {section['todo']}" for section in scenario.get("sections", [])
        )
        keywords_line = ", ".join(keyword_hits) if keyword_hits else "None detected"
        slug_line = slug_hint or "N/A"
        priority_line = priority_override or "None"

        context = (
            f"Scenario focus: {scenario['name']} (key: {scenario['key']}, emoji: {scenario['emoji']})\n"
            f"Default priority: {scenario['default_priority']}\n"
            f"Priority override requested: {priority_line}\n"
            f"Matched keywords: {keywords_line}\n"
            f"Recommended sections:\n{section_lines}\n"
            f"Suggested slug fragment: {slug_line}\n\n"
            f"User prompt:\n{trimmed_input}\n\n"
            "Remember: use only the information above. For any missing detail, respond with a TODO placeholder rather than inventing it."
        )
        return context

    def _suggest_slug(self, user_input: str) -> Optional[str]:
        if not user_input:
            return None
        normalized = re.sub(r"[^a-z0-9]+", "-", user_input.lower())
        normalized = re.sub(r"-+", "-", normalized).strip("-")
        tokens = [token for token in normalized.split("-") if len(token) > 2]
        if not tokens:
            return None
        return "-".join(tokens[:4])

    def _extract_priority_override(self, user_input: str) -> Optional[str]:
        if not user_input:
            return None
        text = user_input.lower()
        if any(term in text for term in ["urgent", "asap", "critical", "high priority", "blocker"]):
            return "High"
        if any(term in text for term in ["low priority", "not urgent", "nice to have", "whenever"]):
            return "Low"
        if any(term in text for term in ["medium priority", "normal priority", "standard priority"]):
            return "Medium"
        return None

    def _post_process_template(
        self,
        template: Dict[str, Any],
        scenario: Optional[Dict[str, Any]],
        slug_hint: Optional[str],
        priority_override: Optional[str],
    ) -> Dict[str, Any]:
        if template.get("error") or not scenario:
            return template

        template["id"] = self._normalize_id(template.get("id"), scenario["id_prefix"], slug_hint)
        template["title"] = self._normalize_title(template.get("title"), scenario)
        template["description"] = self._normalize_description(template.get("description"), scenario)
        template["priority"] = self._normalize_priority(
            template.get("priority"), scenario, priority_override
        )
        template["content"] = self._ensure_content_sections(template.get("content"), scenario)
        return template

    def _normalize_id(self, existing_id: Optional[str], prefix: str, slug_hint: Optional[str]) -> str:
        candidate = (existing_id or "").strip()
        candidate = re.sub(r"[^a-z0-9-]+", "-", candidate.lower()).strip("-")
        if candidate.startswith(prefix):
            return candidate
        if candidate:
            tail = candidate
            if tail.startswith(prefix):
                tail = tail[len(prefix):].strip("-")
            return f"{prefix}-{tail}".strip("-")
        if slug_hint:
            cleaned_slug = re.sub(r"[^a-z0-9-]+", "-", slug_hint.lower()).strip("-")
            if cleaned_slug:
                return f"{prefix}-{cleaned_slug}".strip("-")
        return prefix

    def _normalize_title(self, title: Optional[str], scenario: Dict[str, Any]) -> str:
        expected_prefix = f"{scenario['emoji']} "
        base_label = scenario.get("title_label", scenario["name"])
        candidate = (title or "").strip()
        if candidate.startswith(expected_prefix):
            return candidate
        return f"{expected_prefix}{base_label}"

    def _normalize_description(self, description: Optional[str], scenario: Dict[str, Any]) -> str:
        prefix = f"Scenario: {scenario['name']}."
        desc = (description or "").strip()
        if desc.startswith(prefix):
            return desc
        if desc:
            return f"{prefix} {desc}".strip()
        return f"{prefix} {scenario['description']}"

    def _normalize_priority(
        self,
        priority: Optional[str],
        scenario: Dict[str, Any],
        priority_override: Optional[str],
    ) -> str:
        if priority_override and priority_override.lower() in ALLOWED_PRIORITIES:
            return priority_override.capitalize()
        if priority and priority.lower() in ALLOWED_PRIORITIES:
            return priority.capitalize()
        return scenario["default_priority"]

    def _ensure_content_sections(self, content: Optional[str], scenario: Dict[str, Any]) -> str:
        existing_text = (content or "").strip()
        scenario_sections = scenario.get("sections", [])
        scenario_heading_lookup = {section["heading"].lower(): section for section in scenario_sections}

        pattern = re.compile(r"^##\s+(?P<heading>.+?)\s*$", flags=re.MULTILINE)
        matches = list(pattern.finditer(existing_text))
        existing_blocks: Dict[str, str] = {}
        extras: List[str] = []

        if matches:
            preamble = existing_text[:matches[0].start()].strip()
            if preamble:
                extras.append(preamble)

            for idx, match in enumerate(matches):
                heading = match.group("heading").strip()
                start = match.start()
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(existing_text)
                block = existing_text[start:end].strip()
                if heading.lower() in scenario_heading_lookup:
                    existing_blocks[heading.lower()] = block
                else:
                    extras.append(block)
        elif existing_text:
            extras.append(existing_text)

        normalized_blocks: List[str] = []
        for section in scenario_sections:
            heading = section["heading"]
            heading_lower = heading.lower()
            block = existing_blocks.get(heading_lower)
            if block:
                lines = block.splitlines()
                if not lines:
                    block = f"## {heading}\n- TODO: {section['todo']}"
                else:
                    lines[0] = f"## {heading}"
                    if len(lines) == 1 or not any(line.strip().startswith("-") for line in lines[1:]):
                        block = f"## {heading}\n- TODO: {section['todo']}"
                    else:
                        block = "\n".join(line.rstrip() for line in lines).strip()
            else:
                block = f"## {heading}\n- TODO: {section['todo']}"
            normalized_blocks.append(block.strip())

        normalized_content = "\n\n".join(normalized_blocks).strip()
        if extras:
            extras_text = "\n\n".join(segment.strip() for segment in extras if segment.strip())
            if extras_text:
                if normalized_content:
                    normalized_content = f"{normalized_content}\n\n{extras_text}"
                else:
                    normalized_content = extras_text

        if normalized_content and not normalized_content.endswith("\n"):
            normalized_content += "\n"
        return normalized_content
