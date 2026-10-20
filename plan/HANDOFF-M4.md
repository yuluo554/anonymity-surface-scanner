# HANDOFF-M4 · 第 4 棒启动包（逐记录风险 / 三种攻击者口径）

> **用法**：新对话第一件事 = 跑 `py -3.12 tools/check_sprint_layout.py`（闸门在 `AGENTS.md`）。
> 本文件由 M3 棒收尾时写，是 M4 的**唯一启动上下文**；`plan/` 里的计划文件是背景，本文件是现状。
> 交付里程碑：**M4 = 逐记录风险与攻击者模型**（`anonymity-scanner risk`：三口径 + `risk.json`）。

## 一、当前进度与证据

| 项 | 状态 | 证据（可复跑） |
| --- | --- | --- |
| M0：装订 + 计划套件 + 可运行骨架 | ✅ | `py -3.12 tools/check_sprint_layout.py` → 全绿；`verify_layout_gate.py` → 10/10 变红 |
| M1：夹具生成器 + 独立真值 + Adult 基线 | ✅ | `py -3.12 tools/gen_fixtures.py --check` → 四组逐字节一致 |
| M2：等价类引擎（k/l/t + 三策略 + 违例三件套） | ✅ | `pytest tests/test_m2_classes.py`；`scan.json` 与 `small/truth.json` 的 `by_policy` 三块一致 |
| **M3：组合搜索（剪枝 / 预算 / 边界集 / 三态 / 曲线）** | ✅ | `search.json` 与四组 `truth["search"]` 逐项一致；`search_scenarios` 三组逐组一致；`pytest tests/test_m3_search.py` |
| 计算实现模块 M1（`schema` 子命令） | ⬜ | `anonymity-scanner schema ...` → `MODULE_NOT_READY` + 退出码 `2`（**设计如此**） |
| 计算实现模块 M4–M5 | ⬜ | `risk` / `gate` 均 `MODULE_NOT_READY` + `2` |
| 全量测试 | ✅ | `py -3.12 -m pytest` → **206 passed**；`py -3.8 -m pytest` → **206 passed**；干净树（无 `*.csv`）→ **143 passed + 63 skipped** |

**本轮实测命令与输出摘要**（2026-10-20，本机）：

```text
py -3.12 -m pytest            → 206 passed in 5.79s
py -3.8  -m pytest            → 206 passed in 9.24s
# 干净树（复制时排除 *.csv / __pycache__ / .pytest_cache / .git）
py -3.12 -m pytest            → 143 passed, 63 skipped
py -3.12 tools/check_sprint_layout.py → 全绿（LAYOUT.RELEASE 为 SKIP）
```

`search` 冒烟（budget 夹具，k=5、budget=40）：

```text
search      : k=5 budget=40 pool=10 evaluated=40 pruned=0 completeness=budget-truncated sets=10 → violation (exit 1)
collapse    : non-exhaustive（非穷尽结果，不是最小崩塌集；状态 budget-truncated）
```

## 二、当前事实 · 状态不变量（下一棒动手前必须知道）

1. **M2 的 API 就是 M4 的分组函数**（K1，禁止重写）：`m2_classes.group_rows(table, columns, policy)`
   → `(classes, undecided, values_by_key)`；`m2_classes.k_of(classes)`。M4 只许 import 这两个
   （以及 `MISSING_CLASS_KEY`，如果要给 `separate-class` 的类起名）。**不要**再写一份分组 / 缺失判定。
2. **M3 的模块是 `m3_search.py`**，导出 `search()` / `outcome_for()` / `completeness()` /
   `collapse_sets_status()` / `monotonicity_holds()`。M4 不 import 它（风险口径只依赖 M2 的类大小）。
3. **`truth["unique_records"]` 是 M4 的现成真值**：它是默认策略 + 完整 QI 集合下**单例类**的行号
   （升序），正是 `prosecutor` 口径要输出的行号集合。四组夹具都有（tiny 12 个、small 56 个、
   prune/budget 也有）。`prosecutor` 的测试直接与它逐项比对。
4. **类 id 的独立复算方式**：等价类键 = 按**声明书写顺序**用 `name=value` 以 `|` 拼接
   （`data/README.md` §4.3）。测试里可用 `truth["declaration_order"]` 拼键独立复核，
   不要反过来用 `group_rows` 的输出当真值。
5. **真值的 `declaration_order` 是有序数组**：`canonical.dumps(sort_keys=True)` 会打乱
   `declaration.columns` 的对象键序。写声明 / 复算键序必须读 `declaration_order`。
6. **`separate-class` 的缺失类键** = `m2_classes.MISSING_CLASS_KEY`（`"__MISSING__"`）；
   `drop` 下的未裁决行**不在任何类里**，M4 必须给它们明确的 `class_id: null` 与
   `undefined_reason`（或 `records` 里标注 `participates: false`），不得静默丢掉。
7. **空表 / 全被丢的边界**：`group_rows` 返回空 `classes`。M4 必须 `records: []` +
   `undefined_reason`（`"empty_table"` / `"no_participating_rows"`）+ 退出码 `2`，
   **不得**返回 `pass`（`plan/03 §模块 M4` 的失败路径；fail-closed 硬规则）。
8. **三口径阈值写死在 `data/README.md` §4.8**：`prosecutor` = `class_size == 1`；
   `journalist` = `class_size <= 2`；`marketer` = `class_size < 3`（即 `<= 2`）。
   测试名必须带口径名（`plan/05` M4 DoD）。
9. **`_cmd_risk` 现有校验顺序不要动**：缺策略 / 缺 attacker / attacker 不在枚举都在
   `raise ModuleNotReady` 之前。只替换最后那句 raise。
10. **`main()` 已支持真实结论**：handler 的返回值经 `map_outcome()` 映射（`None` → pass；
    M2 返回 `"pass"/"violation"/"undecidable"`）。M4 照此返回结论字符串：
    有任一条记录命中 → `violation`；无命中 → `pass`；算不出（空表/无参与行）→ `undecidable`。
11. **产物走 `canonical.write_json`**（K3）：`<out-dir>/risk.json`。双跑必须逐字节一致。
    路径用 `canonical.relativize(table.source, root)`，不得写绝对路径（K7）。
12. **`risk` 没有 `--k`/`--budget`**：风险口径只看类大小，不看 k 门限；不要偷偷引入阈值参数。
    报告首屏仍要回显声明（`_echo_declarations`）。
13. **四处状态副本**（`plan/00` 里程碑表 / `plan/05` 状态表 / `README` 状态行 / `plan/06` 覆盖对标表）
    M4 收尾时**四处一起改**；漏一处布局门即红。M4 收尾还要写 `plan/HANDOFF-M5.md`（七节）。
14. **`plan/06` 缺口表**：G1 的"缺口状态"列不得出现已 ✅ 的里程碑编号（M3 已从归属列移除）；
    关闭 M4 部分时同样**只描述、不点名文件**，缺口列不写 `M4`。

## 三、下一棒待办（M4）

- [ ] 写 `src/anonymity_scanner/m4_risk.py`：纯函数（不写盘、不读时钟/随机、不 import `cli`）。
      API 建议：`classify(classes, attacker)` → 每类判定；`risk(table, pool, policy, attacker, sensitive=())`
      → 含 `attacker` / `threshold` / `records` / `flagged_rows` / `by_class_size` / `verdict` /
      `undefined_reason`。记录按行号升序输出，类 id 用 §4.3 的键。
- [ ] `_cmd_risk` 接上它：产物 `risk.json`；返回真实结论；空表/无参与行 → `undecidable`（退出码 2）。
- [ ] 四组夹具：`prosecutor` 的 `flagged_rows` 与 `truth["unique_records"]` 逐项一致；
      类 id 用 `declaration_order` 独立拼键复核。
- [ ] 三口径各至少一个专门用例（测试名带 `prosecutor` / `journalist` / `marketer`）：
      手工构造 1 / 2 / 3 人等价类，断言边界值（`==1`、`<=2`、`<3`）互不串味。
- [ ] `drop` + 缺失行：未裁决行的表达被测试锁定（不得静默消失，也不得 `pass`）。
- [ ] `separate-class`：缺失类的 `class_id` = `__MISSING__`，类大小单独给出。
- [ ] 双跑 `risk.json` 逐字节一致；序列化走 `canonical`；无绝对路径/时间戳。
- [ ] 更新 `tests/test_contract.py::test_risk_with_valid_arguments_is_module_not_ready`
      （改成断言真实结果；保留缺 attacker / 未知 attacker / 缺策略的契约断言）。
- [ ] 收尾：四处状态副本改 ✅ → 写 `plan/HANDOFF-M5.md`（七节）→ commit。

## 四、既定口径清单（K 编号，动了会打挂测试）

| K | 口径 | 唯一位置 | 改动后果 |
| --- | --- | --- | --- |
| K1 | k/l/t 与 QI 打分公式只有一个实现 | `data/README.md` §4.2–4.3；`m2_classes`（已落地） | 全部数值断言与四组真值同时失效 |
| K2 | 退出码映射单点 | `exit_codes.map_outcome` | `tests/test_contract.py` 整组红 |
| K3 | 序列化冻结参数 | `canonical.dumps` | `tests/test_determinism.py` 逐字节断言红 |
| K4 | 缺失值集合 | `tableio.missing_set` | 三策略用例与真值全部偏一格 |
| K5 | 完整性三态闭合互斥 | `data/README.md` §4.5；`m3_search.completeness`（已落地） | M3 的"不得冒充穷尽"断言失效 |
| K6 | 行号语义（1 起、不含表头、空行不占号） | `tableio.read_table` | 真值里的 `row_numbers` 与 M4 逐记录输出全错位 |
| K7 | 报告无时间戳/主机名/绝对路径 | `canonical.relativize` + 序列化单点 | `test_output_has_no_timestamp_hostname_or_abs_path` 红 |
| K8 | 计算层禁 import CLI、禁读时钟/随机 | `tests/test_m2_classes.py` / `tests/test_m3_search.py` 的同型守门 | 确定性承诺失效 |
| K9 | 版本号单一来源 | `__init__.__version__` | `tools/scaffold_selftest.py` 的 `VERSION.SINGLE_SOURCE` 红 |
| K10 | 真值由生成器独立 oracle 写出，不 import 生产模块 | `plan/04 §二`；`tools/fixture_oracle.py` | 真值变成"自证"，基准永久全绿 |
| K11（M4 新增） | 攻击者阈值 `1 / 2 / 3` 只写在 §4.8 表里 | `data/README.md` §4.8；`m4_risk.classify` 落地后引用同一张表 | 三口径边界互串，测试名失去意义 |

## 五、本机环境坑（只写实测过的）

- **`python` 是商店占位符**：本机一律 `py -3.12 ...` / `py -3.8 ...`。两条通道都能跑全量测试。
- **子进程测试不要整份替换 `env`**：Windows 上用 `dict(os.environ)` 起底，只覆盖编码与 `PYTHONPATH`
  （见 `tests/test_fixtures.py::_clean_env`）。
- **跨盘符 `relpath` 抛 ValueError**：一律走 `canonical.relativize`。
- **`.gitignore` 排除 `*.csv` / `*.data` / `*.names`**：`data/fixtures/*/table.csv` 不入库。
  依赖表格的测试必须 `pytest.skip` 而不是 fail；干净树里 **143 passed + 63 skipped** 是预期。
  其中 M3 新增 40 项 skip（四组真值对照 4 + CLI 对照 4 + 场景 12 + 空集/无解 8 + 预算/单调性/剪枝 5 +
  曲线 4 + 双跑/序列化/顺序 3），M3 另有 7 项不依赖表格（`completeness` 真值表、退出码映射、纯函数校验、
  计算层纪律、场景名集合）；其余 23 项是 M1–M2 既有 skip。
- **`canonical.dumps(sort_keys=True)` 会打乱声明键序**：复算等价类键时读真值的 `declaration_order`。
- **`.gitignore` 里的 `.pytest_cache` / `__pycache__`**：干净树复制时排除它们，否则会带上上一轮的缓存。
- **`tests/conftest.py` 已把 `src/` 注入 `sys.path`**：未安装也能跑 pytest，别删。
- **M3 的额外口径提醒**：`search()` 早退（无解）时 `completeness` 是 `exhausted`（真值如此）；
  `evaluated_subsets` 不含为 `declared_k` 做的单独计算；`outcome_for()` 才是 CLI 退出码的来源。
  M4 不要照抄 `verdict` 字段当退出码（`search` 的 `verdict` 是 `ok`/`no_solution`）。

## 六、DoD 逐项 checklist（M4）

- [ ] `anonymity-scanner risk` 能跑出 `risk.json`；`prosecutor` 的行号与 `truth["unique_records"]` 一致
- [ ] 三口径各有一个测试名带口径名的用例，边界值（1 / 2 / 3）被手工构造的类锁死
- [ ] `records` 按行号升序；每条给 `row_number` / `class_id` / `class_size` / `flagged` / `attacker`
- [ ] 空表 → `records: []` + `undefined_reason="empty_table"` + 退出码 `2`；无参与行同理
- [ ] `drop` 未裁决行与 `separate-class` 缺失类的表达被测试锁定
- [ ] 双跑 `risk.json` 逐字节一致；`canonical` 冻结参数；无绝对路径/时间戳
- [ ] 计算层纪律测试（不 import CLI、不读时钟/随机、不 import 真值工具）
- [ ] `tests/test_contract.py` 的 risk 断言按实际更新（保留契约面断言）
- [ ] 四处状态副本改 ✅ 后布局门绿；`verify_layout_gate.py` 10/10 变红
- [ ] 双通道（3.8 / 3.12）全量 pytest 绿；干净树 skip 数如实记录
- [ ] `plan/HANDOFF-M5.md` 落盘（七节齐）

## 七、关键命令速查

```bash
# 门（顺序固定：先布局门，再变异验证）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/verify_layout_gate.py
py -3.12 tools/scaffold_selftest.py

# 测试（双通道）
py -3.12 -m pytest
py -3.8  -m pytest
py -3.12 -m pytest tests/test_m3_search.py -q     # M3 的验收（回归用）
py -3.12 -m pytest tests/test_m4_risk.py -q       # M4 落地后

# 夹具（表不入库；真值与 manifest 入库）
py -3.12 tools/gen_fixtures.py
py -3.12 tools/gen_fixtures.py --check

# scan / search 冒烟（M2 / M3 已落地）
anonymity-scanner scan --table data/fixtures/small/table.csv \
    --decl <decl.json> --missing-policy drop --k 5 --out-dir out/
anonymity-scanner search --table data/fixtures/small/table.csv \
    --decl <decl.json> --missing-policy drop --k 5 --budget 256 --out-dir out/

# risk 契约冒烟（当前应 rc=2 且报 MODULE_NOT_READY；M4 落地后改为真实结论）
anonymity-scanner risk --table data/fixtures/small/table.csv \
    --decl <decl.json> --missing-policy drop --attacker journalist --out-dir out/

# 收尾顺序（硬约束）
# DoD 验证 → plan/00·05·06 + README 四处状态回写 → 写 HANDOFF-M5 → commit
```
