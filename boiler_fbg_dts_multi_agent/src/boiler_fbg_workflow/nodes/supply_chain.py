"""Supply Chain Manager (SCM) node.

Placeholder for supply chain role implementation.
"""

from __future__ import annotations

from typing import Any

from boiler_fbg_workflow.config import RuntimeDeps
from boiler_fbg_workflow.schemas import WorkflowState


def execute_supplier_analysis(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Execute supplier analysis."""
    if deps.is_simulation:
        return {}
    return {"suppliers": []}
