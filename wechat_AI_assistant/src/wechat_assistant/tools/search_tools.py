"""Group 3 External Search Tools with pre-search company/client/price redaction."""

from __future__ import annotations

import re
from typing import Any, Iterable

from wechat_assistant.config import Settings, assert_no_secrets_leaked

_DEFAULT_SENSITIVE_TERMS = (
    "帕莫瑞",
    "维恩科仪",
    "Wissentek",
    "wissentek",
    "chairman-vault",
)

_ORG_PATTERN = re.compile(r"[\u4e00-\u9fa5A-Za-z0-9]{2,12}(?:科技有限公司|有限公司|集团|热电厂|电厂|股份)")
_PRICE_PATTERN = re.compile(r"(?:[¥$￥]\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*(?:万元|万|元/支|元/台|RMB|USD))")


def sanitize_external_query(
    query: str,
    sensitive_terms: Iterable[str] = (),
) -> tuple[str, list[str]]:
    """Strip client names, company entities, and monetary figures before outbound search."""
    redacted: list[str] = []
    cleaned = query

    all_terms = sorted({*_DEFAULT_SENSITIVE_TERMS, *(t for t in sensitive_terms if t)}, key=len, reverse=True)
    for term in all_terms:
        if term in cleaned:
            redacted.append(term)
            cleaned = cleaned.replace(term, "")

    for pattern, label in ((_ORG_PATTERN, "[ORG]"), (_PRICE_PATTERN, "[PRICE]")):
        matches = pattern.findall(cleaned)
        if matches:
            redacted.extend(matches)
            cleaned = pattern.sub("", cleaned)

    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ，,。；;:")
    return cleaned, redacted


def search_public_tech_intel(
    query: str,
    settings: Settings,
    *,
    sensitive_terms: Iterable[str] = (),
) -> dict[str, Any]:
    """Run sanitized public technical search only when EXTERNAL_SEARCH_ENABLED is true."""
    assert_no_secrets_leaked(query, settings)
    safe_query, removed = sanitize_external_query(query, sensitive_terms=sensitive_terms)

    if not settings.external_search_enabled:
        return {
            "enabled": False,
            "sanitized_query": safe_query,
            "redacted_terms": removed,
            "results": [],
            "note": "EXTERNAL_SEARCH_ENABLED=false，已阻止外部联网检索。",
        }

    if not safe_query:
        return {
            "enabled": True,
            "sanitized_query": "",
            "redacted_terms": removed,
            "results": [],
            "note": "脱敏剥离敏感实体后查询为空，已取消外搜。",
        }

    return {
        "enabled": True,
        "sanitized_query": safe_query,
        "redacted_terms": removed,
        "results": [],
        "note": f"已按脱敏关键词「{safe_query}」就绪公开检索（剥离敏感词 {len(removed)} 个）。",
    }
