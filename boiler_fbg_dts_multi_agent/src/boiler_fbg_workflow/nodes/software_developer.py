"""Software Developer (SW) node.

Placeholder for software development role implementation.
"""

from __future__ import annotations

from typing import Any

from boiler_fbg_workflow.config import RuntimeDeps
from boiler_fbg_workflow.schemas import WorkflowState


def execute_sw_architecture(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Execute software architecture design."""
    if deps.is_simulation:
        return {}
    return {"architecture": {}}


def execute_sw_development(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Execute software development."""
    if deps.is_simulation:
        return {}
    return {}
