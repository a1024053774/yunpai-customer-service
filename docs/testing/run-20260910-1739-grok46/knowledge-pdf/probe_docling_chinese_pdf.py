# -*- coding: utf-8 -*-
"""L0/L2-parser probe: Docling importability and Chinese electronic PDF truth."""
from __future__ import annotations

import importlib
import json
import re
import sys
import tempfile
import unicodedata
from io import BytesIO
from pathlib import Path

ROOT = Path("/tmp/yunpai-test-candidate-grok46-pZG5r3")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
NNNN_RE = re.compile(r"n{4,}")
P1_A = "\u7a7a\u6c14\u70b8\u9505\u5bb9\u91cf 5L"
P1_B = "\u9002\u5408 3-4 \u4eba\u5bb6\u5ead"
P1_C = "\u5bb9\u91cf"
P2_A = "\u552e\u540e\u4fdd\u4fee\u4e00\u5e74"
TRUTH = {
    "page1_phrases": [P1_A, P1_B, P1_C, "5L"],
    "page2_phrases": [P2_A],
}


def _pdf_bytes() -> bytes:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    out = BytesIO()
    doc = canvas.Canvas(out)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    doc.setFont("STSong-Light", 12)
    doc.drawString(72, 760, P1_A)
    doc.drawString(72, 740, P1_B)
    doc.line(72, 700, 240, 700)
    doc.line(72, 680, 240, 680)
    doc.line(72, 660, 240, 660)
    doc.line(72, 700, 72, 660)
    doc.line(156, 700, 156, 660)
    doc.line(240, 700, 240, 660)
    doc.drawString(80, 686, P1_C)
    doc.drawString(164, 686, "5L")
    doc.showPage()
    doc.setFont("STSong-Light", 12)
    doc.drawString(72, 760, P2_A)
    doc.save()
    return out.getvalue()


def _char_stats(text: str) -> dict:
    cjk = CJK_RE.findall(text)
    return {
        "chars": len(text),
        "cjk_count": len(cjk),
        "cjk_sample": "".join(cjk[:24]),
        "nnnn_runs": NNNN_RE.findall(text),
        "has_real_chinese": len(cjk) >= 4,
        "looks_like_nnnn_corruption": bool(NNNN_RE.search(text)) and len(cjk) < 4,
    }


def extract_pdfplumber(content: bytes) -> list[dict]:
    import pdfplumber

    pages = []
    with pdfplumber.open(BytesIO(content)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(
                {"page": index, "extractor": "pdfplumber", "text": text, **_char_stats(text)}
            )
    return pages


def extract_pypdf(content: bytes):
    try:
        from pypdf import PdfReader
    except ImportError:
        return {"available": False}
    reader = PdfReader(BytesIO(content))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"page": index, "extractor": "pypdf", "text": text, **_char_stats(text)})
    return pages


def probe_docling() -> dict:
    try:
        module = importlib.import_module("docling")
        version = getattr(module, "__version__", None)
        from docling.document_converter import DocumentConverter

        return {
            "importable": True,
            "version": version,
            "module_file": getattr(module, "__file__", None),
            "DocumentConverter_importable": DocumentConverter is not None,
        }
    except Exception as exc:
        return {"importable": False, "error": f"{type(exc).__name__}: {exc}"}


def ingest_and_read(content: bytes, dest_pdf: Path) -> dict:
    from customer_service_fixtures import build_core, principal_for_core
    from yunpai_customer_service.knowledge_ingest import ingest_document

    dest_pdf.write_bytes(content)
    with tempfile.TemporaryDirectory() as tmp:
        core = build_core(Path(tmp), seed_knowledge=False)
        try:
            principal = principal_for_core(core)
            imported = ingest_document(
                core.knowledge,
                filename="catalog.pdf",
                content=content,
                tenant_id=principal.tenant_id,
                intent="product_inquiry",
                storage_dir=Path(tmp) / "uploads",
            )
            pages = {}
            for item in imported:
                row = core.knowledge.get_document(item.id, tenant_id=principal.tenant_id)
                pages.setdefault(item.page, []).append(row["answer"] if row else "")
            joined = {str(page): "\n".join(chunks) for page, chunks in pages.items()}
            stats = {page: _char_stats(text) for page, text in joined.items()}
            return {
                "imported_count": len(imported),
                "pages": sorted({item.page for item in imported}),
                "tables_by_page": {str(item.page): item.tables for item in imported},
                "extracted_text": joined,
                "stats": stats,
                "parser_path": "knowledge_ingest.ingest_document",
            }
        finally:
            core.close()


def phrases_present(text: str, phrases: list[str]) -> dict:
    compact = "".join(text.split())
    return {phrase: "".join(phrase.split()) in compact for phrase in phrases}


def main() -> int:
    here = Path(__file__).resolve().parent
    pdf_path = here / "fixture-catalog.pdf"
    extracted_path = here / "fixture-catalog.extracted.txt"
    content = _pdf_bytes()
    pdfplumber_pages = extract_pdfplumber(content)
    pypdf_pages = extract_pypdf(content)
    ingest = ingest_and_read(content, pdf_path)
    independent_text = "\n".join(page["text"] for page in pdfplumber_pages)
    ingest_text = "\n".join(ingest["extracted_text"].values())
    extracted_path.write_text(
        "=== independent pdfplumber ===\n"
        + independent_text
        + "\n\n=== ingest_document ===\n"
        + ingest_text
        + "\n",
        encoding="utf-8",
    )
    page1 = ingest["extracted_text"].get("1", "")
    page2 = ingest["extracted_text"].get("2", "")
    fixture_valid_chinese = (
        pdfplumber_pages[0]["has_real_chinese"]
        and pdfplumber_pages[1]["has_real_chinese"]
        and not any(page["looks_like_nnnn_corruption"] for page in pdfplumber_pages)
    )
    out = {
        "docling": probe_docling(),
        "pdf_path": str(pdf_path),
        "extracted_text_path": str(extracted_path),
        "pdf_bytes": len(content),
        "pdf_magic": content[:8].hex(),
        "independent_pdfplumber": pdfplumber_pages,
        "independent_pypdf": pypdf_pages,
        "ingest": ingest,
        "truth_check": {
            "page1_phrases_in_ingest": phrases_present(page1, TRUTH["page1_phrases"]),
            "page2_phrases_in_ingest": phrases_present(page2, TRUTH["page2_phrases"]),
            "independent_pdfplumber_has_cjk": all(p["has_real_chinese"] for p in pdfplumber_pages),
            "ingest_has_cjk": all(stats["has_real_chinese"] for stats in ingest["stats"].values()),
            "nnnn_in_independent": any(p["looks_like_nnnn_corruption"] for p in pdfplumber_pages),
            "nnnn_in_ingest": any(stats["looks_like_nnnn_corruption"] for stats in ingest["stats"].values()),
            "fixture_valid_chinese": fixture_valid_chinese,
            "nfkc_independent_sample": unicodedata.normalize("NFKC", independent_text)[:240],
            "nfkc_ingest_sample": unicodedata.normalize("NFKC", ingest_text)[:240],
        },
    }
    dest = here / "probe_docling_chinese_pdf.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "docling": out["docling"],
        "fixture_valid_chinese": fixture_valid_chinese,
        "page1_phrases_in_ingest": out["truth_check"]["page1_phrases_in_ingest"],
        "page2_phrases_in_ingest": out["truth_check"]["page2_phrases_in_ingest"],
        "nnnn_in_independent": out["truth_check"]["nnnn_in_independent"],
        "nnnn_in_ingest": out["truth_check"]["nnnn_in_ingest"],
        "ingest_has_cjk": out["truth_check"]["ingest_has_cjk"],
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
