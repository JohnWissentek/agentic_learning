"""Shared runtime dependencies container injected cleanly via RunnableConfig."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from vf_ccus_workflow.config import CostLedger, LLMClientProtocol, WorkflowSettings
from vf_ccus_workflow.tools.evidence_vault import EvidenceVault
from vf_ccus_workflow.tools.search_router import DualEngineSearchRouter


@dataclass
class RuntimeDeps:
    """Out-of-state resources so LangGraph WorkflowState remains 100% JSON-serializable."""

    settings: WorkflowSettings
    ledger: CostLedger
    vault: EvidenceVault
    search_router: DualEngineSearchRouter
    llm: LLMClientProtocol
    semaphore: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(6))
