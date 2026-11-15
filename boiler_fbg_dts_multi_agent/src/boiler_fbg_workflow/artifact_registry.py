"""Artifact Registry - Track and pass artifacts between stages.

RUN-03 Fix: QA and PM must receive actual upstream outputs.
Each artifact has ID, hash, source role, and validation status.
"""

from __future__ import annotations
import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class Artifact:
    """A tracked artifact from a stage."""
    artifact_id: str
    source_role: str
    stage: str
    created_at: str
    
    # Content
    raw_response: str
    parsed_output: Optional[dict[str, Any]]
    
    # Validation
    parse_success: bool
    schema_valid: bool
    validation_issues: list[str]
    semantic_anomalies: list[dict[str, Any]]
    
    # Hashes for verification
    raw_hash: str
    parsed_hash: str
    
    # Trust level
    trust_level: str  # VERIFIED, UNVERIFIED, QUARANTINED
    quarantine_reason: str = ""
    
    def to_summary(self, max_len: int = 200) -> dict[str, Any]:
        """Create concise summary for downstream consumption."""
        return {
            "artifact_id": self.artifact_id,
            "source_role": self.source_role,
            "stage": self.stage,
            "parse_success": self.parse_success,
            "schema_valid": self.schema_valid,
            "trust_level": self.trust_level,
            "validation_issues": self.validation_issues[:3],  # Top 3
            "semantic_anomalies_count": len(self.semantic_anomalies),
            "raw_preview": self.raw_response[:max_len] + "..." if len(self.raw_response) > max_len else self.raw_response,
            "raw_hash": self.raw_hash,
        }
    
    def to_dict(self) -> dict[str, Any]:
        """Full artifact for storage."""
        return {
            "artifact_id": self.artifact_id,
            "source_role": self.source_role,
            "stage": self.stage,
            "created_at": self.created_at,
            "raw_response": self.raw_response,
            "parsed_output": self.parsed_output,
            "parse_success": self.parse_success,
            "schema_valid": self.schema_valid,
            "validation_issues": self.validation_issues,
            "semantic_anomalies": self.semantic_anomalies,
            "raw_hash": self.raw_hash,
            "parsed_hash": self.parsed_hash,
            "trust_level": self.trust_level,
            "quarantine_reason": self.quarantine_reason,
        }


class ArtifactRegistry:
    """Registry for tracking artifacts across stages."""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self._artifacts: dict[str, Artifact] = {}
        self._artifact_count = 0
    
    def _generate_id(self, role: str) -> str:
        """Generate unique artifact ID."""
        self._artifact_count += 1
        return f"ART-{self.run_id}-{role}-{self._artifact_count:03d}"
    
    def _hash(self, text: str) -> str:
        """Generate hash of text."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]
    
    def register(
        self,
        source_role: str,
        stage: str,
        raw_response: str,
        parsed_output: Optional[dict[str, Any]],
        parse_success: bool,
        schema_valid: bool,
        validation_issues: list[str],
        semantic_anomalies: list[dict[str, Any]],
    ) -> Artifact:
        """Register an artifact."""
        artifact_id = self._generate_id(source_role)
        
        # Determine trust level
        trust_level = "VERIFIED"
        quarantine_reason = ""
        
        if not parse_success:
            trust_level = "QUARANTINED"
            quarantine_reason = "JSON解析失败"
        elif not schema_valid:
            trust_level = "UNVERIFIED"
            quarantine_reason = "Schema验证失败"
        elif len(semantic_anomalies) > 0:
            trust_level = "QUARANTINED"
            quarantine_reason = f"检测到{len(semantic_anomalies)}个语义异常"
        
        artifact = Artifact(
            artifact_id=artifact_id,
            source_role=source_role,
            stage=stage,
            created_at=datetime.now(timezone.utc).isoformat(),
            raw_response=raw_response,
            parsed_output=parsed_output,
            parse_success=parse_success,
            schema_valid=schema_valid,
            validation_issues=validation_issues,
            semantic_anomalies=semantic_anomalies,
            raw_hash=self._hash(raw_response),
            parsed_hash=self._hash(json.dumps(parsed_output, sort_keys=True)) if parsed_output else "",
            trust_level=trust_level,
            quarantine_reason=quarantine_reason,
        )
        
        self._artifacts[artifact_id] = artifact
        return artifact
    
    def get(self, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID."""
        return self._artifacts.get(artifact_id)
    
    def get_by_role(self, role: str) -> list[Artifact]:
        """Get all artifacts from a role."""
        return [a for a in self._artifacts.values() if a.source_role == role]
    
    def get_all(self) -> list[Artifact]:
        """Get all artifacts."""
        return list(self._artifacts.values())
    
    def get_summaries_for_qa(self, roles: list[str]) -> str:
        """Get summaries of upstream artifacts for QA review.
        
        RUN-03 Fix: QA must see actual upstream outputs.
        """
        summaries = []
        
        for role in roles:
            artifacts = self.get_by_role(role)
            for art in artifacts:
                summary = art.to_summary(max_len=300)
                summaries.append(f"""
### {role} ({art.artifact_id})
- 解析成功: {art.parse_success}
- Schema有效: {art.schema_valid}
- 信任级别: {art.trust_level}
- 语义异常: {len(art.semantic_anomalies)}个
- 验证问题: {', '.join(art.validation_issues[:3]) if art.validation_issues else '无'}
- 原文摘要: {summary['raw_preview']}
- 原文hash: {art.raw_hash}
""")
        
        return "\n".join(summaries)
    
    def get_quarantined(self) -> list[Artifact]:
        """Get all quarantined artifacts."""
        return [a for a in self._artifacts.values() if a.trust_level == "QUARANTINED"]
    
    def get_input_artifact_ids(self, role: str) -> list[str]:
        """Get artifact IDs that should be inputs for a role.
        
        RUN-03 Fix: Track which artifacts fed into which stage.
        """
        # Define input dependencies
        dependencies = {
            "QA": ["MKT", "OPT", "HW", "SW", "SCM", "MFG", "TRN", "FIN", "SLS"],
            "PM": ["MKT", "OPT", "HW", "SW", "SCM", "MFG", "TRN", "FIN", "SLS", "QA"],
            "STR": ["MKT", "OPT", "HW", "SW", "SCM", "MFG", "TRN", "FIN", "SLS", "QA", "PM"],
            "PM_REWORK": ["QA", "PM"],
        }
        
        input_roles = dependencies.get(role, [])
        artifact_ids = []
        
        for input_role in input_roles:
            for art in self.get_by_role(input_role):
                artifact_ids.append(art.artifact_id)
        
        return artifact_ids
    
    def verify_downstream_received(
        self,
        downstream_role: str,
        downstream_prompt: str,
    ) -> dict[str, bool]:
        """Verify downstream prompt contains expected artifact references.
        
        RUN-03 Fix: Verify QA/PM actually received upstream content.
        """
        expected_ids = self.get_input_artifact_ids(downstream_role)
        received = {}
        
        for artifact_id in expected_ids:
            art = self.get(artifact_id)
            if art:
                # Check if hash or preview appears in prompt
                hash_in_prompt = art.raw_hash in downstream_prompt
                preview_in_prompt = art.raw_response[:50] in downstream_prompt
                received[artifact_id] = hash_in_prompt or preview_in_prompt
            else:
                received[artifact_id] = False
        
        return received
    
    def export(self) -> dict[str, Any]:
        """Export all artifacts."""
        return {
            "run_id": self.run_id,
            "artifact_count": self._artifact_count,
            "artifacts": [a.to_dict() for a in self._artifacts.values()],
            "quarantined_count": len(self.get_quarantined()),
        }
