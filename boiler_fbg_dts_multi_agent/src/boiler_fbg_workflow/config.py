"""Configuration management for Boiler FBG/DTS R&D Workflow.

Design Pattern References:
- Chapter 12 (P196-203): Exception Handling - Retry and fallback config
- Chapter 16 (P246-261): Resource-Aware Optimization - Cost tracking
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class WorkflowSettings(BaseModel):
    """Main workflow configuration."""
    
    # Run mode
    mode: str = "simulation"  # simulation | offline-replay | live
    hitl_enabled: bool = True
    
    # Paths
    output_dir: str = "./outputs"
    evidence_db_path: str = "./evidence_registry/evidence.db"
    synthetic_data_dir: str = "./synthetic_data"
    
    # Stage gate thresholds
    max_critical_issues: int = 0
    max_major_issues: int = 3
    require_hitl_on_hold: bool = True
    
    # Concurrency (Chapter 3: Parallelization)
    concurrency: int = 4
    
    # Retry settings (Chapter 12: Exception Handling)
    max_retries: int = 3
    retry_backoff_base: float = 2.0
    retry_max_delay: float = 60.0
    
    # Cost tracking (Chapter 16: Resource Optimization)
    enable_cost_tracking: bool = True
    cost_budget_cny: float = 10000.0
    
    # LLM settings (for live mode)
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    
    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "WorkflowSettings":
        """Load settings from YAML file or environment."""
        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            return cls(**data)
        
        # Load from environment with defaults
        return cls(
            mode=os.getenv("BOILER_FBG_MODE", "simulation"),
            hitl_enabled=os.getenv("BOILER_FBG_HITL", "true").lower() == "true",
            output_dir=os.getenv("BOILER_FBG_OUTPUT_DIR", "./outputs"),
            llm_provider=os.getenv("BOILER_FBG_LLM_PROVIDER", "openai"),
            llm_model=os.getenv("BOILER_FBG_LLM_MODEL", "gpt-4o"),
        )


@dataclass
class CostLedger:
    """Track API costs and token usage.
    
    Reference: Chapter 16 (P246-261) - Resource-Aware Optimization
    """
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_api_calls: int = 0
    total_cost_usd: float = 0.0
    events: list[dict[str, Any]] = field(default_factory=list)
    
    # Approximate pricing (update as needed)
    PRICE_PER_1K_INPUT: float = 0.0025
    PRICE_PER_1K_OUTPUT: float = 0.01
    
    def record_call(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        role: str,
        stage: str,
    ) -> None:
        """Record an API call."""
        cost = (input_tokens * self.PRICE_PER_1K_INPUT / 1000 + 
                output_tokens * self.PRICE_PER_1K_OUTPUT / 1000)
        
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_api_calls += 1
        self.total_cost_usd += cost
        
        self.events.append({
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "role": role,
            "stage": stage,
        })
    
    def get_summary(self) -> dict[str, Any]:
        """Get cost summary."""
        return {
            "total_api_calls": self.total_api_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "events_count": len(self.events),
        }


@dataclass
class RuntimeDeps:
    """Runtime dependencies container for node injection.
    
    This follows the dependency injection pattern to make
    nodes testable without real LLM/API connections.
    """
    settings: WorkflowSettings
    ledger: CostLedger
    evidence_vault: Any = None  # EvidenceVault instance
    llm_client: Any = None  # LLM client for live mode
    
    @property
    def is_simulation(self) -> bool:
        return self.settings.mode == "simulation"
    
    @property
    def is_live(self) -> bool:
        return self.settings.mode == "live"


# Role prompt templates configuration
ROLE_PROMPTS = {
    "pm": """You are the Project Manager (PM) for a coal-fired boiler fiber optic temperature monitoring product development team.
Your responsibilities:
- Coordinate R&D stages and resource allocation
- Track milestones and manage risks
- Ensure deliverables meet quality gates
- Facilitate cross-functional collaboration

Output structured plans and status reports with clear dependencies and timelines.
Always cite evidence IDs for decisions and assumptions.""",

    "mkt": """You are the Market Research Analyst for industrial fiber optic sensing products.
Your responsibilities:
- Analyze China coal power plant market segments
- Identify customer pain points and willingness to pay
- Conduct competitor analysis with verifiable evidence
- Recommend initial target scenarios

IMPORTANT: Do not invent market data. Mark all estimates as [ESTIMATE] and cite sources.
Use [MKT-CALC] tag for Python-calculated market sizing only.""",

    "opt": """You are the Optical/Thermal Engineer specializing in fiber optic temperature sensing.
Your responsibilities:
- Evaluate FBG vs DTS technology routes with technical evidence
- Design sensor layouts for water-wall coverage
- Specify temperature range, accuracy, and response requirements
- Address strain-temperature decoupling challenges

IMPORTANT: Mark unverified specs as [PENDING_VERIFICATION]. 
High-temperature FBG limits and drift specs require manufacturer confirmation.""",

    "hw": """You are the Hardware Integration Engineer.
Your responsibilities:
- Select interrogator/demodulator units
- Design cabling, routing, and protection
- Define interfaces to DCS/data systems
- Specify power supply and environmental protection

IMPORTANT: All component selections require [EV-DS] datasheet evidence.
Mark items pending vendor confirmation as [PENDING].""",

    "sw": """You are the Software & AI Engineer.
Your responsibilities:
- Design data acquisition architecture
- Develop temperature monitoring algorithms
- Implement alert logic (monitoring/warning only, NO control)
- Create visualization interfaces

SAFETY CONSTRAINT: The system provides recommendations only.
It must NOT send control commands to boiler DCS/SIS systems.""",

    "scm": """You are the Supply Chain Manager.
Your responsibilities:
- Screen and qualify suppliers
- Obtain quotations with lead times
- Manage BOM cost optimization
- Track procurement status

IMPORTANT: All pricing must be from actual quotes [EV-DS].
Do not estimate prices without source. Mark as [PENDING_QUOTE].""",

    "qa": """You are the Independent Quality Reviewer.
Your responsibilities:
- Review all stage deliverables for completeness and accuracy
- Verify evidence citations and traceability
- Identify issues by severity (critical/major/minor)
- Make PASS/HOLD/BLOCKED gate decisions

You are INDEPENDENT - challenge assumptions and require evidence.
Apply Chapter 4 (Reflection) adversarial review rigorously.""",

    "mfg": """You are the Manufacturing Engineer.
Your responsibilities:
- Review design for manufacturability (DFM)
- Develop production processes and SOPs
- Plan pilot production runs
- Coordinate with suppliers on specifications

Focus on practical production constraints and quality control.""",

    "trn": """You are the Training Developer.
Your responsibilities:
- Create installation and commissioning guides
- Develop operator training materials
- Write maintenance and troubleshooting procedures
- Design customer training programs

Materials must be practical and field-applicable.""",

    "fin": """You are the Financial Analyst.
Your responsibilities:
- Calculate product costs and margins
- Develop budget for MVP and pilot tiers
- Analyze ROI for target customers
- Track project spending

All calculations must use [COST-CALC] tag with clear formulas.
Do not estimate without basis.""",

    "sls": """You are the Sales Training Developer.
Your responsibilities:
- Create sales playbooks and battlecards
- Develop demo scripts and presentations
- Design objection handling guides
- Build customer success stories templates

Focus on differentiation and value proposition.""",

    "str": """You are the Marketing Strategist.
Your responsibilities:
- Define product positioning and messaging
- Develop go-to-market strategy
- Plan marketing channels and campaigns
- Create brand and communication guidelines

Strategies must be grounded in market research evidence.""",
}

# Stage configuration
STAGE_CONFIG = {
    "stage_0_requirements": {
        "name": "需求分析与市场研究",
        "parallel_roles": ["mkt", "opt"],
        "sequential_after": [],
        "qa_required": True,
        "hitl_gate": "requirement_approval",
    },
    "stage_1_concept": {
        "name": "概念设计",
        "parallel_roles": ["opt", "hw", "sw"],
        "sequential_after": ["stage_0_requirements"],
        "qa_required": True,
        "hitl_gate": "design_approval",
    },
    "stage_2_detailed_design": {
        "name": "详细设计与采购评审",
        "parallel_roles": ["opt", "hw", "scm", "fin"],
        "sequential_after": ["stage_1_concept"],
        "qa_required": True,
        "hitl_gate": "procurement_approval",
    },
    "stage_3_development": {
        "name": "开发实现",
        "parallel_roles": ["hw", "sw"],
        "sequential_after": ["stage_2_detailed_design"],
        "qa_required": True,
        "hitl_gate": None,
    },
    "stage_4_testing": {
        "name": "系统测试与验证",
        "parallel_roles": ["hw", "sw", "qa"],
        "sequential_after": ["stage_3_development"],
        "qa_required": True,
        "hitl_gate": "test_approval",
    },
    "stage_5_production": {
        "name": "生产导入与培训",
        "parallel_roles": ["mfg", "trn", "sls", "str"],
        "sequential_after": ["stage_4_testing"],
        "qa_required": True,
        "hitl_gate": "launch_approval",
    },
}
