"""Stage 0a MCP-Style Local Corpus Loader for Dr. Siegfried ("Sigi") Praun & Ref Docs."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from pypdf import PdfReader

from vf_ccus_workflow.schemas import EvidenceSearchHit


def _clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_markdown_sections(path: Path) -> list[tuple[str, str]]:
    """Split a Markdown file by headings (## / ###) or compact chunks."""
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []
    blocks: list[tuple[str, str]] = []
    current_title = path.stem
    current_lines: list[str] = []

    for line in text.splitlines():
        if re.match(r"^#{1,3}\s+", line):
            body = "\n".join(current_lines).strip()
            if len(body) >= 40:
                blocks.append((current_title, body))
            current_title = re.sub(r"^#{1,3}\s+", "", line).strip()
            current_lines = []
        else:
            current_lines.append(line)

    tail = "\n".join(current_lines).strip()
    if len(tail) >= 30:
        blocks.append((current_title, tail))

    if not blocks:
        blocks.append((path.stem, text))

    # Merge tiny consecutive blocks and cap oversized chunks
    merged: list[tuple[str, str]] = []
    buf_title = ""
    buf_text = ""
    for title, body in blocks:
        if not buf_text:
            buf_title, buf_text = title, body
        elif len(buf_text) + len(body) < 1200:
            buf_text = f"{buf_text}\n\n[{title}]\n{body}"
        else:
            merged.append((buf_title, buf_text))
            buf_title, buf_text = title, body
    if buf_text:
        merged.append((buf_title, buf_text))

    # Split blocks > 2400 chars into clean slices
    final_chunks: list[tuple[str, str]] = []
    for title, body in merged:
        if len(body) <= 2400:
            final_chunks.append((title, body))
        else:
            step = 1800
            for idx, start in enumerate(range(0, len(body), step), start=1):
                part = body[start : start + step].strip()
                if part:
                    final_chunks.append((f"{title} (Part {idx})", part))
    return final_chunks


# Verified visual extraction for image-only rasterized PDFs (0 text chars via pypdf)
IMAGE_PDF_VISUAL_DIGESTS: dict[str, list[tuple[str, str]]] = {
    "ThermoFisher, Real-time analysis of CO2 purity - 150ppi.pdf": [
        (
            "Pages 1-7/21 (MAX-iR FTIR & MAX-Bev Hardware Architecture)",
            "[p.1-7] Thermo Fisher Scientific presentation: 'Real-time analysis of CO2 purity in beverage and carbon capture applications' (ISBT/EIGA/CCUS). "
            "MAX-iR FTIR Gas Analyzer core features: ZnSe crystal optical beamsplitter (moisture resistant), room-temperature DTGS detector (no liquid nitrogen cooling), "
            "StarBoost optical enhancement technology, 10+ year MTBF source/laser, SQLite-based MAX-Acquisition software, OPC/Modbus industrial communication. "
            "Positioned for both MAX-Bev (beverage grade CO2) and CCS CO2 purity analysis (<24 week system lead time claimed).",
        ),
        (
            "Pages 8-14/21 (MAX-Bev System Cycle, Calibration & Detection Spec)",
            "[p.8-14] MAX-Bev integrated cabinet adds external electrochemical/paramagnetic O2 analyzer and Total Sulfur oxidation converter to the MAX-iR FTIR. "
            "Key operational constraints observed: ~10 minute batch/integrated cycle time for combined sulfur/purity reporting; CO2 purity measurement precision ±0.02%; "
            "requires three calibration/zero gas cylinders (UHP N2 monthly zero, CCS multi-component span mix, and >99.99% CO2 background calibration gas). "
            "Critical physical limitation of FTIR: infrared-inactive homonuclear diatomic and monatomic molecules (H2, N2, Ar, O2) CANNOT be measured directly by MAX-iR FTIR (requires external add-ons for O2 and blind to H2/Ar/N2).",
        ),
        (
            "Pages 15-21/21 (DNV Evaluation Charts & Multi-Impurity Validation)",
            "[p.15-21] DNV independent evaluation charts presented for MAX-iR response to SO2, NO, CH3OH (methanol), CO, C2H5OH (ethanol), and H2O. "
            "Summary vs V&F IMR-MS: MAX-iR/MAX-Bev FTIR offers no direct measurement of H2, Ar, or N2, requires UHP N2 monthly zero + CCS mix + >99.99% CO2 calibration gases, and MAX-Bev runs an ~10-minute batch cycle versus V&F IMR-MS ~1-second continuous measurement.",
        ),
    ]
}


def _extract_pdf_chunks(path: Path, pages_per_chunk: int = 3) -> list[tuple[str, str]]:
    """Extract text chunks per N pages from PDF technical papers & slide decks."""
    reader = PdfReader(str(path))
    chunks: list[tuple[str, str]] = []
    total_pages = len(reader.pages)
    for start in range(0, total_pages, pages_per_chunk):
        end = min(total_pages, start + pages_per_chunk)
        page_texts: list[str] = []
        for idx in range(start, end):
            txt = reader.pages[idx].extract_text() or ""
            txt = _clean_whitespace(txt)
            if txt:
                page_texts.append(f"[p.{idx + 1}] {txt}")
        combined = "\n".join(page_texts).strip()
        if combined:
            label = f"Pages {start + 1}-{end}/{total_pages}"
            chunks.append((label, combined[:2600]))
    if not chunks and path.name in IMAGE_PDF_VISUAL_DIGESTS:
        chunks.extend(IMAGE_PDF_VISUAL_DIGESTS[path.name])
    return chunks


def load_siggi_corpus_hits(siggi_dir: Path) -> list[EvidenceSearchHit]:
    """Parse all primary V&F / Thermo / Shell-IFE docs into normalized EvidenceSearchHits."""
    if not siggi_dir.exists() or not siggi_dir.is_dir():
        return []

    hits: list[EvidenceSearchHit] = []
    all_files = sorted(
        [p for p in siggi_dir.iterdir() if p.is_file() and p.suffix.lower() in {".md", ".pdf"}],
        key=lambda p: p.name.lower(),
    )
    md_stems = {p.stem for p in all_files if p.suffix.lower() == ".md"}
    files = [
        p
        for p in all_files
        if not (p.suffix.lower() == ".pdf" and p.stem in md_stems)
    ]

    for file_path in files:
        encoded_name = quote(file_path.name)
        if file_path.suffix.lower() == ".md":
            sections = _extract_markdown_sections(file_path)
        else:
            sections = _extract_pdf_chunks(file_path, pages_per_chunk=3)

        for idx, (sec_label, body) in enumerate(sections, start=1):
            clean_body = _clean_whitespace(body)
            snippet = clean_body[:420]
            hits.append(
                EvidenceSearchHit(
                    title=f"[Siggi一手资料] {file_path.name} — {sec_label}",
                    url=f"siggi-corpus://{encoded_name}#chunk-{idx}",
                    snippet=snippet,
                    content=body[:3000],
                    source_engine="siggi_mcp",
                    geo_scope="SIGGI",
                    published_at="2024-2026 Primary Corpus",
                    score=1.0,
                )
            )
    return hits
