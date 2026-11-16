"""OEM PDF Datasheet Importer, Online Serper Downloader, and %PDF-/pypdf/SHA256 Verifier."""

from __future__ import annotations

import asyncio
import hashlib
import shutil
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader

from bfbg_workflow.schemas import DatasheetAsset, EvidenceSearchHit
from bfbg_workflow.tools.evidence_vault import EvidenceVault
from bfbg_workflow.tools.search_router import DualEngineSearchRouter

BASELINE_DATASHEET_META: dict[str, tuple[str, str, str]] = {
    "01_Ibsen_I-MON_256_512_USB_Interrogator_Datasheet.pdf": (
        "Ibsen Photonics (Denmark)",
        "I-MON 256 / 512 USB",
        "BS-STD-600 核心光谱解调 OEM 模块",
    ),
    "02_Santec_WSL-110_Tunable_Laser_Source_Datasheet.pdf": (
        "Santec (Japan)",
        "WSL-110",
        "BS-PRO-2000 高密度多通道可调谐激光源",
    ),
    "03_Santec_TSL-570_Swept_Laser_Datasheet.pdf": (
        "Santec (Japan)",
        "TSL-570",
        "BS-PRO-2000 旗舰高速扫频激光源",
    ),
    "04_Amonics_ALS_C-Band_ASE_Broadband_Light_Source_Datasheet.pdf": (
        "Amonics (HK / US)",
        "ALS-CL-15 Series",
        "BS-STD-600 宽带高平坦度 ASE 光源模块",
    ),
    "05_FEMTO_HCA-S-200M-IN_InGaAs_Photoreceiver_TIA_Datasheet.pdf": (
        "FEMTO Messtechnik (Germany)",
        "HCA-S-200M-IN",
        "BS-PRO-2000 200MHz 超低噪声 InGaAs+TIA 接收盒",
    ),
    "06_Sercalo_SW1x16_MEMS_Optical_Switch_Datasheet.pdf": (
        "Sercalo Microtechnology (Switzerland)",
        "SW1x16 / SW1xN-9N",
        "全系通用军工级 MEMS 多路切换光开关",
    ),
    "07_Spectrum_M2p59xx_16bit_PCIe_Digitizer_ADC_Datasheet.pdf": (
        "Spectrum Instrumentation (Germany)",
        "M2p.5922-x4",
        "BS-PRO-2000 16-bit 同步 PCIe 高速采集卡",
    ),
    "08_Wavelength_References_HCN-13_Gas_Cell_Datasheet.pdf": (
        "Wavelength References (USA)",
        "HCN-13 NIST Gas Cell",
        "BS-PRO-2000 NIST 绝对波长校准氰化氢气室",
    ),
    "09_FBGS_FSG-A01_Femtosecond_Grating_Chain_Datasheet.pdf": (
        "FBGS International (Germany/Belgium)",
        "FSG-A01 Femtosecond Grating",
        "Track A 高强度飞秒穿透涂覆层直写高温光栅串",
    ),
    "10_OFS_PyroCoat_HighTemp_Polyimide_Fiber_Datasheet.pdf": (
        "OFS Fitel (USA)",
        "PyroCoat® Polyimide SMF",
        "耐高温聚酰亚胺特种光纤基底 (200 kpsi)",
    ),
    "11_Hamamatsu_G11620_512Pixel_InGaAs_Linear_Sensor_Datasheet.pdf": (
        "Hamamatsu Photonics (Japan)",
        "G11620-512DA",
        "512 像元 InGaAs 线阵图像传感器核心器件",
    ),
}

ADDITIONAL_OEM_SEARCH_SPECS: list[dict[str, Any]] = [
    {
        "target_name": "12_Moxa_MGate_MB3180_Modbus_Gateway_Datasheet.pdf",
        "vendor": "Moxa (Taiwan / Global)",
        "part_number": "MGate MB3180 / MB3280",
        "subsystem": "电厂 DCS 只读通讯协议网关 (Modbus RTU/TCP)",
        "query": 'filetype:pdf "MGate MB3180" datasheet moxa',
        "direct_urls": [
            "https://www.moxa.com/getmedia/4e443188-4666-4239-8900-d945f2c216e1/moxa-mgate-mb3180-mb3280-mb3480-series-datasheet-v1.8.pdf",
        ],
    },
    {
        "target_name": "13_MeanWell_NDR-240_Industrial_DIN_PSU_Datasheet.pdf",
        "vendor": "Mean Well (Taiwan / Global)",
        "part_number": "NDR-240-24 / SDR-240-24",
        "subsystem": "工业 24V 冗余导轨开关电源",
        "query": 'filetype:pdf "NDR-240" datasheet meanwell',
        "direct_urls": [
            "https://www.meanwell.com/Upload/PDF/NDR-240/NDR-240-SPEC.PDF",
        ],
    },
    {
        "target_name": "14_Advantech_ARK-2250L_Industrial_Edge_PC_Datasheet.pdf",
        "vendor": "Advantech 研华",
        "part_number": "ARK-2250L / UNO-2484G",
        "subsystem": "无风扇工业级边缘解调与旁路 AI 计算主机",
        "query": 'filetype:pdf "ARK-2250L" OR "UNO-2484G" datasheet advantech',
        "direct_urls": [],
    },
    {
        "target_name": "15_Fibercore_SM1500_HighTemp_Specialty_Fiber_Datasheet.pdf",
        "vendor": "Fibercore (UK)",
        "part_number": "SM1500(9/125)P / SM1500SC",
        "subsystem": "Track A 纯石英芯/聚酰亚胺超高温抗氢损特种光纤",
        "query": 'filetype:pdf "SM1500" polyimide fibercore datasheet',
        "direct_urls": [],
    },
    {
        "target_name": "16_Thorlabs_PDB470C_Balanced_InGaAs_Photoreceiver_Datasheet.pdf",
        "vendor": "Thorlabs (USA)",
        "part_number": "PDB470C / 6015-3-APC Circulator",
        "subsystem": "高速 InGaAs 光电接收/光学环形器备选供应链",
        "query": 'filetype:pdf "PDB470C" thorlabs manual OR datasheet',
        "direct_urls": [
            "https://www.thorlabs.com/drawings/d5249cb83d6a2d5a-633A83F5-97AC-B390-30DF8FF4259E7CD0/PDB470C-SpecSheet.pdf",
        ],
    },
    {
        "target_name": "17_AMETEK_Jofra_CTC660_DryBlock_Calibrator_Datasheet.pdf",
        "vendor": "AMETEK Jofra (Denmark)",
        "part_number": "CTC-660 / RTC-700",
        "subsystem": "量产 650°C 高温干体/管式计量标定炉 (NPI 标定核心工装)",
        "query": 'filetype:pdf "CTC-660" OR "RTC-700" "AMETEK" OR "Jofra" datasheet',
        "direct_urls": [],
    },
    {
        "target_name": "18_Phoenix_Contact_QUINT4_PS_Redundant_Datasheet.pdf",
        "vendor": "Phoenix Contact (Germany)",
        "part_number": "QUINT4-PS/1AC/24DC/10",
        "subsystem": "高可靠发电厂防浪涌 24V 电源备选",
        "query": 'filetype:pdf "QUINT4-PS/1AC/24DC/10" datasheet',
        "direct_urls": [],
    },
]


def verify_pdf_file(pdf_path: Path, *, max_size_mb: float = 9.5) -> tuple[bool, int, str, str]:
    """Validate %PDF- magic header, size limits, pypdf readability, and SHA256."""
    if not pdf_path.exists() or not pdf_path.is_file():
        return False, 0, "", "missing_file"
    size_bytes = pdf_path.stat().st_size
    if size_bytes < 4096 or size_bytes > int(max_size_mb * 1024 * 1024):
        return False, 0, "", f"size_out_of_bounds:{size_bytes}"
    with pdf_path.open("rb") as f:
        header = f.read(8)
    if not header.startswith(b"%PDF-"):
        return False, 0, "", "invalid_pdf_magic"
    try:
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)
        if page_count < 1:
            return False, 0, "", "zero_pages"
        extracted_chunks: list[str] = []
        for idx in range(min(3, page_count)):
            txt = (reader.pages[idx].extract_text() or "").strip()
            if txt:
                extracted_chunks.append(txt[:900])
        summary_text = " ".join(" ".join(extracted_chunks).split())[:750]
        if not summary_text:
            summary_text = f"Verified PDF ({page_count} pages, {size_bytes // 1024} KB)"
    except Exception as exc:
        return False, 0, "", f"pypdf_error:{exc}"

    sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    return True, page_count, sha256, summary_text


async def _download_verified_pdf(
    urls: list[str],
    dest_path: Path,
    *,
    max_size_mb: float = 9.5,
) -> tuple[bool, str, int, str, str]:
    """Try clean public PDF links sequentially without bypassing any auth/captcha."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; BoilerSense-RD-Research/1.0)",
        "Accept": "application/pdf,*/*;q=0.8",
    }
    tmp_path = dest_path.with_suffix(".pdf.tmp")
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        for url in urls:
            if not url or not url.startswith("http"):
                continue
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    continue
                content = resp.content
                if not content.startswith(b"%PDF-"):
                    continue
                if len(content) < 4096 or len(content) > int(max_size_mb * 1024 * 1024):
                    continue
                tmp_path.write_bytes(content)
                ok, pages, sha, summary = verify_pdf_file(tmp_path, max_size_mb=max_size_mb)
                if ok:
                    tmp_path.replace(dest_path)
                    return True, url, pages, sha, summary
                tmp_path.unlink(missing_ok=True)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                continue
    return False, "", 0, "", ""


async def sync_and_fetch_datasheets(
    *,
    prior_datasheets_dir: Path,
    target_datasheets_dir: Path,
    vault: EvidenceVault,
    search_router: DualEngineSearchRouter,
    max_size_mb: float = 9.5,
    skip_online_download: bool = False,
) -> list[DatasheetAsset]:
    """Copy & verify 11 baseline OEM PDFs and fetch additional integration component PDFs online."""
    target_datasheets_dir.mkdir(parents=True, exist_ok=True)
    assets: list[DatasheetAsset] = []

    # 1. Baseline OEM PDFs (copied from read-only Boiler_FBG_Thermometry_Research)
    if prior_datasheets_dir.exists():
        for pdf_file in sorted(prior_datasheets_dir.glob("*.pdf")):
            dest = target_datasheets_dir / pdf_file.name
            if not dest.exists():
                shutil.copy2(pdf_file, dest)
            ok, pages, sha, summary = verify_pdf_file(dest, max_size_mb=max_size_mb)
            if not ok:
                continue
            vendor, part_num, subsystem = BASELINE_DATASHEET_META.get(
                pdf_file.name, ("OEM Vendor", pdf_file.stem, "Optical/Fiber Component")
            )
            rec = vault.upsert_hit(
                track_id="PDF_BASELINE",
                hit=EvidenceSearchHit(
                    title=f"OEM Datasheet: {vendor} {part_num}",
                    url=f"local-pdf://{pdf_file.name}",
                    snippet=f"{subsystem} | {summary[:420]}",
                    content=summary,
                    source_engine="pdf_datasheet",
                    geo_scope="PDF",
                    published_at="2026",
                    score=1.0,
                ),
            )
            if rec:
                asset = DatasheetAsset(
                    ev_id=rec.ev_id,
                    filename=pdf_file.name,
                    vendor=vendor,
                    part_number=part_num,
                    subsystem=subsystem,
                    source_url=f"local-pdf://{pdf_file.name}",
                    origin_type="baseline_copied",
                    page_count=pages,
                    file_size_bytes=dest.stat().st_size,
                    sha256=sha,
                    key_specs_summary=summary,
                )
                vault.upsert_datasheet(asset)
                assets.append(asset)

    if skip_online_download:
        return assets

    # 2. Online OEM PDF discovery & download for additional industrial integration parts
    async def _fetch_spec(spec: dict[str, Any]) -> DatasheetAsset | None:
        dest = target_datasheets_dir / spec["target_name"]
        if dest.exists():
            ok, pages, sha, summary = verify_pdf_file(dest, max_size_mb=max_size_mb)
            if ok:
                rec = vault.upsert_hit(
                    track_id="PDF_ONLINE",
                    hit=EvidenceSearchHit(
                        title=f"OEM Datasheet: {spec['vendor']} {spec['part_number']}",
                        url=f"local-pdf://{spec['target_name']}",
                        snippet=f"{spec['subsystem']} | {summary[:420]}",
                        content=summary,
                        source_engine="pdf_datasheet",
                        geo_scope="PDF",
                        published_at="2026",
                        score=1.0,
                    ),
                )
                if rec:
                    asset = DatasheetAsset(
                        ev_id=rec.ev_id,
                        filename=spec["target_name"],
                        vendor=spec["vendor"],
                        part_number=spec["part_number"],
                        subsystem=spec["subsystem"],
                        source_url=f"local-pdf://{spec['target_name']}",
                        origin_type="downloaded_online",
                        page_count=pages,
                        file_size_bytes=dest.stat().st_size,
                        sha256=sha,
                        key_specs_summary=summary,
                    )
                    vault.upsert_datasheet(asset)
                    return asset

        candidate_urls: list[str] = list(spec.get("direct_urls", []))
        hits = await search_router.search_track(
            track_id="PDF_FETCH",
            geo_scope="PDF",
            query=spec["query"],
            num_results=6,
            use_time_filter=False,
        )
        for h in hits:
            if h.url not in candidate_urls:
                candidate_urls.append(h.url)

        ok, src_url, pages, sha, summary = await _download_verified_pdf(
            candidate_urls, dest, max_size_mb=max_size_mb
        )
        if not ok:
            return None

        rec = vault.upsert_hit(
            track_id="PDF_ONLINE",
            hit=EvidenceSearchHit(
                title=f"OEM Datasheet: {spec['vendor']} {spec['part_number']}",
                url=src_url,
                snippet=f"{spec['subsystem']} | {summary[:420]}",
                content=summary,
                source_engine="pdf_datasheet",
                geo_scope="PDF",
                published_at="2026",
                score=0.95,
            ),
        )
        if not rec:
            return None
        asset = DatasheetAsset(
            ev_id=rec.ev_id,
            filename=spec["target_name"],
            vendor=spec["vendor"],
            part_number=spec["part_number"],
            subsystem=spec["subsystem"],
            source_url=src_url,
            origin_type="downloaded_online",
            page_count=pages,
            file_size_bytes=dest.stat().st_size,
            sha256=sha,
            key_specs_summary=summary,
        )
        vault.upsert_datasheet(asset)
        return asset

    online_results = await asyncio.gather(*(_fetch_spec(spec) for spec in ADDITIONAL_OEM_SEARCH_SPECS))
    for item in online_results:
        if item is not None:
            assets.append(item)

    return assets
