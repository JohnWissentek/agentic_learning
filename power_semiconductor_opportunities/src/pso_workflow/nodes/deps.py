"""Runtime dependency injection container for workflow graph nodes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from pso_workflow.config import CostLedger, LLMClientProtocol, WorkflowSettings
from pso_workflow.tools.evidence_vault import EvidenceVault
from pso_workflow.tools.search_router import SearchRouterProtocol


@dataclass
class RuntimeDeps:
    """Shared async-safe dependencies passed to LangGraph nodes via closures."""

    settings: WorkflowSettings
    ledger: CostLedger
    vault: EvidenceVault
    search_router: SearchRouterProtocol
    llm: LLMClientProtocol
    semaphore: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self.semaphore = asyncio.Semaphore(max(1, self.settings.concurrency))
