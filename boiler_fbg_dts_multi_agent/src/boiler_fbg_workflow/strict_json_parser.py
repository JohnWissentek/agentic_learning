"""Strict JSON Parser - No regex salvage, no inner extraction.

RUN-01 Fix: Complete root object parsing only.
If root fails, mark PARSE_FAILED. No silent partial extraction.
Also detect semantic anomalies in raw text even on parse failure.
"""

from __future__ import annotations
import json
import re
from typing import Any, Optional
from dataclasses import dataclass, field


# Semantic anomalies to detect in raw text (even if JSON parse fails)
SEMANTIC_ANOMALIES = {
    "engineering_pass": {
        "patterns": [
            r"工程验证[^不]*[=：:]\s*(PASS|通过|完成)",
            r"10[项个].*PASS",
            r"验证状态[^不]*PASS",
            r'"状态"[^}]*"PASS"',  # JSON format: "状态": "PASS"
            r"状态.*PASS",
        ],
        "severity": "CRITICAL",
        "conflict": "工程验证10项仍OPEN，不可声称PASS",
    },
    "fabricated_price": {
        "patterns": [
            r"\$\d{2,},?\d{3}",  # $50,000 etc
            r"[\d,]+元/套",
            r"报价.*\d{4,}",
        ],
        "severity": "HIGH",
        "conflict": "无真实报价来源，不可伪造价格",
    },
    "fabricated_company": {
        "patterns": [
            r"XYZ|ABC公司|ACME|某某公司",
        ],
        "severity": "HIGH",
        "conflict": "虚构公司名称",
    },
    "wavelength_sufficient": {
        "patterns": [
            r"波长预算(充足|足够|满足)",
            r"预算[^不]*(充足|足够)",
        ],
        "severity": "HIGH",
        "conflict": "波长预算状态UNKNOWN，不可声称充足",
    },
    "customer_testimonials": {
        "patterns": [
            r"customer\s*testimonial",
            r"客户证言|用户评价",
        ],
        "severity": "HIGH",
        "conflict": "无真实客户证言，不可伪造",
    },
    "wrong_forbidden_claims": {
        "patterns": [
            r"forbidden.*not ready for delivery",
            r"forbidden.*no real project",
            r"forbidden.*competitive.*not verified",
        ],
        "severity": "CRITICAL",
        "conflict": "真实限制不应放入forbidden_claims，应放入required_disclosures",
    },
}


@dataclass
class SemanticAnomaly:
    """Detected semantic anomaly."""
    anomaly_id: str
    severity: str
    pattern_matched: str
    conflict: str
    raw_context: str  # Surrounding text


@dataclass
class StrictParseResult:
    """Result of strict JSON parsing."""
    success: bool
    parsed: Optional[dict[str, Any]]
    raw_text: str
    error_message: str = ""
    error_position: tuple[int, int] = (0, 0)  # line, col
    semantic_anomalies: list[SemanticAnomaly] = field(default_factory=list)
    had_markdown_fence: bool = False
    had_js_comments: bool = False
    is_partial_extraction: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "error_message": self.error_message,
            "error_position": self.error_position,
            "semantic_anomalies": [
                {
                    "id": a.anomaly_id,
                    "severity": a.severity,
                    "conflict": a.conflict,
                    "context": a.raw_context[:100],
                }
                for a in self.semantic_anomalies
            ],
            "had_markdown_fence": self.had_markdown_fence,
            "had_js_comments": self.had_js_comments,
            "is_partial_extraction": self.is_partial_extraction,
        }


def _remove_markdown_fence(text: str) -> tuple[str, bool]:
    """Remove only outermost markdown fence, not inner content."""
    had_fence = False
    text = text.strip()
    
    # Check for ```json or ``` at start
    if text.startswith("```"):
        had_fence = True
        # Find first newline after fence
        first_nl = text.find("\n")
        if first_nl > 0:
            text = text[first_nl + 1:]
        
        # Find closing fence
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    
    return text, had_fence


def _detect_js_comments(text: str) -> bool:
    """Detect JavaScript-style comments in JSON."""
    # // comments
    if re.search(r'//[^\n]*', text):
        return True
    # /* */ comments
    if re.search(r'/\*.*?\*/', text, re.DOTALL):
        return True
    return False


def _detect_semantic_anomalies(raw_text: str) -> list[SemanticAnomaly]:
    """Detect semantic anomalies in raw text."""
    anomalies = []
    raw_lower = raw_text.lower()
    
    for anomaly_id, config in SEMANTIC_ANOMALIES.items():
        for pattern in config["patterns"]:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                # Get context
                start = max(0, match.start() - 30)
                end = min(len(raw_text), match.end() + 30)
                context = raw_text[start:end]
                
                anomalies.append(SemanticAnomaly(
                    anomaly_id=anomaly_id,
                    severity=config["severity"],
                    pattern_matched=match.group(),
                    conflict=config["conflict"],
                    raw_context=context,
                ))
                break  # One match per anomaly type
    
    return anomalies


def strict_parse_json(raw_response: str) -> StrictParseResult:
    """Strictly parse JSON from response.
    
    RUN-01 Fix:
    1. Remove ONLY outer markdown fence
    2. Detect JS comments (// or /* */)
    3. Attempt json.loads on COMPLETE root object
    4. If fails, mark PARSE_FAILED (no regex salvage)
    5. Detect semantic anomalies in raw REGARDLESS of parse success
    """
    # Detect semantic anomalies first (always, even if parse fails)
    anomalies = _detect_semantic_anomalies(raw_response)
    
    # Remove outer markdown fence
    text, had_fence = _remove_markdown_fence(raw_response)
    
    # Detect JS comments
    has_comments = _detect_js_comments(text)
    
    # Strict root object parse - NO partial extraction
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            return StrictParseResult(
                success=False,
                parsed=None,
                raw_text=raw_response,
                error_message=f"Root object is {type(parsed).__name__}, not dict",
                semantic_anomalies=anomalies,
                had_markdown_fence=had_fence,
                had_js_comments=has_comments,
            )
        
        return StrictParseResult(
            success=True,
            parsed=parsed,
            raw_text=raw_response,
            semantic_anomalies=anomalies,
            had_markdown_fence=had_fence,
            had_js_comments=has_comments,
        )
        
    except json.JSONDecodeError as e:
        return StrictParseResult(
            success=False,
            parsed=None,
            raw_text=raw_response,
            error_message=f"JSONDecodeError: {e.msg}",
            error_position=(e.lineno, e.colno),
            semantic_anomalies=anomalies,
            had_markdown_fence=had_fence,
            had_js_comments=has_comments,
        )


# Test case from RUN-01 (PM with // comments)
PM_RUN01_NEGATIVE_CASE = '''```json
{
  "output_summary": {
    "文档纠正": "10项已完成，独立复查10/10已接受",
    "工程验证": {
      "状态": "PASS",  // 这是错误的！
      "备注": "10项工程验证已通过"
    }
  },
  "rework_items": [
    // 可能需要返工的项目列表
    {"role": "OPT", "reason": "缺少fwhm_analysis字段"}
  ],
  "action_plan": "继续推进"
}
```'''


def test_pm_run01_case() -> bool:
    """Regression test for RUN-01 PM case."""
    result = strict_parse_json(PM_RUN01_NEGATIVE_CASE)
    
    # Must fail due to JS comments
    assert not result.success, "PM with // comments must fail parse"
    assert result.had_js_comments, "Must detect JS comments"
    assert result.had_markdown_fence, "Must detect markdown fence"
    
    # Must detect engineering PASS anomaly
    pass_anomalies = [a for a in result.semantic_anomalies 
                      if a.anomaly_id == "engineering_pass"]
    assert len(pass_anomalies) > 0, "Must detect engineering PASS anomaly"
    
    return True
