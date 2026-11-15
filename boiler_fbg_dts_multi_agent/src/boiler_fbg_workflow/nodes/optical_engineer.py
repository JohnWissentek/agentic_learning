"""Optical/Thermal Engineer (OPT) node.

Placeholder for optical engineering role implementation.
"""

from __future__ import annotations

from typing import Any

from boiler_fbg_workflow.config import RuntimeDeps
from boiler_fbg_workflow.schemas import WorkflowState


def execute_tech_feasibility(deps: RuntimeDeps) -> dict[str, Any]:
    """Execute technical feasibility assessment."""
    if deps.is_simulation:
        return {}
    return {"requirements": []}


def execute_optical_design(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Execute optical system design."""
    if deps.is_simulation:
        return {}
    return {"tech_route": {}, "sensor_specs": []}


def execute_detailed_optical(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Execute detailed optical design."""
    if deps.is_simulation:
        return {}
    return {}
