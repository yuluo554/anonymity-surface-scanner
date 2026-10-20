# HANDOFF-M3 · 第 3 棒启动包（组合搜索 / 最小崩塌集）

> **用法**：新对话第一件事 = 跑 `py -3.12 tools/check_sprint_layout.py`（闸门在 `AGENTS.md`）。
> 本文件由 M2 棒收尾时写，是 M3 的**唯一启动上下文**；`plan/` 里的计划文件是背景，本文件是现状。
> 交付里程碑：**M3 = 组合攻击面搜索**（`anonymity-scanner search`：反单调剪枝、最小崩塌集、完整性三态）。

## 一、当前进度与证据

| 项 | 状态 | 证据（可复跑） |
| --- | --- | --- |
| M0：装订 + 计划套件 + 可运行骨架 | ✅ | `py -3.12 tools/check_sprint_layout.py` → 全绿；`verify_layout_gate.py` → 10/10 变红 |
| M1：夹具生成器 + 独立真值 + Adult 基线 | ✅ | `py -3.12 tools/gen_fixtures.py --check` → 四组逐字节一致；`pytest tests/test_fixtures.py` → 49 项绿 |
| **M2：等价类引擎（k/l/t + 三策略 + 违例三件套）** | ✅ | `scan` 产出 `scan.json`；`pytest tests/test_m2_classes.py` → 25 项绿；与 `small/truth.json` 的 `by_policy` 三块逐项一致 |
| 计算实现模块 M1（`schema` 子命令） | ⬜ | `anonymity-scanner schema ...` → `MODULE_NOT_READY` + 退出码 `2`（**设计如此**） |
| 计算实现模块 M3–M5 | ⬜ | 同上，三条子命令均 `MODULE_NOT_READY` + `2` |
| 全量测试 | ✅ | `py -3.12 -m pytest` → **159 passed**；`py -3.8 -m pytest` → **159 passed**；干净树（无 `*.csv`）→ **136 passed + 23 skipped** |

**本轮实测命令与输出摘要**（2026-10-20，本机）：

```text
py -3.12 -m pytest            → 159 passed in 4.82s
py -3.8  -m pytest            → 159 passed in 6.03s
# 干净树（tar 排除 *.csv）
py -3.12 -m pytest            → 136 passed, 23 skipped
py -3.12 tools/check_sprint_layout.py → 全绿（LAYOUT.RELEASE 为 SKIP）
```

`scan` 冒烟（small，drop，k=5）：

```text
qi columns  : age, zip, dob, sex     # 声明书写顺序（来自 declaration_order）
sensitive   : disease
scan        : k=1 l=1 t=0.678571 classes=51 violations=51 → violation (exit 1)
```

## 二、当前事实 · 状态不变量（下一棒动手前必须知道）

1. **M2 的 API 就是 M3 的分组函数**（K1，禁止重写）：`m2_classes.group_rows(table, columns, policy)`
   → `(classes, undecided, values_by_key)`；`m2_classes.k_of(classes)`。M3 只许 import 这两个（以及
   `m2_classes.MISSING_CLASS_KEY` 若需要），不得再写一份分组 / 缺失判定。`summarize()` 是 M2 的对外入口，
   但它把 QI 固定成整组；M3 要按子集反复调用 `group_rows`。
2. **空集已经可用**：`group_rows(table, [], policy)` 返回**一个类**（键 = `""`），包含全部行；`k_of` = 行数。
   `data/README.md` §4.5 的 `k(∅) = 参与分组的行数` 由此成立（small 实测 60）。
3. **真值里的 `minimal_collapse_sets` / `search` / `search_scenarios` 是 M3 的唯一对照**。
   `tools/fixture_oracle.py::search_collapse_sets` 是独立朴素实现，**M3 不得 import 它**（K10）——
   也不许 import `tools/gen_fixtures.py`。
4. **单调性判据（K5）**：`monotone = (policy != "drop") or (候选池里没有任何列含缺失)`。
   `drop` + 池内含缺失 → `monotonicity-not-applicable`，**不剪枝**，结论不得写"最小"。
   small 的池（age/zip/dob/sex）含缺失 → 适用；prune/budget 无缺失 → 适用；`drop` 无缺失 → 适用。
5. **枚举顺序**：按子集大小升序；同大小按列名码位序（`sorted`）。边界集按枚举顺序全部列出，不只第一个。
6. **预算按 `evaluated_subsets` 计数**（实际算过 k 的不同子集数，含空集）；到上限即停，
   `completeness = "budget-truncated"`，`non_exhaustive = true`。`pruned_subsets` 单独计数。
7. **边界集定义**：S 安全（`k(S) >= threshold`，`k` 为 `None` 视为不安全）且对池中每个 `c ∉ S`，
   `k(S ∪ {c})` 为 `undefined` 或 `< threshold`。`monotone=false` 时若某扩展**没算过**，不得断言它不安全
   （oracle 的做法：跳过该 S，不列为边界集）——这一条直接决定 small 的期望结果，照抄口径、不要"优化"。
8. **空集与无解**：空集本身不安全（行数 < threshold）→ `verdict="no_solution"` + `minimal_collapse_sets: []`；
   没有任何单列安全 → `minimal_collapse_sets: [[]]` + `empty_set_witness: true`（语义 = 一个 QI 列都不能加，
   `plan/00` 勘误 E2）。每组的 `search_scenarios` 都已把这两种边界写成真值。
9. **`collapse_sets_status`**：`completeness != "exhausted"` 时必须写 `"non-exhaustive"`，
   报告/JSON 文案不得称"最小崩塌集"（`plan/06` A2）。
10. **候选池 = 声明为 `qi` 的列**。当前 CLI 没有 `--include-candidates`；`plan/03` 提到的"高分未声明列"
    不在 M3 的最小范围（要加须先改 CLI 契约 + 测试）。`_prepare` 已拒绝"未声明任何 qi 列"。
11. **`_cmd_search` 现有校验顺序不要动**：缺策略 / 缺 k / 非正 k / 缺 budget / 非正 budget 都在
    `raise ModuleNotReady` 之前。只替换最后那句 raise。
12. **`main()` 已支持真实结论**：handler 的返回值经 `map_outcome()` 映射（`None` → pass；
    M2 的 `_cmd_scan` 返回 `"pass"/"violation"/"undecidable"`）。M3 照此返回 `verdict` 字符串。
13. **产物走 `canonical.write_json`**（K3）：`<out-dir>/search.json`。双跑必须逐字节一致。
    路径用 `canonical.relativize(table.source, root)`，不得写绝对路径（K7）。
14. **`--require-exhaustive` + `budget-truncated` → `CriteriaError`（退出码 2）**；这是 M3 新增的失败路径。
15. **`budget` 夹具没有 sensitive 列**：`l`/`t` 为 `null` 是期望值，不是 bug；M3 不应因缺 sensitive 报错
    （只有 `scan --l/--t` 才要求 sensitive）。
16. **真值里的 `declaration_order` 是有序数组**：`canonical.dumps(sort_keys=True)` 会打乱
    `declaration.columns` 的对象键序。写声明/复算键序时必须读 `declaration_order`（M2 测试已踩过）。
17. **四处状态副本**（`plan/00` 里程碑表 / `plan/05` 状态表 / `README` 状态行 / `plan/06` 覆盖对标表）
    M3 收尾时**四处一起改**；漏一处布局门即红。
18. **`plan/06` 缺口表**：关闭 G1 的 M3 部分时**只描述、不点名 `.md` 文件名**，缺口列不写 `M3`。

## 三、下一棒待办（M3）

- [ ] 写 `src/anonymity_scanner/m3_search.py`：纯函数（不写盘、不读时钟/随机、不 import `cli`）。
      API 建议：`search(table, pool, sensitive, policy, threshold, budget=None, require_exhaustive=False)`
      → 含 `minimal_collapse_sets / empty_set_witness / empty_set_k / completeness / non_exhaustive /
      evaluated_subsets / pruned_subsets / subset_space / candidate_count / verdict`。
- [ ] `_cmd_search` 接上它：产物 `search.json` 走 `canonical.write_json`；返回真实 verdict；
      `--require-exhaustive` + 截断 → `CriteriaError`。
- [ ] 四组夹具逐项对 `truth["search"]` 与 `truth["minimal_collapse_sets"]` 断言
      （`evaluated_subsets` / `pruned_subsets` / `empty_set_k` / `completeness` / `non_exhaustive`）。
- [ ] `search_scenarios` 三组（`default` / `empty_set_witness` / `no_solution`）逐组断言；
      这覆盖"空集是边界集"与"无解"两条最危险的语义。
- [ ] 预算截断：把 `--budget` 设成小于 `evaluated_subsets` 的值，必须 `budget-truncated` 且不冒充穷尽；
      加 `--require-exhaustive` → 退出码 `2`。
- [ ] `drop` + 池含缺失（small）→ `monotonicity-not-applicable` 且**不剪枝**（`pruned_subsets == 0`）。
- [ ] 双跑 `search.json` 逐字节一致；序列化走 `canonical`；无绝对路径/时间戳。
- [ ] 更新 `tests/test_contract.py::test_search_with_valid_arguments_is_module_not_ready`
      （改成断言真实结果；保留缺 budget / 非正 budget / 缺策略的契约断言）。
- [ ] 收尾：四处状态副本改 ✅ → 写 `plan/HANDOFF-M4.md`（七节）→ commit。

## 四、既定口径清单（K 编号，动了会打挂测试）

| K | 口径 | 唯一位置 | 改动后果 |
| --- | --- | --- | --- |
| K1 | k/l/t 与 QI 打分公式只有一个实现 | `data/README.md` §4.2–4.3；`m2_classes`（已落地）/ `m1_candidates`（未落地） | 全部数值断言与四组真值同时失效 |
| K2 | 退出码映射单点 | `exit_codes.map_outcome` | `tests/test_contract.py` 整组红 |
| K3 | 序列化冻结参数 | `canonical.dumps` | `tests/test_determinism.py` 逐字节断言红 |
| K4 | 缺失值集合 | `tableio.missing_set` | 三策略用例与真值全部偏一格 |
| K5 | 完整性三态闭合互斥 | `data/README.md` §4.5；`m3_search.completeness`（M3 落地） | M3 的"不得冒充穷尽"断言失效 |
| K6 | 行号语义（1 起、不含表头、空行不占号） | `tableio.read_table` | 真值里的 `row_numbers` 全错位 |
| K7 | 报告无时间戳/主机名/绝对路径 | `canonical.relativize` + 序列化单点 | `test_output_has_no_timestamp_hostname_or_abs_path` 红 |
| K8 | 计算层禁 import CLI、禁读时钟/随机 | `tests/test_m2_classes.py::test_m2_module_respects_compute_layer_discipline`（M2 已加同型守门） | 确定性承诺失效 |
| K9 | 版本号单一来源 | `__init__.__version__` | `tools/scaffold_selftest.py` 的 `VERSION.SINGLE_SOURCE` 红 |
| K10 | 真值由生成器独立 oracle 写出，不 import 生产模块 | `plan/04 §二`；`tools/fixture_oracle.py` | 真值变成"自证"，基准永久全绿 |

## 五、本机环境坑（只写实测过的）

- **`python` 是商店占位符**：本机一律 `py -3.12 ...` / `py -3.8 ...`。两条通道都能跑全量测试。
- **子进程测试不要整份替换 `env`**：Windows 上用 `dict(os.environ)` 起底，只覆盖编码与 `PYTHONPATH`
  （见 `tests/test_fixtures.py::_clean_env`）。
- **跨盘符 `relpath` 抛 ValueError**：一律走 `canonical.relativize`。
- **`.gitignore` 排除 `*.csv` / `*.data` / `*.names`**：`data/fixtures/*/table.csv` 不入库。
  依赖表格的测试必须 `pytest.skip` 而不是 fail；干净树里 **136 passed + 23 skipped** 是预期。
  本轮新增的 skip 集中在：三策略 CLI 对照（3）、四组 × 三策略（12）、空集语义（1）、双跑（1）、
  序列化（1）；其余是 M1 的 4 项与"控制台脚本未安装"（1）。
- **`canonical.dumps(sort_keys=True)` 会打乱声明键序**：复算等价类键时读真值的 `declaration_order`。
- **`data/README.md` 的 `t` 口径**：全表分布 = 参与分组的行（`drop` 下不含未裁决行）。
  M2 已用 `Fraction` 精确算再 `round6`；M3 若复用 M2 的 `t_detail` 也要保持同口径。
- **`.gitignore` 里的 `.pytest_cache` / `__pycache__`**：干净树复制时排除它们，否则会带上上一轮的缓存。
- **`tests/conftest.py` 已把 `src/` 注入 `sys.path`**：未安装也能跑 pytest，别删。

## 六、DoD 逐项 checklist（M3）

- [ ] `anonymity-scanner search` 能跑出 `search.json`，与四组 `truth["search"]` 逐项一致
- [ ] `minimal_collapse_sets` 逐组命中；`empty_set_witness` 与 `no_solution` 两种边界显式表达
- [ ] `budget-truncated` 有专门用例；`--require-exhaustive` 下退出码 `2`
- [ ] `drop` + 池含缺失 → `monotonicity-not-applicable` 且不剪枝（`pruned_subsets == 0`）
- [ ] 剪枝成立时 `pruned_subsets > 0`（`prune` 夹具）且 `completeness == "exhausted"`
- [ ] 分层曲线（按 `|S|` 的 `min_k` / `exposed_rows`）有输出且可复算（`plan/03 §M3` 步骤 8）
- [ ] 双跑 `search.json` 逐字节一致
- [ ] `tests/test_contract.py` 里 search 的"未实现 → 2"断言按实际情况更新（保留契约面断言）
- [ ] 四处状态副本改 ✅ 后布局门绿
- [ ] 双通道（3.8 / 3.12）全量 pytest 绿
- [ ] `plan/HANDOFF-M4.md` 落盘（七节齐）

## 七、关键命令速查

```bash
# 门（顺序固定：先布局门，再变异验证）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/verify_layout_gate.py
py -3.12 tools/scaffold_selftest.py

# 测试（双通道）
py -3.12 -m pytest
py -3.8  -m pytest
py -3.12 -m pytest tests/test_m2_classes.py -q     # M2 的 25 项验收

# 夹具（表不入库；真值与 manifest 入库）
py -3.12 tools/gen_fixtures.py                   # 全集生成
py -3.12 tools/gen_fixtures.py --check           # 逐字节比对（生成器改动未重生成 → 红）

# scan 冒烟（M2 已落地）
anonymity-scanner scan --table data/fixtures/small/table.csv \
    --decl <decl.json> --missing-policy drop --k 5 --out-dir out/

# search 契约冒烟（当前应 rc=2 且报 MODULE_NOT_READY）
anonymity-scanner search --table data/fixtures/small/table.csv \
    --decl <decl.json> --missing-policy drop --k 5 --budget 256 --out-dir out/

# 收尾顺序（硬约束）
# DoD 验证 → plan/00·05·06 + README 四处状态回写 → 写 HANDOFF-M4 → commit
```
