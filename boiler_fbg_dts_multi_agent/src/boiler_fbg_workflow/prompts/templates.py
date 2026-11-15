"""Prompt templates for multi-agent R&D workflow roles.

These prompts are used in live mode with actual LLM calls.
In simulation mode, pre-defined outputs are used instead.
"""

from boiler_fbg_workflow.config import ROLE_PROMPTS

def get_role_prompt(role_id: str) -> str:
    """Get the system prompt for a role."""
    return ROLE_PROMPTS.get(role_id, f"You are the {role_id} agent.")


def get_stage_prompt(stage: str, role: str, context: dict) -> str:
    """Build a stage-specific prompt with context."""
    base_prompt = get_role_prompt(role)
    
    stage_instructions = {
        "stage_0_requirements": """
Current Task: Stage 0 - Requirements Analysis and Market Research

Analyze the following and produce structured output:
1. Market segments and sizing (use [MKT-CALC] tag for calculations)
2. Customer pain points and needs
3. Technical requirements
4. Competitive landscape

Mark all uncertain data with [EV-UNKNOWN] evidence tags.
""",
        "stage_1_concept": """
Current Task: Stage 1 - Concept Design

Based on Stage 0 outputs, develop:
1. Technology route analysis (FBG vs DTS)
2. Sensor specifications (mark pending items as [PENDING])
3. System architecture
4. Safety constraints

All selections must cite evidence. Use [EV-UNKNOWN] for unverified specs.
""",
        "stage_2_detailed_design": """
Current Task: Stage 2 - Detailed Design

Develop detailed designs including:
1. Detailed optical/sensor design
2. Hardware specifications and BOM
3. Software architecture
4. Cost analysis

All BOM items without quotes should be marked as pending_quote.
""",
    }
    
    instruction = stage_instructions.get(stage, f"Current Task: {stage}")
    
    context_str = "\n".join(f"- {k}: {v}" for k, v in context.items() if v)
    
    return f"""{base_prompt}

{instruction}

Available Context:
{context_str}

Output Requirements:
- Use structured JSON format
- Include evidence_ids for all claims
- Mark uncertainties clearly
- Follow safety constraints
"""
