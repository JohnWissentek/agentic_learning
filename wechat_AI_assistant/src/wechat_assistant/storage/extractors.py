"""Page-level document text extractors for PDF, Word, Excel, and plain text."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from pypdf import PdfReader
from docx import Document


def extract_document_pages(file_path: str | Path) -> list[dict[str, Any]]:
    """Extract numbered pages or structured sheets from a document for citation RAG."""
    p = Path(file_path)
    suffix = p.suffix.lower()

    if suffix == ".pdf":
        reader = PdfReader(str(p))
        pages: list[dict[str, Any]] = []
        for idx, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            pages.append({"page": idx, "text": text})
        return pages

    if suffix == ".docx":
        doc = Document(str(p))
        lines = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        for tbl in doc.tables:
            for row in tbl.rows:
                cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                if any(cells):
                    lines.append(" | ".join(cells))
        return [{"page": 1, "text": "\n".join(lines)}]

    if suffix in {".xlsx", ".xlsm"}:
        wb = load_workbook(filename=str(p), data_only=True, read_only=True)
        pages = []
        for idx, name in enumerate(wb.sheetnames, start=1):
            ws = wb[name]
            rows_txt: list[str] = [f"[Sheet: {name}]"]
            for row in ws.iter_rows(values_only=True):
                vals = [str(v) if v is not None else "" for v in row]
                if any(vals):
                    rows_txt.append(" | ".join(vals))
            pages.append({"page": idx, "sheet": name, "text": "\n".join(rows_txt)})
        wb.close()
        return pages

    if suffix in {
        ".amr",
        ".mp3",
        ".wav",
        ".m4a",
        ".ogg",
        ".silk",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".mp4",
        ".mov",
        ".bin",
    }:
        return [{"page": 1, "text": f"[Media attachment: {p.name}]"}]

    text = p.read_text(encoding="utf-8", errors="replace").strip()
    return [{"page": 1, "text": text}]


def parse_excel_quote_rows(file_path: str | Path, sheet_index: int = 0) -> list[dict[str, Any]]:
    """Extract normalized numeric quote rows from an Excel sheet for deterministic Diff."""
    wb = load_workbook(filename=str(file_path), data_only=True, read_only=True)
    try:
        sheet = wb[wb.sheetnames[sheet_index]]
        all_rows = list(sheet.iter_rows(values_only=True))
    finally:
        wb.close()

    if not all_rows:
        return []

    headers = [str(h or f"col_{i}").strip() for i, h in enumerate(all_rows[0])]
    records: list[dict[str, Any]] = []
    for r_idx, row in enumerate(all_rows[1:], start=2):
        if not any(v is not None and str(v).strip() != "" for v in row):
            continue
        item = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
        item["_row_num"] = r_idx
        records.append(item)
    return records
