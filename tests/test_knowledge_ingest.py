from __future__ import annotations

from io import BytesIO
from yunpai_customer_service.knowledge_ingest import ingest_document

from customer_service_fixtures import build_core, principal_for_core


def _pdf_bytes() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    out = BytesIO()
    doc = canvas.Canvas(out)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    doc.setFont("STSong-Light", 12)
    doc.drawString(72, 760, "空气炸锅容量 5L")
    doc.drawString(72, 740, "适合 3-4 人家庭")
    doc.line(72, 700, 240, 700)
    doc.line(72, 680, 240, 680)
    doc.line(72, 660, 240, 660)
    doc.line(72, 700, 72, 660)
    doc.line(156, 700, 156, 660)
    doc.line(240, 700, 240, 660)
    doc.drawString(80, 686, "容量")
    doc.drawString(164, 686, "5L")
    doc.showPage()
    doc.setFont("STSong-Light", 12)
    doc.drawString(72, 760, "售后保修一年")
    doc.save()
    return out.getvalue()


def test_pdf_import_preserves_page_sources_and_tenant_scope(tmp_path) -> None:
    core = build_core(tmp_path, seed_knowledge=False)
    principal = principal_for_core(core)

    imported = ingest_document(
        core.knowledge,
        filename="catalog.pdf",
        content=_pdf_bytes(),
        tenant_id=principal.tenant_id,
        intent="product_inquiry",
    )

    assert len(imported) == 2
    assert {item.page for item in imported} == {1, 2}
    assert imported[0].tables == 1
    by_page = {item.page: core.knowledge.get_document(item.id, tenant_id=principal.tenant_id)["answer"] for item in imported}
    assert "空气炸锅容量" in "".join(by_page[1].split())
    assert "售后保修一年" in "".join(by_page[2].split())
    rows = core.knowledge.retrieve(
        "空气炸锅容量", top_k=3, min_score=0.01,
        intent="product_inquiry", tenant_id=principal.tenant_id,
    )
    assert rows
    assert any("page=1" in row["source"] for row in rows)
    assert all(row["tenant_id"] == principal.tenant_id for row in rows if "catalog.pdf" in row["source"])


def test_knowledge_import_endpoint_lists_imported_pdf(tmp_path) -> None:
    from fastapi.testclient import TestClient
    from yunpai_customer_service.demo.app import create_app
    from yunpai_customer_service.config import Settings
    from dataclasses import replace

    settings = replace(Settings.from_env(), data_dir=tmp_path, model_mock_mode=True, model_enabled=False,
                       kg_import_enabled=False, kg_dream_worker_enabled=False)
    app = create_app(settings)
    pdf = _pdf_bytes()
    with TestClient(app) as client:
        response = client.post(
            "/api/knowledge/import",
            files={"file": ("catalog.pdf", pdf, "application/pdf")},
            data={"intent": "product_inquiry"},
        )
        assert response.status_code == 200
        assert response.json()["count"] == 2
        listed = client.get("/api/knowledge")
        assert listed.status_code == 200
        assert any(item["question"].startswith("catalog.pdf 第") for item in listed.json()["items"])
        files = client.get("/api/knowledge/files")
        assert files.status_code == 200
        assert files.json()["items"][0]["name"].endswith("-catalog.pdf")
        assert str(tmp_path) not in files.text
        downloaded = client.get("/api/knowledge/files/" + files.json()["items"][0]["name"])
        assert downloaded.status_code == 200
        assert downloaded.content == pdf
        assert client.get("/api/knowledge/files/..%2Fagent.sqlite3").status_code == 404
        reindexed = client.post("/api/knowledge/reindex")
        assert reindexed.status_code == 200
        assert reindexed.json()["embedding_provider"] == "hash"
        assert reindexed.json()["updated"] >= 2
        before_repeat = len(listed.json()["items"])
        repeated = client.post(
            "/api/knowledge/import",
            files={"file": ("catalog.pdf", pdf, "application/pdf")},
            data={"intent": "product_inquiry"},
        )
        assert repeated.status_code == 200
        assert len(client.get("/api/knowledge").json()["items"]) == before_repeat


def test_feedback_endpoint_creates_experience_candidate(tmp_path) -> None:
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from yunpai_customer_service.config import Settings
    from yunpai_customer_service.demo.app import create_app

    settings = replace(Settings.from_env(), data_dir=tmp_path, model_mock_mode=True, model_enabled=False,
                       kg_import_enabled=False, kg_dream_worker_enabled=False)
    app = create_app(settings)
    with TestClient(app) as client:
        chat = client.post("/api/chat", json={"session_id": "feedback-1", "message": "空气炸锅容量是多少"})
        assert chat.status_code == 200
        message_id = chat.json()["message_id"]
        feedback = client.post("/api/feedback", json={
            "message_id": message_id, "rating": -1,
            "corrected_answer": "请以商品详情页的容量参数为准。",
            "evidence_source": "demo-user-feedback",
        })
        assert feedback.status_code == 200
        assert feedback.json()["status"] == "candidate_pending"
        candidates = client.get("/api/evolution/candidates")
        assert candidates.status_code == 200
        assert candidates.json()["items"][0]["status"] == "pending"


def test_chunks_keep_markdown_heading_with_following_content() -> None:
    from yunpai_customer_service.knowledge_ingest import _chunks

    chunks = _chunks("# 商品规格\n\n容量：5L。\n\n# 售后政策\n\n整机保修一年。", limit=80)

    assert chunks == ["# 商品规格\n\n容量：5L。", "# 售后政策\n\n整机保修一年。"]


def test_mixed_native_and_scanned_pdf_pages_keep_reading_order(monkeypatch):
    import yunpai_customer_service.knowledge_ingest as ingestion
    monkeypatch.setattr(ingestion, '_extract_pdf_docling', lambda _: [(1, '扫描页内容', 0), (2, '结构化第二页', 1)])
    monkeypatch.setattr(ingestion, '_extract_pdf_pdfplumber', lambda _: [(2, '原生第二页', 1)])
    result = ingestion._extract_pdf(b'parser-boundary-fixture')
    assert [page for page, _, _ in result] == [1, 2]
    assert result[0][1] == '扫描页内容'
