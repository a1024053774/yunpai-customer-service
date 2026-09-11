"""Document ingestion for tenant-scoped knowledge.

PDFs are parsed from native text and table geometry when available.  The parser keeps
page boundaries and source metadata so retrieval citations remain auditable.  Docling can
be added by hosts that need heavier layout/formula recognition; this baseline deliberately
has no OCR-only path and never sends uploaded files to a model.
"""

from __future__ import annotations

import hashlib
import io
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .intent import INTENT_ROUTING, routing_for_intent
from .rag import KnowledgeBase


@dataclass(frozen=True, slots=True)
class ImportedDocument:
    id: str
    filename: str
    page: int
    characters: int
    tables: int


class DocumentIngestError(ValueError):
    pass


_ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}
_MAX_BYTES = 20 * 1024 * 1024


def _stored_knowledge_intent(intent: str) -> str:
    """Import UI uses customer intents; knowledge rows use retrieve intents."""
    if intent in INTENT_ROUTING:
        return routing_for_intent(intent)["knowledge_intent"]
    return intent


def ingest_document(
    knowledge: KnowledgeBase,
    *,
    filename: str,
    content: bytes,
    tenant_id: str,
    intent: str = "product_inquiry",
    source_prefix: str = "upload",
    storage_dir: Path | None = None,
) -> list[ImportedDocument]:
    """Parse and index a document into the tenant's knowledge layer."""
    safe_name = Path(filename).name.strip()
    suffix = Path(safe_name).suffix.lower()
    if not safe_name or suffix not in _ALLOWED_SUFFIXES:
        raise DocumentIngestError("仅支持 PDF、TXT 或 Markdown 文件")
    if not content or len(content) > _MAX_BYTES:
        raise DocumentIngestError("文件不能为空且不得超过 20 MiB")
    digest = hashlib.sha256(content).hexdigest()[:16]
    if storage_dir is not None:
        storage_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{digest}-{safe_name}"
        stored_path = storage_dir / stored_name
        if not stored_path.exists():
            stored_path.write_bytes(content)
    if suffix == ".pdf":
        pages = _extract_pdf(content)
    else:
        text = content.decode("utf-8", errors="replace").strip()
        pages = [(1, text, 0)]
    imported: list[ImportedDocument] = []
    for page, text, table_count in pages:
        for chunk_number, chunk in enumerate(_chunks(text), start=1):
            question = f"{safe_name} 第 {page} 页"
            if chunk_number > 1:
                question += f"（片段 {chunk_number}）"
            source = f"{source_prefix}://{safe_name}?sha256={digest}#page={page}&chunk={chunk_number}"
            existing = knowledge.find_by_knowledge_key(source, tenant_id=tenant_id)
            document_id = str(existing["id"]) if existing is not None else knowledge.add_document(
                category="uploaded_document",
                intent=_stored_knowledge_intent(intent),
                question=question,
                answer=chunk,
                keywords=f"{safe_name} 第{page}页",
                risk_level="low",
                source=source,
                tenant_id=tenant_id,
                knowledge_key=source,
                layer="industry",
                review_status="approved",
            )
            imported.append(
                ImportedDocument(
                    id=document_id,
                    filename=safe_name,
                    page=page,
                    characters=len(chunk),
                    tables=table_count,
                )
            )
    if not imported:
        raise DocumentIngestError("文件中没有可索引的文本内容")
    return imported


def _extract_pdf(content: bytes) -> list[tuple[int, str, int]]:
    # Prefer Docling when a host explicitly installs the optional advanced parser. It
    # preserves document hierarchy, reading order and table objects; the lightweight
    # pdfplumber path below remains the deterministic default for the demo.
    try:
        structured = _extract_pdf_docling(content)
        # Docling may leave a sparse/short page empty when its OCR confidence is low.
        # Validate page coverage with native extraction and only use native pages that the
        # structured parser missed; this preserves layout-aware output without dropping
        # recoverable text.
        native = _extract_pdf_pdfplumber(content)
        structured_by_page = {page: (text, tables) for page, text, tables in structured}
        merged: list[tuple[int, str, int]] = []
        for page, native_text, native_tables in native:
            if page in structured_by_page and structured_by_page[page][0].strip():
                text, tables = structured_by_page.pop(page)
                merged.append((page, text, tables))
            else:
                structured_by_page.pop(page, None)
                merged.append((page, native_text, native_tables))
        merged.extend(
            (page, text, tables)
            for page, (text, tables) in structured_by_page.items()
        )
        return sorted(merged, key=lambda page: page[0])
    except ImportError:
        pass
    except Exception:
        # A malformed or unsupported document should still get the native-text parser's
        # error classification rather than silently becoming an empty import.
        pass
    return _extract_pdf_pdfplumber(content)


def _extract_pdf_pdfplumber(content: bytes) -> list[tuple[int, str, int]]:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise DocumentIngestError("缺少 PDF 解析依赖，请安装 pdfplumber") from exc
    pages: list[tuple[int, str, int]] = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                tables = page.extract_tables() or []
                table_text = "\n".join(_table_to_text(table) for table in tables)
                combined = "\n".join(part for part in (text.strip(), table_text.strip()) if part)
                if combined.strip():
                    pages.append((page_number, combined, len(tables)))
    except Exception as exc:
        raise DocumentIngestError(f"PDF 解析失败：{type(exc).__name__}") from exc
    return pages


def _extract_pdf_docling(content: bytes) -> list[tuple[int, str, int]]:
    from docling.document_converter import DocumentConverter

    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(content)
        handle.flush()
        document = DocumentConverter().convert(handle.name).document
    pages: list[tuple[int, str, int]] = []
    for page_number in sorted(document.pages):
        text = document.export_to_markdown(page_no=page_number).strip()
        table_count = sum(
            1
            for table in document.tables
            if any(getattr(provenance, "page_no", None) == page_number for provenance in table.prov)
        )
        if text:
            pages.append((page_number, text, table_count))
    return pages


def _table_to_text(table: list[list[Any]]) -> str:
    rows = []
    for row in table:
        cells = [re.sub(r"\s+", " ", str(cell or "")).strip() for cell in row]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _chunks(text: str, limit: int = 1800) -> list[str]:
    """Split on document structure first, then hard-wrap oversized blocks."""
    normalized = re.sub(r"[ \t]+", " ", text).strip()
    if not normalized:
        return []
    sections = [part.strip() for part in re.split(r"(?m)(?=^#{1,6}\s)", normalized) if part.strip()]
    chunks: list[str] = []
    for section in sections:
        if len(section) <= limit:
            chunks.append(section)
            continue
        paragraphs = [part.strip() for part in re.split(r"\n{2,}|(?<=。)\s*", section) if part.strip()]
        current = ""
        for paragraph in paragraphs:
            if len(current) + len(paragraph) + 1 <= limit:
                current = f"{current}\n{paragraph}".strip()
            else:
                if current:
                    chunks.append(current)
                current = paragraph
                while len(current) > limit:
                    chunks.append(current[:limit].strip())
                    current = current[limit:].strip()
        if current:
            chunks.append(current)
    return chunks
