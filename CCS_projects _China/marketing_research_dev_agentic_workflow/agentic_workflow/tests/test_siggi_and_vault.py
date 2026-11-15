"""Tests for Siggi primary corpus MCP loader, EvidenceVault scoping, and secret guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from vf_ccus_workflow.config import WorkflowSettings, assert_no_secrets_leaked
from vf_ccus_workflow.schemas import EvidenceSearchHit
from vf_ccus_workflow.tools.evidence_vault import EvidenceVault, render_evidence_index
from vf_ccus_workflow.tools.siggi_corpus_loader import load_siggi_corpus_hits


def test_siggi_corpus_loader_parses_real_docs() -> None:
    settings = WorkflowSettings.load()
    hits = load_siggi_corpus_hits(settings.siggi_corpus_dir)
    assert len(hits) >= 15
    assert all(h.geo_scope == "SIGGI" for h in hits)
    assert all(h.source_engine == "siggi_mcp" for h in hits)
    titles = " ".join(h.title for h in hits)
    assert "CCS_Presentation_Meeting_Transcript_and_Analysis.md" in titles
    assert "ThermoFisher" in titles
    assert "Corrosion" in titles


def test_vault_scoping_dedup_and_render(tmp_path: Path) -> None:
    vault = EvidenceVault(tmp_path / "vault.db")
    try:
        r_s = vault.upsert_hit(
            track_id="SIGGI_BASE",
            hit=EvidenceSearchHit(
                title="Brevik QAS",
                url="siggi-corpus://brevik#1",
                snippet="Brevik 400ktpa ~30s cycle 10m heated line",
                source_engine="siggi_mcp",
                geo_scope="SIGGI",
            ),
        )
        r_cn = vault.upsert_hit(
            track_id="T1",
            hit=EvidenceSearchHit(
                title="齐鲁石化-胜利油田CCUS",
                url="https://example.cn/qilu",
                snippet="百万吨级超临界CO2管道工程投运",
                source_engine="metaso",
                geo_scope="CN",
            ),
        )
        r_gl = vault.upsert_hit(
            track_id="T2",
            hit=EvidenceSearchHit(
                title="Northern Lights Ph2",
                url="https://norlights.com/ph2",
                snippet=">5 Mtpa LCO2 shipping and pipeline terminal",
                source_engine="serper",
                geo_scope="GLOBAL",
            ),
        )
        # Duplicate URL should keep existing ID without creating second record
        dup = vault.upsert_hit(
            track_id="T1",
            hit=EvidenceSearchHit(
                title="齐鲁石化-胜利油田CCUS",
                url="https://example.cn/qilu",
                snippet="duplicate snippet",
                source_engine="metaso",
                geo_scope="CN",
            ),
        )
        assert r_s and r_s.ev_id == "EV-SIGGI-001"
        assert r_cn and r_cn.ev_id == "EV-CN-001"
        assert r_gl and r_gl.ev_id == "EV-GL-001"
        assert dup and dup.ev_id == "EV-CN-001"

        stats = vault.stats()
        assert stats["total"] == 3
        assert stats["siggi_count"] == 1
        assert stats["cn_count"] == 1
        assert stats["global_count"] == 1

        md = render_evidence_index(vault.list_all(), db_label="test.db")
        assert "EV-SIGGI-001" in md
        assert "EV-CN-001" in md
        assert "EV-GL-001" in md
    finally:
        vault.close()


def test_secret_leak_guard_blocks_tokens_and_checks_outputs() -> None:
    settings = WorkflowSettings.load()
    assert_no_secrets_leaked("Clean executive markdown with [MKT-CALC] metrics", settings)

    secrets = settings.secret_values()
    if secrets:
        with pytest.raises(AssertionError):
            assert_no_secrets_leaked(f"Oops {secrets[0]} leaked", settings)

    # Also validate any already-generated deliverables in research_outputs/
    out_dir = settings.default_output_dir
    if out_dir.exists():
        for f in out_dir.iterdir():
            if f.is_file() and f.suffix in {".md", ".json", ".svg"}:
                assert_no_secrets_leaked(f.read_text(encoding="utf-8", errors="ignore"), settings)
