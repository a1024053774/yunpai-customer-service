"""示例店模拟数据：晴川小家电（虚构目录 + 话术，仅供本机演示）。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..customer_service import CustomerServiceCore
from ..database import utc_now
from ..text_utils import checksum, hash_embedding, search_text, vector_to_blob


DEMO_STORE_ID = "demo-qingchuan-shop"
DEMO_STORE_NAME = "晴川小家电（模拟店）"
DEMO_CONNECTOR_ID = "demo-catalog"
DEMO_CONTEXT = {"store_id": DEMO_STORE_ID, "platform": "demo"}
DEMO_SOURCE = "demo:qingchuan-catalog-v1"

_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "sku_id": "QC-AF50",
        "item_id": "item-qc-af50",
        "title": "晴川空气炸锅 QC-AF50 5L",
        "sale_price": "329.00",
        "attributes": {
            "容量": "5L",
            "功率": "1500W",
            "颜色": "米白",
            "锅体": "可拆洗不粘内锅",
            "配件": "烤架、接油盘",
            "安装": "即插即用，无需上门安装",
        },
    },
    {
        "sku_id": "QC-AF35",
        "item_id": "item-qc-af35",
        "title": "晴川空气炸锅 QC-AF35 3.5L",
        "sale_price": "259.00",
        "attributes": {
            "容量": "3.5L",
            "功率": "1300W",
            "颜色": "浅灰",
            "锅体": "可拆洗不粘内锅",
            "配件": "接油盘",
            "安装": "即插即用，无需上门安装",
        },
    },
    {
        "sku_id": "QC-HM4",
        "item_id": "item-qc-hm4",
        "title": "晴川加湿器 QC-HM4 4L",
        "sale_price": "189.00",
        "attributes": {
            "水箱": "4L",
            "雾化": "冷雾",
            "适用面积": "约20㎡",
            "滤芯": "QC-HM4-F，建议 2–3 个月更换",
        },
    },
    {
        "sku_id": "QC-GS2",
        "item_id": "item-qc-gs2",
        "title": "晴川手持挂烫机 QC-GS2",
        "sale_price": "219.00",
        "attributes": {
            "功率": "1200W",
            "蒸汽": "两档可调",
            "水箱": "200ml 可拆",
            "预热": "约 25 秒",
        },
    },
)

_KNOWLEDGE: tuple[dict[str, Any], ...] = (
    {
        "knowledge_key": "demo:qingchuan-airfryer-5l-capacity",
        "sku_id": None,
        "category": "商品",
        "intent": "product",
        "keywords": "晴川 空气炸锅 AF50 5L 容量 规格",
        "question": "晴川空气炸锅 5L 容量是多少",
        "answer": (
            "晴川空气炸锅 QC-AF50 标称容量 5L、功率 1500W，颜色米白，"
            "标配烤架和接油盘。适合 3–4 人家庭；1–2 人也可看 3.5L 的 QC-AF35。"
            "页面价格 329 元，实际支付以结算页为准。"
        ),
    },
    {
        "knowledge_key": "demo:qingchuan-airfryer-35-capacity",
        "sku_id": None,
        "category": "商品",
        "intent": "product",
        "keywords": "晴川 空气炸锅 AF35 3.5L 容量 规格",
        "question": "3.5L 空气炸锅适合几个人",
        "answer": (
            "晴川空气炸锅 QC-AF35 标称容量 3.5L、功率 1300W，更适合 1–2 人。"
            "3–4 人家庭建议 QC-AF50 5L。两款都是即插即用，无需上门安装。"
        ),
    },
    {
        "knowledge_key": "demo:qingchuan-airfryer-install",
        "sku_id": None,
        "category": "安装",
        "intent": "product",
        "keywords": "空气炸锅 安装 上门 调试",
        "question": "空气炸锅包安装吗",
        "answer": (
            "晴川空气炸锅 QC-AF50 / QC-AF35 均为即插即用小家电，商品页未包含上门安装。"
            "到货后接好电源、洗净内锅即可使用；第一次建议空载预热 3 分钟。"
        ),
    },
    {
        "knowledge_key": "demo:qingchuan-airfryer-clean",
        "sku_id": None,
        "category": "商品",
        "intent": "product",
        "keywords": "空气炸锅 清洗 保养 洗碗机",
        "question": "空气炸锅怎么清洗",
        "answer": (
            "QC-AF50 / QC-AF35 的内锅和烤架可拆下，用中性洗涤剂清洗后晾干。"
            "机身与加热管不要浸水，也不建议放进洗碗机。说明书未写的养护方式我不会额外承诺。"
        ),
    },
    {
        "knowledge_key": "demo:qingchuan-humidifier-filter",
        "sku_id": None,
        "category": "商品",
        "intent": "product",
        "keywords": "加湿器 滤芯 更换 HM4",
        "question": "加湿器滤芯怎么换",
        "answer": (
            "晴川加湿器 QC-HM4 滤芯型号是 QC-HM4-F，建议每 2–3 个月更换。"
            "水箱 4L，冷雾，适用约 20㎡。更换时先断电，取出旧滤芯，按说明书方向装入新滤芯。"
        ),
    },
    {
        "knowledge_key": "demo:qingchuan-steamer",
        "sku_id": None,
        "category": "商品",
        "intent": "product",
        "keywords": "挂烫机 蒸汽 预热 GS2",
        "question": "挂烫机预热要多久",
        "answer": (
            "晴川手持挂烫机 QC-GS2 功率 1200W，约 25 秒出蒸汽，两档可调，"
            "水箱 200ml 可拆洗。页面价格 219 元，实际支付以结算页为准。"
        ),
    },
    {
        "knowledge_key": "demo:qingchuan-warranty",
        "sku_id": None,
        "category": "商品",
        "intent": "product",
        "keywords": "保修 质保 一年 维修",
        "question": "保修多久",
        "answer": (
            "晴川小家电机身保修 12 个月，以签收次日和保修卡为准。"
            "耗材（滤芯、不粘涂层异常磨损）、进水、摔损不在保修范围，需人工凭凭证判定。"
        ),
    },
    {
        "knowledge_key": "demo:qingchuan-shipping",
        "sku_id": None,
        "category": "发货",
        "intent": "shipping",
        "keywords": "发货 时效 现货 快递",
        "question": "什么时候发货",
        "answer": (
            "模拟店现货订单一般在付款后 48 小时内发出，偏远地区以结算页承运范围为准。"
            "预售、大促或仓库复核异常时不能承诺具体发出时刻。"
        ),
    },
    {
        "knowledge_key": "demo:qingchuan-return",
        "sku_id": None,
        "category": "售后",
        "intent": "return_exchange",
        "keywords": "七天 无理由 退货 换货",
        "question": "支持七天无理由吗",
        "answer": (
            "晴川小家电支持七天无理由退货：商品、配件、包装和发票需完好，不影响二次销售。"
            "已使用、自行拆机或定制刻字不在此列。退货运费由判责结果决定，客服不能预先承诺谁承担。"
        ),
    },
    {
        "knowledge_key": "demo:qingchuan-refund-boundary",
        "sku_id": None,
        "category": "退款",
        "intent": "refund",
        "keywords": "退款 马上 立即 帮我退",
        "question": "请马上给我退款",
        "answer": (
            "退款会改变交易和资金状态，智能客服不能代为执行。"
            "请在平台订单的售后入口申请；需要协助时我会转人工，请只提供必要的订单编号。"
        ),
    },
)


def _tenant_suffix(tenant_id: str) -> str:
    """主键掺入租户指纹：同一库被不同租户重复种子时不撞固定主键。"""
    return hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:8]


def seed_demo_store(core: CustomerServiceCore, *, tenant_id: str) -> dict[str, int]:
    """幂等写入示例店目录和话术；已有相同 knowledge_key / SKU 时跳过或覆盖目录。"""
    catalog_written = _seed_catalog(core, tenant_id=tenant_id)
    knowledge_written = _seed_knowledge(core, tenant_id=tenant_id)
    return {
        "catalog_items": catalog_written,
        "knowledge_records": knowledge_written,
    }


def _seed_catalog(core: CustomerServiceCore, *, tenant_id: str) -> int:
    now = utc_now()
    written = 0
    with core.db._write_lock, core.db.connect() as conn:
        for item in _CATALOG:
            attributes = json.dumps(item["attributes"], ensure_ascii=False, sort_keys=True)
            payload_hash = hashlib.sha256(
                f"{item['title']}|{item['sale_price']}|{attributes}".encode("utf-8")
            ).hexdigest()
            row_id = f"demo-catalog-{_tenant_suffix(tenant_id)}-{item['sku_id'].lower()}"
            conn.execute(
                """
                INSERT INTO catalog_items(
                    id, tenant_id, connector_id, store_id, item_id, sku_id,
                    title, status, sale_price, currency, attributes_json,
                    source_id, source_updated_at, payload_hash, version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, 'CNY', ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(tenant_id, connector_id, store_id, sku_id)
                DO UPDATE SET
                    title=excluded.title,
                    sale_price=excluded.sale_price,
                    attributes_json=excluded.attributes_json,
                    payload_hash=excluded.payload_hash,
                    updated_at=excluded.updated_at
                """,
                (
                    row_id,
                    tenant_id,
                    DEMO_CONNECTOR_ID,
                    DEMO_STORE_ID,
                    item["item_id"],
                    item["sku_id"],
                    item["title"],
                    item["sale_price"],
                    attributes,
                    DEMO_SOURCE,
                    now,
                    payload_hash,
                    now,
                    now,
                ),
            )
            written += 1
    return written


def _seed_knowledge(core: CustomerServiceCore, *, tenant_id: str) -> int:
    written = 0
    for record in _KNOWLEDGE:
        with core.db._write_lock, core.db.connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM knowledge
                WHERE tenant_id=? AND knowledge_key=? AND status='active'
                """,
                (tenant_id, record["knowledge_key"]),
            ).fetchone()
            if existing is not None:
                _refresh_demo_knowledge(
                    conn, doc_id=str(existing["id"]), record=record, tenant_id=tenant_id,
                )
                continue
        core.knowledge.add_document(
            category=record["category"],
            intent=record["intent"],
            question=record["question"],
            answer=record["answer"],
            keywords=record["keywords"],
            risk_level="low",
            source=DEMO_SOURCE,
            version=1,
            id=f"{record['knowledge_key']}:{_tenant_suffix(tenant_id)}",
            status="active",
            approved_by="demo",
            tenant_id=tenant_id,
            knowledge_key=record["knowledge_key"],
            layer="store",
            store_id=DEMO_STORE_ID,
            sku_id=record["sku_id"],
            review_status="approved",
        )
        written += 1
    return written


def _refresh_demo_knowledge(
    conn: Any, *, doc_id: str, record: dict[str, Any], tenant_id: str,
) -> None:
    """已存在的示例话术也对齐最新文案，并清掉 sku 范围（否则检索会因未带 sku_id 被滤掉）。"""
    indexed_text = search_text(
        record["question"], record["answer"], record["keywords"],
        record["category"], record["intent"],
    )
    embedding = vector_to_blob(
        hash_embedding(f"{record['question']} {record['keywords']} {record['answer']}")
    )
    now = utc_now()
    digest = checksum(
        record["question"], record["answer"], DEMO_SOURCE, "1", tenant_id,
        "store", DEMO_STORE_ID, record["sku_id"] or "",
    )
    conn.execute(
        """
        UPDATE knowledge SET
            category=?, intent=?, question=?, answer=?, keywords=?, search_text=?,
            embedding=?, sku_id=?, checksum=?, updated_at=?
        WHERE id=?
        """,
        (
            record["category"], record["intent"], record["question"], record["answer"],
            record["keywords"], indexed_text, embedding, record["sku_id"], digest, now,
            doc_id,
        ),
    )
    conn.execute("DELETE FROM knowledge_fts WHERE doc_id=?", (doc_id,))
    conn.execute(
        "INSERT INTO knowledge_fts(doc_id, search_text) VALUES (?, ?)",
        (doc_id, indexed_text),
    )
