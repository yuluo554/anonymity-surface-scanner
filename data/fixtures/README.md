# data/fixtures — 合成夹具与真值

> 口径出处：数值定义见 [`data/README.md` §四](../README.md)；夹具设计与植入纪律见
> [`plan/04` §二/§三](../../plan/04-数据计划.md)。本文件只说明**这一目录怎么用**。

## 一句话

四组**程序化植入已知违例**的合成表 + 由**独立 oracle** 复算的真值。
表格本体**不入库**（`.gitignore` 排除 `*.csv`），入库的是 `truth.json` 与 `manifest.json`。

## 目录布局

```text
data/fixtures/
├── manifest.json     # 生成器 / oracle / 每份真值的 sha256 + 种子 + 参数（只有全集运行才写）
├── tiny/table.csv    12 行 × 7 列   — 手算可核
├── tiny/truth.json
├── small/table.csv   60 行 × 8 列   — 三缺失策略 + zip+dob 单例 + l=1 用例
├── small/truth.json
├── prune/table.csv   300 行 × 9 列  — 反单调剪枝
├── prune/truth.json
├── budget/table.csv  1200 行 × 10 列 — 预算截断
└── budget/truth.json
```

`table.csv` 是**生成物**：可能不在你的 clone 里（被 `.gitignore` 排除）。
需要时用下面任一条命令重建，产物与入库真值逐字节一致。

## 命令

```bash
py -3.12 tools/gen_fixtures.py              # 全集生成（表 + 真值 + manifest）
py -3.12 tools/gen_fixtures.py --check      # 重生成到临时目录，与入仓真值逐字节比对
py -3.12 tools/gen_fixtures.py --only tiny  # 只生成一组；不改写 manifest.json
```

`--check` 在**没有表格**的干净 clone 里同样成立——这是"表不入库"与"真值可复算"两条承诺的交点
（`tests/test_fixtures.py::test_generator_check_works_without_tables`）。

## truth.json 的结构

顶层键（`plan/04` §二 规定的契约面）：

| 键 | 含义 |
| --- | --- |
| `fixture` / `seed` / `rows` / `columns` | 身份与形状 |
| `planted` | 生成期**断言过**的植入项（类大小/单例数/行号清单） |
| `minimal_collapse_sets` / `empty_set_witness` | 崩塌边界集；`[[]]` 的语义是"**一个 QI 列都不能加**" |
| `collapse_sets_status` | `exhaustive` 或 `non-exhaustive`（非穷尽时不得渲染成"最小"） |
| `k_by_columns` | 若干子集的 k（键是规范化列名 JSON，如 `["age","zip"]`） |
| `violations` | 默认策略下的违例三件套：`key` + `count` + `row_numbers` |
| `missing_rows` / `unique_records` | 缺失行号 / 唯一记录行号 |
| `k_l_t` / `by_policy` | 默认策略摘要 + 三策略对照（无缺失时后两者写 `{"same_as": "drop"}`） |
| `search` / `search_scenarios` | 默认阈值下的搜索结论 + 三个边界场景（default / empty_set_witness / no_solution） |
| `meta` / `declaration` / `declaration_order` / `qi_columns` / `sensitive_columns` / `missing_cells` | 复算所需的输入侧信息 |

**真值纪律**：只存**输入与期望**。出现 `observed_*` 一律视为"真值由被测实现自证"
（`tests/test_fixtures.py::test_truth_has_no_observed_fields` 扫描断言）。

## 声明顺序（易错点）

等价类键按**声明书写顺序**拼接（`data/README.md` §4.3），顺序是语义的一部分。
但真值走 `canonical.dumps(sort_keys=True)`，`declaration.columns`（JSON 对象）的**键序会被排成字典序**。

因此真值另存 **`declaration_order`**（有序数组，元素 `{name, role[, precision]}`）：

- 要按声明顺序拼键 / 建等价类 → 读 `declaration_order`（或等价的 `qi_columns`）；
- **不要**从 `declaration.columns` 推导顺序——那是字典序。
- `tests/test_fixtures.py::test_declaration_order_is_explicit_and_matches_key_order` 钉住了这条。

## 行号语义

行号 = **数据行序号，1 起，不含表头**；完全空行不占号（`data/README.md` §4.3）。
真值里的 `row_numbers` 全部按这个语义，M2 的违例行号必须能与之逐项对上。

## 复算

真值由 `tools/fixture_oracle.py` 从**已生成的行**朴素复算写入，该模块：

- **不 import** `anonymity_scanner`（AST 守门）；
- **不被** `gen_fixtures.py` 以外的任何模块 import（方向单向）；
- **不用** `random`（生成器自带 splitmix64，跨解释器序列一致）。

`tests/test_fixtures.py::test_oracle_recomputes_recorded_truth` 会从 `table.csv` 再算一遍，
与 `truth.json` 逐项比对——真值与表脱节时这条会红。
