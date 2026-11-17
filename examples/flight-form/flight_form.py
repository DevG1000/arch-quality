"""机票预订表单: 自然语言 -> 表单 Schema -> 一次提交校验。

三层职责:
  1. parse_intent   NLU 槽位解析(规则式, 可替换为 LLM)
  2. build_schema   生成表单 Schema(预填/默认/显隐规则都进 schema)
  3. validate_payload  服务端校验(镜像客户端规则, 并以城市库/日期兜底)

用法:
  python flight_form.py "我想订一张去北京的机票"
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta

FORM_ID = "flight_booking"

# ---- 共享领域数据(服务端权威) ----------------------------------------
CITY_DB = {
    "北京", "上海", "广州", "深圳", "成都", "杭州", "南京", "武汉", "西安",
    "重庆", "长沙", "天津", "青岛", "厦门", "昆明", "三亚", "哈尔滨", "乌鲁木齐",
    "郑州", "济南", "福州", "沈阳", "大连",
}
CITY_ALIASES = {
    "首都": "北京", "帝都": "北京", "魔都": "上海", "沪": "上海", "穗": "广州",
    "蓉": "成都", "杭": "杭州", "宁": "南京", "汉": "武汉", "镐": "西安",
    "津": "天津", "鹏城": "深圳", "春城": "昆明",
}
CITY_CJK = r"[\u4e00-\u9fff]{2,5}?"

# ---- 规则式 NLU(关键词 + 少量词法) -----------------------------------
DEST_RE = re.compile(r"(?:去|到|飞往|前往|飞抵|飞)" + CITY_CJK + r"(?=的|机票|吧|了|，|。|从|$)")
ORIGIN_RE = re.compile(r"(?:从|自)" + CITY_CJK + r"(?=出发|走|去|到|飞|坐|乘|飞往|的|，|。|$)")
DATE_RE = re.compile(r"(今天|明天|后天|(\d{1,2})月(\d{1,2})日?)")
TYPE_RE = re.compile(r"往返|来回|单程")


def _normalize_city(raw: str) -> str | None:
    """'北京市' -> '北京'; 别名映射; 不在库内返回 None 并留待人工确认。"""
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.endswith("市"):
        raw = raw[:-1]
    if raw in CITY_ALIASES:
        raw = CITY_ALIASES[raw]
    return raw if raw in CITY_DB else None


def _resolve_date(tok: str) -> str | None:
    today = date.today()
    if tok == "今天":
        return today.isoformat()
    if tok == "明天":
        return (today + timedelta(days=1)).isoformat()
    if tok == "后天":
        return (today + timedelta(days=2)).isoformat()
    m = re.fullmatch(r"(\d{1,2})月(\d{1,2})日?", tok)
    if m:
        mon, day = int(m.group(1)), int(m.group(2))
        try:
            d = date(today.year, mon, day)
        except ValueError:
            return None
        if d < today:  # 已过则顺延到下一年
            d = date(today.year + 1, mon, day)
        return d.isoformat()
    return None


def parse_intent(utterance: str) -> dict:
    """返回 {intent, slots, missing, warnings}。槽位无法映射/不识别时进 warnings。"""
    u = (utterance or "").strip()
    slots = {"origin": None, "destination": None, "depart_date": None, "travel_type": None}
    warnings = []

    m = DEST_RE.search(u)
    if m:
        city = _normalize_city(m.group(0)[1:])
        if city:
            slots["destination"] = city
        else:
            warnings.append(f"未在航点库中找到目的地 {m.group(0)[1:]}，请用户在表单中确认")

    m = ORIGIN_RE.search(u)
    if m:
        city = _normalize_city(m.group(0)[1:])
        if city:
            slots["origin"] = city
        else:
            warnings.append(f"未在航点库中找到出发地 {m.group(0)[1:]}，请用户在表单中确认")

    m = DATE_RE.search(u)
    if m:
        resolved = _resolve_date(m.group(1))
        if resolved:
            slots["depart_date"] = resolved

    if TYPE_RE.search(u):
        slots["travel_type"] = "round_trip" if ("往返" in u or "来回" in u) else "single"

    missing = [k for k, v in slots.items() if v is None]
    return {"intent": "book_flight", "slots": slots, "missing": missing, "warnings": warnings}


# ---- Schema 生成(渲染层与校验层的唯一事实源) --------------------------
def build_schema(utterance: str) -> dict:
    parsed = parse_intent(utterance)
    s = parsed["slots"]
    today = date.today().isoformat()

    fields = [
        {
            "name": "origin", "label": "出发城市", "type": "text", "required": True,
            "placeholder": "如: 上海",
            "prefill_value": s["origin"],
            "validate": [{"rule": "required"}, {"rule": "in_city_db"}],
        },
        {
            "name": "destination", "label": "到达城市", "type": "text", "required": True,
            "placeholder": "如: 北京",
            "prefill_value": s["destination"],
            "validate": [{"rule": "required"}, {"rule": "in_city_db"}],
        },
        {
            "name": "depart_date", "label": "出发日期", "type": "date", "required": True,
            "prefill_value": s["depart_date"],
            "validate": [{"rule": "required"}, {"rule": "date_min", "value": today}],
        },
        {
            "name": "travel_type", "label": "旅行类型", "type": "radio", "required": True,
            "options": [
                {"value": "single", "label": "单程"},
                {"value": "round_trip", "label": "往返"},
            ],
            "default": s["travel_type"] or "single",
            "validate": [{"rule": "required"}],
        },
        {
            "name": "return_date", "label": "返程日期", "type": "date", "required": False,
            "visible_when": {"field": "travel_type", "equals": "round_trip"},
            "validate": [{"rule": "date_after", "value": "depart_date"}],
        },
    ]

    return {
        "form_id": FORM_ID,
        "title": "机票预订",
        "intent": parsed["intent"],
        "submit_once": True,
        "fields": fields,
        "meta": {
            "utterance": utterance,
            "slots": parsed["slots"],
            "missing": parsed["missing"],
            "warnings": parsed["warnings"],
        },
    }


# ---- 服务端校验(镜像客户端规则 + 领域约束) ----------------------------
def validate_payload(payload: dict) -> dict:
    errors = []
    p = payload or {}

    origin = (p.get("origin") or "").strip()
    dest = (p.get("destination") or "").strip()
    depart = p.get("depart_date") or ""
    travel_type = p.get("travel_type") or ""
    ret = p.get("return_date") or ""

    if not origin:
        errors.append({"field": "origin", "message": "出发城市不能为空"})
    elif origin not in CITY_DB:
        errors.append({"field": "origin", "message": f"航点库中不存在 {origin}"})
    if not dest:
        errors.append({"field": "destination", "message": "到达城市不能为空"})
    elif dest not in CITY_DB:
        errors.append({"field": "destination", "message": f"航点库中不存在 {dest}"})
    if origin and dest and origin == dest:
        errors.append({"field": "destination", "message": "出发与到达城市不能相同"})

    if not depart:
        errors.append({"field": "depart_date", "message": "出发日期必选"})
    elif depart < date.today().isoformat():
        errors.append({"field": "depart_date", "message": "出发日期不能早于今天"})

    if travel_type not in ("single", "round_trip"):
        errors.append({"field": "travel_type", "message": "旅行类型不合法"})
    elif travel_type == "round_trip":
        if not ret:
            errors.append({"field": "return_date", "message": "往返行程需要填写返程日期"})
        elif depart and ret <= depart:
            errors.append({"field": "return_date", "message": "返程日期必须晚于出发日期"})
    else:
        if ret:
            errors.append({"field": "return_date", "message": "单程无需返程日期，已忽略"})

    return {"valid": not errors, "errors": errors, "normalized": p}


def main() -> None:
    utterance = sys.argv[1] if len(sys.argv) > 1 else "我想订一张去北京的机票"
    schema = build_schema(utterance)
    print(json.dumps(schema, ensure_ascii=False, indent=2))
    print("\n# 一次提交校验示例(不含出行信息时的空提交)")
    print(json.dumps(validate_payload({}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
