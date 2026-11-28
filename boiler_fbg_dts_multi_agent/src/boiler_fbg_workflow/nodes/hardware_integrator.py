"""Hardware Integrator (HW) node.

Placeholder for hardware integration role implementation.
"""

from __future__ import annotations

from typing import Any

from boiler_fbg_workflow.config import RuntimeDeps
from boiler_fbg_workflow.schemas import WorkflowState


def execute_hw_architecture(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Execute hardware architecture design."""
    if deps.is_simulation:
        return {}
    return {"architecture": {}}


def execute_detailed_hw(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Execute detailed hardware design."""
    if deps.is_simulation:
        return {}
    return {"design": {}, "bom": []}


def execute_hw_integration(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Execute hardware integration."""
    if deps.is_simulation:
        return {}
    return {}
