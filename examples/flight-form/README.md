# 机票预订表单 Demo — 自然语言 → Schema → 一次提交

针对「用户输入『我想订一张去北京的机票』→ Agent 生成表单 → 用户一次提交」场景的可运行示例。

## 关键设计决策

1. **槽位映射正确性**：NLU 解析出的 `destination=北京` 必须落到「到达城市」字段；
   原始需求表单只有"出发城市"会填反，故本示例补充了「到达城市」字段。
2. **Schema 是唯一事实源**：预填值、默认值、显隐规则（`visible_when`）、校验规则（`validate`）
   全部声明在 JSON Schema 中，渲染层与校验层都消费同一份数据。
3. **依赖-显隐-校验职责分离**：显隐只负责"往返才显示返程日期"，校验只负责字段规则。
4. **一次提交**：不做多轮追问，缺的字段留空由 `required` 兜底；隐藏字段不参与提交。

## 文件

| 文件 | 职责 |
|---|---|
| `flight_form.py` | NLU 槽位解析 + Schema 生成 + 服务端校验（`validate_payload`） |
| `demo.html` | 自包含渲染 Demo：显隐联动、客户端校验、一次提交（双击即可打开） |
| `test_flight_form.py` | 单测（unittest，可用 pytest 跑） |

## 用法

```powershell
# 1. 生成 Schema（打印到终端）
python examples\flight-form\flight_form.py "我想订一张去北京的机票"

# 2. 打开渲染 Demo（浏览器里可直接填表、切"往返"看返程日期显隐、提交看校验）
start examples\flight-form\demo.html

# 3. 跑单测
python -m pytest examples\flight-form\test_flight_form.py -q
```

## 示例输出（NLU 解析）

输入 `我想订一张去北京的机票`：

```json
{
  "intent": "book_flight",
  "slots": { "destination": "北京", "origin": null, "depart_date": null, "travel_type": null },
  "missing": ["origin", "depart_date", "travel_type"]
}
```

`去北京 → destination=北京` 被预填进「到达城市」；出发城市、日期、旅行类型缺省，用户在表单中一次补齐。

## 扩展点

- NLU 目前是规则式（`去/到/飞往` + 城市库 + 别名表），可替换为 LLM 输出，但**输出契约不变**：
  只认 `{intent, slots, missing, warnings}`，无法映射的槽位一律进 `warnings` 走人工确认，绝不盲目预填。
- 校验规则是数据驱动的，新增规则只需在 `validate` 列表里加一项（客户端 JS 与
  服务端 `validate_payload` 各实现一次，建议以 schema 为共同基线做一致性测试）。
