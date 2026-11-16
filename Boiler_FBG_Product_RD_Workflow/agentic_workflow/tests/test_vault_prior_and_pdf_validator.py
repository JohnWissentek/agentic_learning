"""Tests for EvidenceVault deduplication, prior corpus ingestion, PDF verification & secret guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from bfbg_workflow.config import WorkflowSettings, assert_no_secrets_leaked
from bfbg_workflow.nodes.critic_and_judge import normalize_volume_markdown
from bfbg_workflow.schemas import EvidenceSearchHit
from bfbg_workflow.tools.datasheet_fetcher import verify_pdf_file
from bfbg_workflow.tools.evidence_vault import EvidenceVault, deterministic_contract_checks
from bfbg_workflow.tools.prior_corpus_loader import ingest_prior_research_corpus


def test_evidence_vault_dedup_and_scoping(tmp_path: Path) -> None:
    vault = EvidenceVault(tmp_path / "vault.db")
    try:
        h1 = EvidenceSearchHit(
            title="Test CN",
            url="https://example.cn/boiler",
            snippet="煤电深调峰水冷壁测温",
            source_engine="metaso",
            geo_scope="CN",
        )
        r1 = vault.upsert_hit(track_id="T1_MARKET_POLICY", hit=h1)
        r2 = vault.upsert_hit(track_id="T1_MARKET_POLICY", hit=h1)
        assert r1 is not None and r2 is not None
        assert r1.ev_id == r2.ev_id == "EV-CN-0001"

        h2 = EvidenceSearchHit(
            title="Test GL",
            url="https://example.com/ibsen",
            snippet="Ibsen I-MON 512",
            source_engine="serper",
            geo_scope="GLOBAL",
        )
        r3 = vault.upsert_hit(track_id="T3_OPTICS_HARDWARE", hit=h2)
        assert r3 is not None and r3.ev_id == "EV-GL-0001"
        assert vault.stats()["TOTAL"] == 2
    finally:
        vault.close()


def test_prior_corpus_and_baseline_pdfs_verify() -> None:
    settings = WorkflowSettings.load()
    if settings.prior_research_dir.exists():
        pdf_dir = settings.prior_research_dir / "06_300Pts_System_Design_and_Datasheets" / "Datasheets_PDF"
        pdfs = sorted(pdf_dir.glob("*.pdf"))
        assert len(pdfs) == 11
        for p in pdfs:
            ok, pages, sha, summary = verify_pdf_file(p)
            assert ok, f"Failed PDF check on {p.name}: {summary}"
            assert pages >= 1
            assert len(sha) == 64


def test_pdf_rejects_html_poison_and_secret_guard(tmp_path: Path) -> None:
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"<html><body>403 Forbidden</body></html>" * 200)
    ok, _, _, reason = verify_pdf_file(fake_pdf)
    assert not ok
    assert reason == "invalid_pdf_magic"

    settings = WorkflowSettings.load()
    if settings.secret_values():
        secret = settings.secret_values()[0]
        with pytest.raises(AssertionError):
            assert_no_secrets_leaked(f"Leaked key: {secret}", settings)


def test_prior_loader_and_contract_checks(tmp_path: Path) -> None:
    vault = EvidenceVault(tmp_path / "v.db")
    try:
        recs = ingest_prior_research_corpus(WorkflowSettings.load().prior_research_dir, vault)
        assert len(recs) >= 15
        out_dir = tmp_path / "out"
        (out_dir / "datasheets_pdf").mkdir(parents=True)
        vols = {
            "00_EXECUTIVE_PRODUCT_CHARTER_AND_ROADMAP.md": f"Ref [{recs[0].ev_id}] and [EV-CN-9999].",
        }
        chk = deterministic_contract_checks(
            vault=vault,
            volumes=vols,
            output_dir=out_dir,
            contract={"required_output_volumes": ["00_EXECUTIVE_PRODUCT_CHARTER_AND_ROADMAP.md"]},
        )
        assert chk["invalid_citations_count"] == 1
        assert chk["invalid_citations"]["00_EXECUTIVE_PRODUCT_CHARTER_AND_ROADMAP.md"] == ["EV-CN-9999"]
    finally:
        vault.close()


def test_normalize_volume_markdown() -> None:
    raw = (
        "See [spec](file:///Users/john/Desktop/agentic_learning/datasheets_pdf/01_Ibsen_I-MON_256_512_USB_Interrogator_Datasheet.pdf) "
        "and [doc](file:///datasheets_pdf/17_AMETEK_Jofra_CTC660_DryBlock_Calibrator_Datasheet.pdf) "
        "with [[EV-PDF-0001]] and [[EV-CN-0014]]."
    )
    cleaned = normalize_volume_markdown(raw)
    assert "file://" not in cleaned
    assert "(./datasheets_pdf/01_Ibsen_I-MON_256_512_USB_Interrogator_Datasheet.pdf)" in cleaned
    assert "(./datasheets_pdf/17_AMETEK_Jofra_CTC660_DryBlock_Calibrator_Datasheet.pdf)" in cleaned
    assert "[EV-PDF-0001]" in cleaned and "[[EV-PDF-0001]]" not in cleaned
    assert "[EV-CN-0014]" in cleaned and "[[EV-CN-0014]]" not in cleaned
