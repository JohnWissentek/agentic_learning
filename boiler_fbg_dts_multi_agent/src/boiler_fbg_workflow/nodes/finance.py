"""Finance Analyst (FIN) node.

Placeholder for finance role implementation.
"""

from __future__ import annotations

from typing import Any

from boiler_fbg_workflow.config import RuntimeDeps
from boiler_fbg_workflow.schemas import WorkflowState


def execute_cost_analysis(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Execute cost analysis."""
    if deps.is_simulation:
        return {}
    return {"breakdown": {}}
