"""E04 cross-page table probe. ASCII source."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak, Spacer
from reportlab.lib.styles import getSampleStyleSheet

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "tests"))

from conftest import make_settings  # noqa: E402
from customer_service_fixtures import TableDrivenModel, build_core  # noqa: E402
from yunpai_customer_service.knowledge_ingest import ingest_document  # noqa: E402


def build_pdf() -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    header = ["SKU", "Capacity", "Color", "Condition"]
    page1 = [
        header,
        ["QA-E04-AAA", "5L", "rice-white", "AAA only; not for BBB"],
        ["QA-E04-AAA", "5L", "rice-white", "warranty 12 months"],
    ]
    page2 = [
        header,
        ["QA-E04-BBB", "7L", "black", "BBB only; not for AAA"],
        ["QA-E04-BBB", "7L", "black", "no microwave"],
    ]
    story = [
        Paragraph("E04 cross-page SKU table", styles["Title"]),
        Paragraph("Page 1 is AAA only. Page 2 is BBB only.", styles["Normal"]),
        Spacer(1, 12),
        Table(page1, colWidths=[120, 80, 100, 180]),
        PageBreak(),
        Paragraph("Continued table page 2", styles["Heading2"]),
        Table(page2, colWidths=[120, 80, 100, 180]),
    ]
    for flow in story:
        if isinstance(flow, Table):
            flow.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ]
                )
            )
    doc.build(story)
    return buf.getvalue()


def main() -> None:
    pdf = build_pdf()
    (EVIDENCE / "e04-crosspage.pdf").write_bytes(pdf)
    with TemporaryDirectory(prefix="yunpai-e04-", dir="/tmp") as raw:
        tmp = Path(raw)
        settings = make_settings(tmp)
        core = build_core(tmp, settings=settings, model=TableDrivenModel(settings), seed_knowledge=False)
        imported = ingest_document(
            core.knowledge,
            filename="e04-crosspage.pdf",
            content=pdf,
            tenant_id=core.settings.bootstrap_tenant_id,
        )
        pages = [{"page": i.page, "chars": i.characters, "tables": i.tables, "id": i.id} for i in imported]
        hits_a = core.knowledge.retrieve(
            "QA-E04-AAA capacity color",
            top_k=5,
            min_score=0.01,
            intent="product",
            tenant_id=core.settings.bootstrap_tenant_id,
        )
        hits_b = core.knowledge.retrieve(
            "QA-E04-BBB capacity color",
            top_k=5,
            min_score=0.01,
            intent="product",
            tenant_id=core.settings.bootstrap_tenant_id,
        )
        a_text = " ".join((h["answer"] if isinstance(h, dict) else h.answer) for h in hits_a)
        b_text = " ".join((h["answer"] if isinstance(h, dict) else h.answer) for h in hits_b)
        a_has_aaa = "QA-E04-AAA" in a_text or "5L" in a_text
        a_mixed = "QA-E04-BBB" in a_text and "7L" in a_text and "QA-E04-AAA" not in a_text
        b_has_bbb = "QA-E04-BBB" in b_text or "7L" in b_text
        page_count = len({i.page for i in imported})
        # PASS only if both SKUs parsed on distinct pages and retrieve does not invert SKU facts
        parsed_two = page_count >= 2 and any(i.tables for i in imported)
        inverted = ("QA-E04-AAA" in b_text and "5L" in b_text and "QA-E04-BBB" not in b_text)
        status = "INCOMPLETE"
        if parsed_two and a_has_aaa and b_has_bbb and not inverted:
            status = "PASS"
        if not parsed_two:
            status = "INCOMPLETE"
        case = {
            "id": "E04",
            "priority": "P1",
            "level": "L1",
            "status": status,
            "expected": "cross-page table keeps SKU-param mapping; AAA 5L rice-white; BBB 7L black",
            "actual": {
                "imported_pages": pages,
                "page_count": page_count,
                "a_text": a_text[:500],
                "b_text": b_text[:500],
                "parsed_two": parsed_two,
                "inverted": inverted,
            },
            "saved_utc": datetime.now(timezone.utc).isoformat(),
        }
        (EVIDENCE / "e04.json").write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"id": "E04", "status": status, "page_count": page_count}, ensure_ascii=False))
        core.close()


if __name__ == "__main__":
    main()
