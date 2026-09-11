from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .text_utils import normalize_text, redact_sensitive


PROMPT_INJECTION_PATTERNS = (
    r"忽略.{0,8}(之前|以上|系统).{0,8}(指令|规则)",
    r"(system prompt|系统提示词|开发者消息|隐藏指令)",
    r"(越权|绕过).{0,8}(限制|权限|审核|平台)",
)
PROMPT_DISCLOSURE_ACTION_PATTERN = re.compile(
    r"(输出|打印|显示|展示|复述|重复|回显|泄露|贴出|逐字|原样|一字不差|"
    r"print|show|reveal|repeat|recite|display|dump|quote|verbatim|word\s+for\s+word)",
    re.IGNORECASE,
)
PROMPT_DISCLOSURE_TARGET_PATTERN = re.compile(
    r"((?:system|系统).{0,6}(?:prompt|提示|消息|指令|规则|设定)|"
    r"内部.{0,6}(提示|消息|指令|规则|设定)|"
    r"开发者.{0,6}(消息|指令|规则|模式)|隐藏.{0,6}(消息|指令|规则|设定)|"
    r"角色.{0,6}(设定|规则|文字)|设定.{0,6}角色|"
    r"developer\s+(message|instruction|mode)|"
    r"hidden\s+(prompt|policy|instruction|rule)|internal\s+(prompt|policy|instruction|rule))",
    re.IGNORECASE,
)

HIGH_RISK_ACTION_PATTERNS = (
    r"(帮我|给我|立即|马上|现在).{0,6}(退款|退钱|赔付|赔偿|补偿)",
    r"(申请|执行|操作).{0,5}(退款|退货|换货|赔付)",
    r"(改|修改|换).{0,5}(价格|价钱|地址|手机号|收货人|发票抬头)",
    r"(价格|价钱|地址|手机号|收货人|发票抬头).{0,8}(改|修改|换)",
    r"(取消|关闭).{0,4}订单",
    r"(补发|重新发|拦截快递|召回包裹)",
)

UNAUTHORIZED_DATA_PATTERNS = (
    r"(别家|竞品|其他店铺).{0,8}(真实销量|库存|订单|买家)",
    r"(其他|别的).{0,5}(买家|客户).{0,5}(电话|地址|数据|信息)",
)

FORBIDDEN_OUTPUT_PATTERNS = (
    r"(已经|已为您|现已).{0,8}(退款|退钱|改价|改地址|取消订单|补发|赔付|开票)",
    r"(保证|承诺|一定|百分之百).{0,12}(到货|发货|有效|成功|退款)",
    r"(请提供|请补充|请填写|请输入|发送).{0,12}(密码|验证码|完整身份证|银行卡密码)",
    r"(加我微信|转到私人账户|站外支付)",
)

# Same numeral with a different unit (5L vs 5 years) is not a supported claim.
_NUMBER_UNIT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*-?\s*(years?|months?|days?|hours?|liters?|watts?|"
    r"L|W|kg|ml|mm|cm|"
    r"\u5e74|\u4e2a\u6708|\u6708|\u5929|\u5c0f\u65f6|\u5143|\u6beb\u5347)",
    re.IGNORECASE,
)
_UNIT_CANON = {
    "year": "year",
    "years": "year",
    "month": "month",
    "months": "month",
    "day": "day",
    "days": "day",
    "hour": "hour",
    "hours": "hour",
    "liter": "L",
    "liters": "L",
    "l": "L",
    "watt": "W",
    "watts": "W",
    "w": "W",
    "kg": "kg",
    "ml": "ml",
    "mm": "mm",
    "cm": "cm",
    "\u5e74": "year",
    "\u4e2a\u6708": "month",
    "\u6708": "month",
    "\u5929": "day",
    "\u5c0f\u65f6": "hour",
    "\u5143": "CNY",
    "\u6beb\u5347": "ml",
}

# Internal identifiers a shopper cannot be expected to know. The agent must resolve
# them from the wording the customer already used instead of asking for them.
INTERNAL_IDENTIFIER_FIELDS = {
    "sku",
    "sku_id",
    "skuid",
    "sku_code",
    "item_id",
    "itemid",
    "num_iid",
    "product_id",
    "productid",
    "product_code",
    "spu",
    "spu_id",
    "spuid",
    "goods_id",
    "catalog_id",
    "catalog_item_id",
}

INTERNAL_IDENTIFIER_LABEL = "商品名称或商品链接"

INTERNAL_IDENTIFIER_REQUEST_PATTERNS = (
    r"sku",
    r"(item|product|spu|goods)[\s_-]*id",
    r"(商品|宝贝|货品)\s*(id|编号|编码|货号|代码)",
)

ALLOWED_CONTEXT_FIELDS = {
    "authorized",
    "platform",
    "store_id",
    "shop_id",
    "product_name",
    "sku_id",
    "sku",
    "order_id",
    "order_status",
    "logistics_status",
    "carrier",
    "tracking_last_event",
    "shop_policy",
}


@dataclass(frozen=True, slots=True)
class PrecheckDecision:
    route: str
    reason: str


def sanitize_context(context: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in context.items():
        if key not in ALLOWED_CONTEXT_FIELDS:
            continue
        if isinstance(value, bool):
            sanitized[key] = value
        elif isinstance(value, (str, int, float)):
            normalized = normalize_text(str(value))[:500]
            sanitized[key] = redact_sensitive(normalized)[0]
    return sanitized


def precheck_request(message: str, context: dict[str, Any]) -> PrecheckDecision:
    """Enforce trust boundaries without deciding normal business intent."""

    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, message, re.IGNORECASE):
            return PrecheckDecision("refuse", "prompt_injection_detected")
    if PROMPT_DISCLOSURE_ACTION_PATTERN.search(
        message
    ) and PROMPT_DISCLOSURE_TARGET_PATTERN.search(message):
        return PrecheckDecision("refuse", "prompt_injection_detected")
    for pattern in UNAUTHORIZED_DATA_PATTERNS:
        if re.search(pattern, message, re.IGNORECASE):
            return PrecheckDecision("refuse", "unauthorized_data_request")
    return PrecheckDecision("deliberate", "llm_deliberation_allowed")


def is_business_action_request(message: str) -> bool:
    """Detect actions that require verified execution or a human handoff."""

    return any(re.search(pattern, message) for pattern in HIGH_RISK_ACTION_PATTERNS)


def asks_for_internal_identifier(text: str) -> bool:
    """Detect a reply that demands SKU/item ids a shopper does not have."""

    return any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in INTERNAL_IDENTIFIER_REQUEST_PATTERNS
    )


def customer_facing_missing_fields(fields: list[str]) -> list[str]:
    """Replace internal identifier field names with what a shopper can provide."""

    described: list[str] = []
    for field in fields:
        label = field.strip()
        if label.lower().replace("-", "_") in INTERNAL_IDENTIFIER_FIELDS:
            label = INTERNAL_IDENTIFIER_LABEL
        if label and label not in described:
            described.append(label)
    return described


def review_output(answer: str, evidence: str) -> tuple[bool, str]:
    if not answer.strip():
        return False, "empty_model_output"
    verified_business_result = bool(
        re.search(r'"postcondition_met"\s*:\s*true', evidence, re.IGNORECASE)
    )
    for pattern in FORBIDDEN_OUTPUT_PATTERNS:
        if re.search(pattern, answer) and not verified_business_result:
            return False, "forbidden_commitment_in_output"
    # Treat 499 and 499.00 as equal; keep percentages distinct.
    unsupported_numbers = _normalized_numbers(answer) - _normalized_numbers(evidence)
    if unsupported_numbers:
        return False, "numeric_claim_without_evidence"
    unsupported_units = _number_units(answer) - _number_units(evidence)
    if unsupported_units:
        return False, "numeric_unit_mismatch"
    return True, "output_policy_passed"


def _canon_unit(unit: str) -> str:
    return _UNIT_CANON.get(unit.lower(), unit.lower())


def _number_units(text: str) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for raw, unit in _NUMBER_UNIT_PATTERN.findall(text):
        try:
            number = format(Decimal(raw).normalize(), "f")
        except InvalidOperation:
            continue
        pairs.add((number, _canon_unit(unit)))
    return pairs


def _normalized_numbers(text: str) -> set[str]:
    # Numbered-list ordinals are formatting, not prices/counts/percentages. Remove
    # only a marker at a line or punctuation boundary, retaining factual numbers.
    text = re.sub(
        r"(?m)(^|[：:；;])\s*(?:[（(]?\d+[）)]|\d+[.、](?=\s))\s*",
        r"\1", text,
    )
    values: set[str] = set()
    for raw in re.findall(r"\d+(?:\.\d+)?%?", text):
        percent = raw.endswith("%")
        number_text = raw[:-1] if percent else raw
        try:
            number = Decimal(number_text)
        except InvalidOperation:
            continue
        values.add(("%" if percent else "") + format(number.normalize(), "f"))
    return values
