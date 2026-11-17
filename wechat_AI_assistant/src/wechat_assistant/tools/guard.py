"""Ch.18 tool permission guard enforcing human approval tokens on state mutations."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

MUTATION_TOOLS = frozenset(
    {
        "propose_list_mutations",
        "compose_markdown_brief",
        "organize_onedrive_files",
    }
)


@dataclass(frozen=True)
class ApprovalToken:
    """Short-lived HMAC token minted strictly after human confirmation."""

    proposal_id: int
    issued_at: float
    signature: str

    @classmethod
    def mint(cls, proposal_id: int, secret: str) -> ApprovalToken:
        ts = round(time.time(), 3)
        msg = f"{proposal_id}:{ts}".encode("utf-8")
        sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        return cls(proposal_id=proposal_id, issued_at=ts, signature=sig)

    def verify(self, secret: str, max_age_seconds: int = 86400) -> bool:
        if not secret or time.time() - self.issued_at > max_age_seconds:
            return False
        msg = f"{self.proposal_id}:{self.issued_at}".encode("utf-8")
        expected = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.signature)


def before_tool_callback(
    tool_name: str,
    args: dict[str, Any],
    *,
    approval_token: ApprovalToken | None = None,
    signing_secret: str = "",
) -> None:
    """Block unapproved state-mutating tools before execution."""
    if tool_name not in MUTATION_TOOLS:
        return
    if approval_token is None or not approval_token.verify(signing_secret):
        raise PermissionError(
            f"Blocked unapproved mutation tool '{tool_name}': valid human ApprovalToken is required."
        )
