"""Shared runtime dependency container injected into LangGraph nodes via functools.partial."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from bfbg_workflow.config import CostLedger, LLMGatewayProtocol, WorkflowSettings
from bfbg_workflow.tools.evidence_vault import EvidenceVault
from bfbg_workflow.tools.search_router import DualEngineSearchRouter


@dataclass
class RuntimeDeps:
    """In-process dependencies kept outside LangGraph serializable WorkflowState."""

    settings: WorkflowSettings
    ledger: CostLedger
    vault: EvidenceVault
    search_router: DualEngineSearchRouter
    llm: LLMGatewayProtocol
    semaphore: asyncio.Semaphore
