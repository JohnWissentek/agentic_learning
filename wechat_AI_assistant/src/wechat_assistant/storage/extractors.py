"""Page-level document text extractors for PDF, Word, Excel, ZIP, CSV/text, and safe binary fallback."""

from __future__ import annotations

import csv
import io
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

_MEDIA_SUFFIXES = {
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
}

_TEXT_SUFFIXES = {".txt", ".md", ".csv", ".tsv", ".json", ".log", ".yaml", ".yml", ".xml", ".eml"}

_MAX_ZIP_FILES = 30
_MAX_ZIP_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB zip-bomb guard


def _looks_like_text(raw: bytes) -> bool:
    if not raw:
        return True
    if b"\x00" in raw[:4096]:
        return False
    try:
        raw[:4096].decode("utf-8")
        return True
    except UnicodeDecodeError:
        try:
            raw[:4096].decode("gb18030")
            return True
        except UnicodeDecodeError:
            return False


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return ""


def _extract_zip_pages(p: Path, *, depth: int) -> list[dict[str, Any]]:
    if depth >= 2:
        return [{"page": 1, "text": f"[嵌套压缩包跳过解析（原件已归档）: {p.name}]"}]
    if not zipfile.is_zipfile(p):
        return [{"page": 1, "text": f"[未解析压缩包（格式异常或损坏，原件已归档）: {p.name}]"}]

    pages: list[dict[str, Any]] = []
    total_bytes = 0
    processed_files = 0
    try:
        with zipfile.ZipFile(p, "r") as zf, tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir).resolve()
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if info.flag_bits & 0x1:
                    pages.append({"page": len(pages) + 1, "text": f"[加密压缩文件无法解析正文（原件已归档）: {p.name}/{info.filename}]"})
                    continue
                processed_files += 1
                if processed_files > _MAX_ZIP_FILES:
                    pages.append({"page": len(pages) + 1, "text": f"[压缩包内文件超过 {_MAX_ZIP_FILES} 个上限，其余已保留原件]"})
                    break
                # Zip-slip path traversal guard (strict is_relative_to blocks sibling-prefix tricks)
                dest = (tmp_root / info.filename).resolve()
                if not dest.is_relative_to(tmp_root):
                    continue
                if info.file_size and total_bytes + max(0, info.file_size) > _MAX_ZIP_UNCOMPRESSED_BYTES:
                    pages.append({"page": len(pages) + 1, "text": "[压缩包解压体积超限，已停止展开，原件已归档]"})
                    break
                dest.parent.mkdir(parents=True, exist_ok=True)
                exceeded = False
                with zf.open(info, "r") as src, dest.open("wb") as dst:
                    while True:
                        chunk = src.read(65536)
                        if not chunk:
                            break
                        total_bytes += len(chunk)
                        if total_bytes > _MAX_ZIP_UNCOMPRESSED_BYTES:
                            exceeded = True
                            break
                        dst.write(chunk)
                if exceeded:
                    try:
                        dest.unlink(missing_ok=True)
                    except OSError:
                        pass
                    pages.append({"page": len(pages) + 1, "text": "[压缩包解压体积超限，已停止展开，原件已归档]"})
                    break

                inner_pages = extract_document_pages(dest, _zip_depth=depth + 1)
                for ip in inner_pages:
                    txt = (ip.get("text") or "").strip()
                    if txt:
                        pages.append(
                            {
                                "page": len(pages) + 1,
                                "text": f"[ZIP内文件: {info.filename}｜第{ip.get('page', 1)}页]\n{txt}",
                            }
                        )
    except RuntimeError as exc:
        if "encrypted" in str(exc).lower() or "password" in str(exc).lower():
            return [{"page": 1, "text": f"[加密压缩包无法自动提取正文（原件已归档，请补充说明）: {p.name}]"}]
        return [{"page": 1, "text": f"[压缩包暂无法解析（原件已归档）: {p.name}]"}]
    except Exception:
        return [{"page": 1, "text": f"[压缩包暂无法解析（原件已归档）: {p.name}]"}]

    return pages or [{"page": 1, "text": f"[压缩包内未提取到文本（原件已归档）: {p.name}]"}]


def extract_document_pages(file_path: str | Path, *, _zip_depth: int = 0) -> list[dict[str, Any]]:
    """Extract numbered pages or structured sheets from a document for citation RAG."""
    p = Path(file_path)
    suffix = p.suffix.lower()

    if suffix == ".pdf":
        try:
            reader = PdfReader(str(p))
            if getattr(reader, "is_encrypted", False):
                return [{"page": 1, "text": f"[加密 PDF 无法自动提取正文（原件已归档，请补充说明）: {p.name}]"}]
            pages: list[dict[str, Any]] = []
            for idx, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                pages.append({"page": idx, "text": text})
            if pages and not any(pg["text"] for pg in pages):
                return [
                    {
                        "page": 1,
                        "text": f"[扫描件/图片型 PDF（共 {len(pages)} 页）暂未提取到可选中文本，原件已归档，请补充一句说明]: {p.name}",
                    }
                ]
            return pages
        except Exception:
            return [{"page": 1, "text": f"[PDF 暂无法解析正文（原件已归档，请补充说明）: {p.name}]"}]

    if suffix == ".docx":
        try:
            doc = Document(str(p))
            lines = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
            for tbl in doc.tables:
                for row in tbl.rows:
                    cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                    if any(cells):
                        lines.append(" | ".join(cells))
            return [{"page": 1, "text": "\n".join(lines)}]
        except Exception:
            return [{"page": 1, "text": f"[Word 文档暂无法解析正文（可能已加密或格式损坏，原件已归档）: {p.name}]"}]

    if suffix in {".xlsx", ".xlsm"}:
        try:
            wb = load_workbook(filename=str(p), data_only=True, read_only=True)
            try:
                pages = []
                for idx, name in enumerate(wb.sheetnames, start=1):
                    ws = wb[name]
                    rows_txt: list[str] = [f"[Sheet: {name}]"]
                    for row in ws.iter_rows(values_only=True):
                        vals = [str(v) if v is not None else "" for v in row]
                        if any(vals):
                            rows_txt.append(" | ".join(vals))
                    pages.append({"page": idx, "sheet": name, "text": "\n".join(rows_txt)})
                return pages
            finally:
                wb.close()
        except Exception:
            return [{"page": 1, "text": f"[Excel 表格暂无法解析正文（可能已加密或格式损坏，原件已归档）: {p.name}]"}]

    if suffix == ".zip":
        return _extract_zip_pages(p, depth=_zip_depth)

    if suffix in _MEDIA_SUFFIXES:
        return [{"page": 1, "text": f"[Media attachment: {p.name}]"}]

    raw_bytes = p.read_bytes()
    if suffix in {".csv", ".tsv"}:
        decoded = _decode_text(raw_bytes)
        delim = "\t" if suffix == ".tsv" else ","
        rows = [" | ".join(r) for r in csv.reader(io.StringIO(decoded), delimiter=delim) if any(r)]
        return [{"page": 1, "text": "\n".join(rows)}]

    if suffix in _TEXT_SUFFIXES or _looks_like_text(raw_bytes):
        return [{"page": 1, "text": _decode_text(raw_bytes)}]

    size_kb = max(1, round(len(raw_bytes) / 1024))
    return [
        {
            "page": 1,
            "text": f"[未解析二进制附件（{suffix or '未知格式'}，{size_kb} KB），不支持自动提取正文，原件已归档，请补充文字/语音说明]: {p.name}",
        }
    ]
