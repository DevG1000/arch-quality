"""flight_form 单元测试: NLU 槽位解析 / Schema 生成 / 一次提交校验。"""
import unittest
from datetime import date, timedelta

from flight_form import build_schema, parse_intent, validate_payload


class TestParseIntent(unittest.TestCase):
    def test_destination_prefilled_from_nlu(self):
        r = parse_intent("我想订一张去北京的机票")
        self.assertEqual(r["slots"]["destination"], "北京")
        self.assertIsNone(r["slots"]["origin"])
        self.assertIn("origin", r["missing"])
        self.assertEqual(r["warnings"], [])

    def test_origin_and_destination_both(self):
        r = parse_intent("从上海去北京的往返机票")
        self.assertEqual(r["slots"]["origin"], "上海")
        self.assertEqual(r["slots"]["destination"], "北京")
        self.assertEqual(r["slots"]["travel_type"], "round_trip")

    def test_single_trip_detected(self):
        r = parse_intent("帮我订一张北京到广州的单程票")
        self.assertEqual(r["slots"]["travel_type"], "single")

    def test_date_tomorrow(self):
        r = parse_intent("明天去北京")
        self.assertEqual(r["slots"]["depart_date"],
                         (date.today() + timedelta(days=1)).isoformat())

    def test_date_mm_dd(self):
        r = parse_intent("去北京，3月5日出发")
        self.assertIsNotNone(r["slots"]["depart_date"])

    def test_alias_mapping(self):
        self.assertEqual(parse_intent("从魔都去北京")["slots"]["origin"], "上海")

    def test_unknown_city_warning(self):
        r = parse_intent("去亚特兰蒂斯")
        self.assertIsNone(r["slots"]["destination"])
        self.assertTrue(any("亚特兰蒂斯" in w for w in r["warnings"]))


class TestBuildSchema(unittest.TestCase):
    def test_schema_shape_and_dependency(self):
        s = build_schema("我想订一张去北京的机票")
        self.assertEqual(s["form_id"], "flight_booking")
        self.assertTrue(s["submit_once"])
        by_name = {f["name"]: f for f in s["fields"]}
        self.assertEqual(by_name["destination"]["prefill_value"], "北京")
        self.assertIsNone(by_name["origin"]["prefill_value"])
        self.assertEqual(by_name["travel_type"]["default"], "single")
        # 返程日期依赖旅行类型
        self.assertEqual(
            by_name["return_date"]["visible_when"],
            {"field": "travel_type", "equals": "round_trip"},
        )
        # 每个字段都有可执行校验规则
        for f in s["fields"]:
            self.assertIn("validate", f)

    def test_round_trip_default_bubbles(self):
        s = build_schema("从上海去北京往返")
        by_name = {f["name"]: f for f in s["fields"]}
        self.assertEqual(by_name["travel_type"]["default"], "round_trip")


class TestValidatePayload(unittest.TestCase):
    def test_valid_single_trip(self):
        r = validate_payload({
            "origin": "上海", "destination": "北京",
            "depart_date": (date.today() + timedelta(days=3)).isoformat(),
            "travel_type": "single",
        })
        self.assertTrue(r["valid"])

    def test_round_trip_requires_return(self):
        r = validate_payload({
            "origin": "上海", "destination": "北京",
            "depart_date": (date.today() + timedelta(days=3)).isoformat(),
            "travel_type": "round_trip",
        })
        self.assertFalse(r["valid"])
        self.assertTrue(any(e["field"] == "return_date" for e in r["errors"]))

    def test_return_after_depart(self):
        d = (date.today() + timedelta(days=3)).isoformat()
        r = validate_payload({
            "origin": "上海", "destination": "北京", "depart_date": d,
            "travel_type": "round_trip", "return_date": d,
        })
        self.assertFalse(r["valid"])
        self.assertTrue(any("晚于" in e["message"] for e in r["errors"]))

    def test_unknown_city_rejected(self):
        r = validate_payload({
            "origin": "亚特兰蒂斯", "destination": "北京",
            "depart_date": (date.today() + timedelta(days=1)).isoformat(),
            "travel_type": "single",
        })
        self.assertFalse(r["valid"])

    def test_same_city_origin_dest(self):
        r = validate_payload({
            "origin": "北京", "destination": "北京",
            "depart_date": (date.today() + timedelta(days=1)).isoformat(),
            "travel_type": "single",
        })
        self.assertFalse(r["valid"])

    def test_empty_payload_reports_all_required(self):
        r = validate_payload({})
        self.assertFalse(r["valid"])
        self.assertEqual({e["field"] for e in r["errors"]},
                         {"origin", "destination", "depart_date", "travel_type"})


if __name__ == "__main__":
    unittest.main()
