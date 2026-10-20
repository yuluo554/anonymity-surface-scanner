# HANDOFF-M2 · 第 2 棒启动包（等价类引擎）

> **用法**：新对话第一件事 = 跑 `py -3.12 tools/check_sprint_layout.py`（闸门在 `AGENTS.md`）。
> 本文件由 M1 棒收尾时写，是 M2 的**唯一启动上下文**；`plan/` 里的计划文件是背景，本文件是现状。
> 交付里程碑：**M2 = 等价类引擎**（`anonymity-scanner scan`：k / l / t、三种缺失策略、违例三件套）。

## 一、当前进度与证据

| 项 | 状态 | 证据（可复跑） |
| --- | --- | --- |
| M0：装订 + 计划套件 + 可运行骨架 | ✅ | `py -3.12 tools/check_sprint_layout.py` → 全绿；`verify_layout_gate.py` → 10/10 变红 |
| **M1：夹具生成器 + 独立真值 + Adult 基线** | ✅ | `py -3.12 tools/gen_fixtures.py --check` → 四组逐字节一致；`pytest tests/test_fixtures.py` → 49 项绿；Adult 真实件实跑 32561 × 15 |
| 计算实现模块 M1（`schema` 子命令） | ⬜ | `anonymity-scanner schema ...` → `MODULE_NOT_READY` + 退出码 `2`（**设计如此**） |
| 计算实现模块 M2–M5 | ⬜ | 同上，四条子命令均 `MODULE_NOT_READY` + `2` |
| 全量测试 | ✅ | `py -3.12 -m pytest` → **129 passed**；`py -3.8 -m pytest` → **129 passed**；干净 clone（无 `*.csv`）→ **125 passed + 4 skipped** |

**本轮实测命令与输出摘要**（2026-10-20，本机）：

```text
py -3.12 tools/gen_fixtures.py
  tiny      12 行 ×  7 列  truth sha256=61b5aa07d0779f9a…
  small     60 行 ×  8 列  truth sha256=60e979efdaa9f5b1…
  prune    300 行 ×  9 列  truth sha256=d03b29b395c22148…
  budget  1200 行 × 10 列  truth sha256=6ba33d26ee2c5f46…
py -3.12 tools/gen_fixtures.py --check   → 逐字节一致（4 组夹具）   rc=0
py -3.12 tools/adult_baseline.py          → 未取得本地文件（不代下载）rc=3
py -3.12 tools/adult_baseline.py --table /tmp/adult/adult.data
  → rows 32561（期望一致）/ columns 15 / sha256 5b002646…603d
    含问号的列：workclass=1836, occupation=1843, native-country=583        rc=0
py -3.12 -m pytest                        → 129 passed
py -3.8  -m pytest                        → 129 passed
py -3.12 tools/check_sprint_layout.py     → 全绿（LAYOUT.RELEASE 为 SKIP）
```

## 二、当前事实 · 状态不变量（下一棒动手前必须知道）

1. **真值已经落盘，M2 不许改它**：`data/fixtures/*/truth.json` 是 M1 的交付面。M2 的每次断言都拿它做对照；
   发现真值错了要**改生成器并重跑**（`py -3.12 tools/gen_fixtures.py`），不许手改 JSON——`--check` 会当场抓出来。
2. **真值与生产实现互不 import**（K10）：`tools/fixture_oracle.py` 不 import `anonymity_scanner`，
   `tests/test_fixtures.py` 用 AST 守门。M2 写 `m2_classes.py` 时**不要**为了"复用"去 import oracle——
   那会把独立判据变成同一份实现，基准永久全绿。
3. **空集语义（M1 已定口径，`plan/00` 勘误 E2）**：空集的 k = **参与分组的行数**。
   `minimal_collapse_sets: [[]]` 的语义是"**一个 QI 列都不能加**"，不是"什么都不用声明"。
   `data/README.md` §4.5 有对照表，`plan/01` 原文这处措辞有误（不改写，按勘误实现）。
4. **"含缺失的行"只看参与本次分组的列**（`data/README.md` §4.4 末条）：空集下没有任何列参与，
   所以 `drop` 策略下空集的 k 仍是**全部行**（`small` 实测 60，不是 56）。
   M2 的分组函数必须按这个语义写，否则真值对不上。
5. **三种缺失策略的期望值已在真值里**：`small/truth.json` 的 `by_policy` 三块**互不相同**
   （类数 51 / 54 / 52），是 M2 的主用例。
   无缺失的三组夹具把后两种写成 `{"same_as": "drop"}`——读到这个键就回退到 `drop` 块。
6. **`l` 与 `t` 的口径**：`l` = 逐 sensitive 列算类内不同取值数 → 列间取最小 → 再取全部类的最小；
   `t` = 逐类逐列与**全表分布**（`drop` 下不含未裁决行）的总变差距离 `0.5 × Σ|p_class − p_all|` → 取最大。
   `small` 的 `t` 在 `drop` 下是 `0.678571`、另两种策略是 `0.666667`——差异正是"全表分布含不含被丢的行"。
7. **行号 = 数据行序号，1 起，不含表头，空行不占号**（K6）。真值里 `violations[].row_numbers` 按此写。
8. **退出码映射只此一处**：`exit_codes.map_outcome()`。M2 落地时**只替换 `_cmd_scan` 最后那句
   `raise ModuleNotReady`**，前面的校验顺序不要动（`tests/test_contract.py` 逐条钉住）。
   注意：`test_scan_*` 里有几条断言当前会**因为 M2 实现而需要改成断言真实结果**——
   改测试时保留"缺 `--missing-policy` 仍 `2`"这类契约断言，只把"未实现 → 2"换成"算出来了"。
9. **序列化只有一处**：`canonical.dumps()` / `write_json()`。`scan.json` 必须走它。
   `round6()` 用 `Decimal(str(x))`，不要改成 `Decimal(x)`。
10. **四处状态副本**（`plan/00` 里程碑表 / `plan/05` 状态表 / `README` 状态行 / `plan/06` 覆盖对标表）
    必须逐处一致。M2 收尾时**四处一起改**，漏一处布局门即红。
11. **`plan/06` 缺口表**：关闭 G1 的 M2 部分时**只描述、不点名 `.md` 文件名**。
12. **文档点名的 `tools/*.py` 必须有实物**：`LAYOUT.DOC_TOOLS` 逐个断言存在。新增脚本先写文件再写路径。

## 三、下一棒待办（M2）

- [ ] 写 `src/anonymity_scanner/m2_classes.py`：纯函数，输入 `Table` + `Declaration` + 策略 + 阈值，
      输出 k/l/t、类大小直方图、违例三件套、未裁决行、缺失独立类。**不写盘、不读时钟**（K8）。
- [ ] `_cmd_scan` 接上它：产物 `scan.json` 走 `canonical.write_json`；`gate.md` 人读报告留给 M5。
- [ ] 三种缺失策略各一组用例，**直接对 `data/fixtures/small/truth.json` 的 `by_policy` 逐项断言**
      （k / l / t / class_count / violations / undecided_rows / missing_class）。
- [ ] `single-column` 与 `separate-class` 的 `l` 值**人工推导后在测试里写死一个常量**，
      不是只与真值互相比对（针对 sdcMicro #363 型坑）。
- [ ] 边界：空表（只有表头）、单行表、全 QI 相同的表——三种都要有定义行为。
      `k=null` + `undefined_reason="empty_table"`，退出码按"无法裁决"（`2`）。
- [ ] 双跑逐字节一致（`scan.json`）。
- [ ] 收尾：四处状态副本改 ✅ → 写 `plan/HANDOFF-M3.md`（七节）→ commit。

## 四、既定口径清单（K 编号，动了会打挂测试）

| K | 口径 | 唯一位置 | 改动后果 |
| --- | --- | --- | --- |
| K1 | k/l/t 与 QI 打分公式 | `data/README.md` §4.2–4.3；实现 `m1_candidates`（M1 模块，未落地）/ `m2_classes`（M2） | 全部数值断言与四组真值同时失效 |
| K2 | 退出码映射单点 | `exit_codes.map_outcome` | `tests/test_contract.py` 整组红 |
| K3 | 序列化冻结参数 | `canonical.dumps` | `tests/test_determinism.py` 逐字节断言红 |
| K4 | 缺失值集合 | `tableio.missing_set` | 三策略用例与真值全部偏一格 |
| K5 | 完整性三态闭合互斥 | `data/README.md` §4.5；`m3_search.completeness`（M3 落地） | M3 的"不得冒充穷尽"断言失效 |
| K6 | 行号语义（1 起、不含表头、空行不占号） | `tableio.read_table` | 真值里的 `row_numbers` 全错位 |
| K7 | 报告无时间戳/主机名/绝对路径 | `canonical.relativize` + 序列化单点 | `test_output_has_no_timestamp_hostname_or_abs_path` 红 |
| K8 | 计算层禁 import CLI、禁读时钟/随机 | `plan/03 §K` | 确定性承诺失效 |
| K9 | 版本号单一来源 | `__init__.__version__` | `tools/scaffold_selftest.py` 的 `VERSION.SINGLE_SOURCE` 红 |
| K10 | 真值由生成器独立 oracle 写出，不 import 生产模块 | `plan/04 §二`；`tools/fixture_oracle.py` | 真值变成"自证"，基准永久全绿 |

## 五、本机环境坑（只写实测过的）

- **`python` 是商店占位符**：本机一律 `py -3.12 ...` / `py -3.8 ...`。两条通道都能跑全量测试。
- **子进程测试不要整份替换 `env`**：Windows 上 `env={"PYTHONUTF8": "1"}` 会让解释器在
  `_Py_HashRandomization_Init` 阶段直接崩（本轮实测，3.8 通道连红 8 条）。
  正确做法见 `tests/test_fixtures.py::_clean_env`：`dict(os.environ)` 起底，只覆盖编码与 `PYTHONPATH`。
- **跨盘符 `relpath` 抛 ValueError**（C: → D:）：一律走 `canonical.relativize`，不要直接 `os.path.relpath`。
- **`.gitignore` 排除 `*.csv`**：`data/fixtures/*/table.csv` **不入库**。需要在干净 clone 里复现时跑
  `py -3.12 tools/gen_fixtures.py`。`--check` 在没有表格的树里也成立（有测试）。
  依赖表的断言在干净树里必须 **skip 而不是 fail**——本轮实测踩过一次（`prune` 的单列 k 断言），已改成念
  `truth["k_by_columns"]`。新增测试时注意这条：干净 clone 下 4 个 skip 是**预期**，不是失败。
- **Adult 原始件也不入库**：`.gitignore` 另加了 `*.data` / `*.names`。M1 曾实下载 `adult.data`
  （3,974,305 B，sha256 `5b002646…603d`，32561 × 15）跑通读入基线，事实回填在 `data/README` §二；
  演示的 k/l/t 属 M5，不在本棒范围。
- **`data/fixtures/README.md` 是手写的**，不在生成物的覆盖范围内；改生成器不会动它。
- **干净 clone 里没有 `.git` 之外的东西**：`tests/conftest.py` 已把 `src/` 注入 `sys.path`，
  未安装也能跑 pytest——发布包验证的通路，别删。

## 六、DoD 逐项 checklist（M2）

- [ ] `anonymity-scanner scan` 能跑出 `scan.json`，内容与 `small/truth.json` 的 `by_policy` 逐项一致
- [ ] 三策略各一组用例；`l` 在 `single-column` / `separate-class` 下**人工推导**后写死断言
- [ ] 违例三件套（分组键 + 计数 + 行号）可手工复核（`tiny` 组 12 行全可手算）
- [ ] 空表 / 单行表 / 全同表边界有定义行为且被测试锁定
- [ ] 双跑 `scan.json` 逐字节一致
- [ ] `tests/test_contract.py` 里"未实现 → 2"的扫描断言按实际情况更新（保留契约面断言）
- [ ] 四处状态副本改 ✅ 后布局门绿
- [ ] 双通道（3.8 / 3.12）全量 pytest 绿
- [ ] `plan/HANDOFF-M3.md` 落盘（七节齐）

## 七、关键命令速查

```bash
# 门（顺序固定：先布局门，再变异验证）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/verify_layout_gate.py
py -3.12 tools/scaffold_selftest.py

# 测试（双通道）
py -3.12 -m pytest
py -3.8  -m pytest
py -3.12 -m pytest tests/test_fixtures.py -q     # M1 的 49 项验收

# 夹具（表不入库；真值与 manifest 入库）
py -3.12 tools/gen_fixtures.py                   # 全集生成
py -3.12 tools/gen_fixtures.py --check           # 逐字节比对（生成器改动未重生成 → 红）
py -3.12 tools/gen_fixtures.py --only tiny       # 局部生成，不改 manifest

# Adult 基线（只读本地，不代下载）
py -3.12 tools/adult_baseline.py --table <adult.data>

# CLI 契约冒烟（当前应全部 rc=2 且报 MODULE_NOT_READY，除 --version）
anonymity-scanner --version
anonymity-scanner scan --table data/fixtures/tiny/table.csv \
    --decl <d.json> --missing-policy drop --k 3 --out-dir out/

# 收尾顺序（硬约束）
# DoD 验证 → plan/00·05·06 + README 四处状态回写 → 写 HANDOFF-M3 → commit
```
