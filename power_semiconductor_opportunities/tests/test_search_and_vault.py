"""Tests for Metaso/Serper search contracts, SQLite EvidenceVault, and secret leak guard."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pso_workflow.config import WorkflowSettings, unwrap_json_container_strings
from pso_workflow.schemas import (
    BuyerPersonaAssessment,
    CritiqueVerdict,
    ResearchPlan,
    SearchHit,
)
from pso_workflow.tools.evidence_vault import (
    EvidenceVault,
    normalize_url,
    score_source_authority,
)
from pso_workflow.tools.search_router import MetasoAPIError, MetasoClient


def test_metaso_size_page_mutual_exclusion() -> None:
    client = MetasoClient(api_key="mk-dummy")
    p1 = client.build_search_payload(query="SiC 外延", scope="webpage", size=10)
    assert p1["size"] == 10 and "page" not in p1

    p2 = client.build_search_payload(query="SiC 外延", scope="webpage", size=None, page=2)
    assert p2["page"] == 2 and "size" not in p2

    with pytest.raises(ValueError, match="errCode=1000"):
        client.build_search_payload(query="SiC 外延", scope="webpage", size=10, page=2)


def test_metaso_http200_errcode_handling_and_scope_parsing() -> None:
    with pytest.raises(MetasoAPIError) as exc_info:
        MetasoClient.parse_search_response(
            {"errCode": 2005, "errMsg": "invalid key"}, scope="webpage", query="q"
        )
    assert exc_info.value.err_code == 2005

    hits, credits = MetasoClient.parse_search_response(
        {
            "errCode": 0,
            "credits": 3,
            "scholars": [
                {
                    "title": "IEEE SiC Wafer PL Metrology",
                    "link": "https://ieeexplore.ieee.org/document/12345/?utm_source=x",
                    "summary": "Non-destructive PL inspection.",
                    "date": "2026-05-01",
                }
            ],
        },
        scope="scholar",
        query="SiC PL",
        geo_scope="CN",
    )
    assert credits == 3
    assert len(hits) == 1
    assert hits[0].authority_tier == "T1"
    assert hits[0].geo_scope == "CN"


def test_evidence_vault_dedup_and_authority(tmp_path: Path) -> None:
    vault = EvidenceVault(tmp_path / "vault.db")
    try:
        h1 = SearchHit(
            engine="metaso",
            geo_scope="CN",
            query="特高压 C4F7N",
            title="国家电网环保气体标准",
            url="https://www.sgcc.com.cn/news/100/?utm_source=baidu&from=timeline",
            snippet="环保气体在线监测规范",
        )
        h2 = SearchHit(
            engine="serper",
            geo_scope="CN",
            query="特高压 C4F7N",
            title="国家电网环保气体标准",
            url="https://www.sgcc.com.cn/news/100",
            snippet="duplicate without utm",
        )
        r1 = vault.upsert_hit(track_id="P3", hit=h1)
        r2 = vault.upsert_hit(track_id="P3", hit=h2, full_markdown="# 完整正文\n\n至少超过二百字的测试内容..." * 12)
        assert r1 is not None and r2 is not None
        assert r1.ev_id == r2.ev_id == "EV-CN-001"
        assert r1.authority_tier == "T1"
        assert normalize_url(h1.url) == normalize_url(h2.url)

        stats = vault.stats()
        assert stats["total"] == 1
        assert stats["cn_count"] == 1
        assert stats["with_fulltext_count"] == 1
        assert score_source_authority("https://semi.org/en/standards") == "T1"
    finally:
        vault.close()


def test_no_secret_tokens_leaked_in_tracked_files() -> None:
    """Ch 18 Guardrail: ensure raw paid tokens never appear in tracked project files."""
    settings = WorkflowSettings.load()
    root = settings.root_dir
    forbidden_values = [
        v
        for v in (settings.metaso_api_key, settings.serper_api_key, settings.dashscope_api_key)
        if v and len(v) >= 16 and not v.startswith("your")
    ]
    # Also check parent github token if readable
    gh_tok_file = root.parent / ".env.tokens"
    if gh_tok_file.exists():
        for line in gh_tok_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                val = line.split("=", 1)[1].strip().strip('"\'')
                if len(val) >= 16:
                    forbidden_values.append(val)

    skip_dirs = {".venv", "__pycache__", ".pytest_cache", "data", "outputs", ".git"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            if fn.startswith(".env"):
                continue
            fp = Path(dirpath) / fn
            if fp.suffix in {".db", ".pyc", ".png", ".pdf"}:
                continue
            text = fp.read_text(encoding="utf-8", errors="ignore")
            for secret in forbidden_values:
                assert secret not in text, f"Secret leaked into tracked file: {fp}"


def test_unwrap_stringified_json_and_schema_validators() -> None:
    raw = {
        "contract_id": "PSO-CONTRACT-2026-V1",
        "sector_filter": "all",
        "profile": "flagship",
        "step_back_thesis": "在线传感决定制造良率与双碳ROI。",
        "track_plans": [
            {
                "track_id": "P1",
                "sector": "Power & Energy",
                "name": "储能电池",
                "step_back_physics_principle": "激光超声与电化学原位测量。",
                "cn_queries": '[{"关键词": "极片在线检测"}]',
                "global_queries": "[]",
            }
        ],
    }
    coerced = unwrap_json_container_strings(raw)
    plan = ResearchPlan.model_validate(coerced)
    assert plan.track_plans[0].sector == "power_energy"
    assert plan.track_plans[0].cn_queries == [{"关键词": "极片在线检测", "query": "极片在线检测"}]
    assert plan.track_plans[0].global_queries == []

    persona = BuyerPersonaAssessment(
        persona_role="财务/采购成本负责人 (CFO ROI Gatekeeper)",
        core_question="多快回本？",
        adoption_barrier="CAPEX偏高",
        spec_in_trigger="12个月内回收",
        recommended_product_tweak="模块化旁路设计",
    )
    assert persona.persona_role == "CFO / Procurement ROI Gatekeeper"

    with pytest.raises(Exception):
        CritiqueVerdict(
            decision="REV_NEEDED",  # type: ignore[arg-type]
            overall_confidence=75.0,
            summary="补齐S3碳化硅证据",
            gap_queries=["SiC 晶圆级动态 KGD 测试 中国产线"],
        )

    verdict = CritiqueVerdict(
        decision="needs_more_evidence",
        overall_confidence=75.0,
        summary="补齐S3碳化硅证据",
        gap_queries=["SiC 晶圆级动态 KGD 测试 中国产线"],
    )
    assert verdict.decision == "needs_more_evidence"
    assert verdict.gap_queries[0]["track_id"] == "S3"
    assert verdict.gap_queries[0]["query"] == "SiC 晶圆级动态 KGD 测试 中国产线"
