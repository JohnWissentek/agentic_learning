"""Boiler FBG/DTS Multi-Agent R&D Workflow Package.

Based on "Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems"
by Antonio Gulli (Google CTO Office Engineering Director).

This package implements a multi-agent product development team workflow for
coal-fired boiler water-wall fiber optic temperature monitoring systems.

v0.2 includes real QA findings integration (5 HIGH, 5 MEDIUM) for Reflection Pattern.
"""

__version__ = "0.2.0"

from boiler_fbg_workflow.qa_findings import (
    QA_REVIEW_METADATA,
    QA_FINDINGS_HIGH,
    QA_FINDINGS_MEDIUM,
    QA_FINDINGS_ALL,
    get_findings_summary,
    get_findings_for_reflection_prompt,
    get_pm_task_revision_input,
)

__all__ = [
    "QA_REVIEW_METADATA",
    "QA_FINDINGS_HIGH",
    "QA_FINDINGS_MEDIUM", 
    "QA_FINDINGS_ALL",
    "get_findings_summary",
    "get_findings_for_reflection_prompt",
    "get_pm_task_revision_input",
]
