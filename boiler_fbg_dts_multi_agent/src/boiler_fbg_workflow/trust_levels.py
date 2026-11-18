"""Trust Level Definitions - Renamed for clarity.

Fix #4: VERIFIED → FORMAT_VALID_RULES_NOT_TRIGGERED
- Format valid + rules not hit ≠ fact correct
- Unreviewed facts default to UNREVIEWED
"""

from enum import Enum


class TrustLevel(str, Enum):
    """Trust level definitions - clear naming."""
    
    # Format valid and semantic rules not triggered (NOT fact verification)
    FORMAT_VALID_RULES_NOT_TRIGGERED = "FORMAT_VALID_RULES_NOT_TRIGGERED"
    
    # Schema validation failed
    SCHEMA_FAILED = "SCHEMA_FAILED"
    
    # Semantic rules triggered (may be false positive)
    RULE_TRIGGERED = "RULE_TRIGGERED"
    
    # Facts not reviewed against source
    UNREVIEWED = "UNREVIEWED"
    
    # Parse failed completely
    PARSE_FAILED = "PARSE_FAILED"
    
    # Context limit hit
    CONTEXT_LIMIT = "CONTEXT_LIMIT"
    
    # Invalid artifact reference
    REFERENCE_INVALID = "REFERENCE_INVALID"


# Mapping from old names (for backward compat in tests)
LEGACY_MAPPING = {
    "VERIFIED": TrustLevel.FORMAT_VALID_RULES_NOT_TRIGGERED,
    "QUARANTINED": TrustLevel.RULE_TRIGGERED,
    "UNVERIFIED": TrustLevel.SCHEMA_FAILED,
}


def determine_trust_level(
    parse_success: bool,
    schema_valid: bool,
    rule_hits: int,
    has_source_verification: bool = False,
) -> TrustLevel:
    """Determine trust level based on validation results.
    
    Note: FORMAT_VALID_RULES_NOT_TRIGGERED does NOT mean facts are verified.
    """
    if not parse_success:
        return TrustLevel.PARSE_FAILED
    
    if not schema_valid:
        return TrustLevel.SCHEMA_FAILED
    
    if rule_hits > 0:
        return TrustLevel.RULE_TRIGGERED
    
    if not has_source_verification:
        return TrustLevel.UNREVIEWED
    
    return TrustLevel.FORMAT_VALID_RULES_NOT_TRIGGERED
