# HANDOFF-M5 · 第 5 棒启动包（可复算 gate + 判据文件）

> **用法**：新对话第一件事 = 跑 `py -3.12 tools/check_sprint_layout.py`（闸门在 `AGENTS.md`）。
> 本文件由 M4 棒收尾时写，是 M5 的**唯一启动上下文**；`plan/` 里的计划文件是背景，本文件是现状。
> 交付里程碑：**M5 = 可复算 gate + 判据文件**（`anonymity-scanner gate`：`gate.json` + `gate.md` + 退出码）。

## 一、当前进度与证据

| 项 | 状态 | 证据（可复跑） |
| --- | --- | --- |
| M0：装订 + 计划套件 + 可运行骨架 | ✅ | `py -3.12 tools/check_sprint_layout.py` → 全绿；`verify_layout_gate.py` → 10/10 变红 |
| M1：夹具生成器 + 独立真值 + Adult 基线 | ✅ | `py -3.12 tools/gen_fixtures.py --check` → 四组逐字节一致 |
| M2：等价类引擎（k/l/t + 三策略 + 违例三件套） | ✅ | `pytest tests/test_m2_classes.py`；`scan.json` 与 `small/truth.json` 的 `by_policy` 三块一致 |
| M3：组合搜索（剪枝 / 预算 / 边界集 / 三态 / 曲线） | ✅ | `pytest tests/test_m3_search.py`；`search.json` 与四组 `truth["search"]` 逐项一致 |
| **M4：逐记录风险（三口径 + `risk.json`）** | ✅ | `pytest tests/test_m4_risk.py`；四组夹具 `prosecutor` 的 `flagged_rows` 与 `truth["unique_records"]` 逐项一致；双跑逐字节一致 |
| 计算实现模块 M1（`schema` 子命令） | ⬜ | `anonymity-scanner schema ...` → `MODULE_NOT_READY` + 退出码 `2`（**设计如此**） |
| 计算实现模块 M5（`gate` 子命令） | ⬜ | `gate ...` → `MODULE_NOT_READY` + `2`（**本棒要替换它**） |
| 全量测试 | ✅ | `py -3.12 -m pytest` → **227 passed**；`py -3.8 -m pytest` → **227 passed**；干净树（无 `*.csv`）→ **155 passed + 72 skipped** |

**本轮实测命令与输出摘要**（2026-10-20，本机）：

```text
py -3.12 -m pytest            → 227 passed in 5.94s
py -3.8  -m pytest            → 227 passed in 7.32s
# 干净树（复制时排除 *.csv / __pycache__ / .pytest_cache / .git）
py -3.12 -m pytest            → 155 passed, 72 skipped
py -3.12 tools/check_sprint_layout.py → 全绿（LAYOUT.RELEASE 为 SKIP）
```

`risk` 冒烟（`test_contract` 的 3 行表，`separate-class` + `journalist`）：

```text
risk        : attacker=journalist rule=class_size <= 2 classes=3 flagged=3/3 → violation (exit 1)
```

## 二、当前事实 · 状态不变量（下一棒动手前必须知道）

1. **M5 复用既有计算层，不重写统计**：`m2_classes.summarize(table, qi, sensitive, policy, k, l_threshold=..., t_threshold=...)`
   是 k/l/t 与违例三件套的唯一实现（K1）；`m3_search.search(table, qi, sensitive, policy, k, budget=..., require_exhaustive=...)`
   是组合搜索的唯一实现。M5 只做“读判据 → 调 M2（可选 M3）→ 组装结论 → 映射退出码”。
2. **M2 的 `summary["verdict"]` 可以直接用，但 M3 的 `search["verdict"]` 不是退出码**：
   `search` 的 `verdict` 是 `ok` / `no_solution`；退出码只看 `m3_search.outcome_for(result)`（K5 旁注）。
3. **`_cmd_gate` 现在的形状**：`_load_criteria` → 解析判据里的相对路径（基准 = 判据文件所在目录）→ `read_table`
   → `load_declaration` → 无 qi 列报 `DeclarationError` → `_echo_declarations` → **`raise ModuleNotReady(...)`**。
   本棒只替换最后那句 raise（与 M4 的做法一致）；**前面校验顺序别动**，否则 `tests/test_contract.py` 的
   gate 契约组会红。
4. **判据文件当前只做了半套校验**（本棒要补齐，且不得破坏既有断言）：
   - 已校验：顶层必须是对象；`table` / `declaration` / `missing_policy` / `thresholds` 必须存在；
     `thresholds.k` 必须是非 bool 的正整数；`missing_policy` 走 `require_missing_policy`。
   - **未校验**：未知顶层键（`plan/03 §M5` 要求“闭合，未知键即 `CriteriaError`”）、`thresholds.l` / `.t`
     的类型与取值、可选的 `search` 块（`enabled` / `budget` / `require_exhaustive`）。
   - 现有契约断言在 `tests/test_contract.py` 的“gate 判据文件”一节（缺文件 / 缺策略 / 非法 k）。
5. **判据里的路径语义**：相对路径以**判据文件所在目录**为基准（`Path(args.criteria).resolve().parent`），
   不是 cwd。这是“判据是政策输入、必须可搬移”的口径；M5 不得改成 cwd。
6. **产物名固定**（`plan/02 §四`）：`<out-dir>/gate.json` + `<out-dir>/gate.md`。
   JSON 必须走 `canonical.write_json`（K3）；markdown 也必须**纯确定性**（无时间戳 / 主机名 / 绝对路径，LF 结尾）。
7. **退出码优先级必须显式且被测**（建议：`undecidable` > `violation` > `pass`）：
   `data/README.md` §4.6 规定 `0` 需要“所有阈值满足**且**完整性与未被裁剪”；
   `budget-truncated` + `require_exhaustive=true` → `2`。若有违例但搜索被要求穷尽却截断，
   以 fail-closed 取 `2`，并在 `gate.json` 的 `outcome` 与测试里把这条写死（别让两种信号互相覆盖）。
8. **报告首屏回显四项声明**（`plan/01` §六 结论纪律）：角色 / 缺失策略 / 阈值 / 预算。
   现有 `_echo_declarations` 只回显前三项（预算在 `search` 里才出现）；gate.md 需按判据补齐预算与
   “是否要求穷尽”。
9. **违例三件套是硬要求**：`gate.md` 每条违例必须给“分组键 + 计数 + 行号”（§4.7）；
   `scan.json` 里现成的 `violations` 就是这个形状，不要重新拼一份不同字段名。
10. **M4 的 `risk.json` 不在 gate 主路径内**：`plan/03 §M5` 的判据文件没有 `attacker` 字段。
    若要在 gate 里带风险摘要，只能作为可选块并保持“未知键即报错”的闭合性——本棒默认不做。
11. **`examples/adult/` 目录尚不存在**：`plan/00` 的文档索引把它标成 ⬜ M5，G3 也挂在 M5。
    M5 收尾至少要落脚本 + 判据 + 实测摘要（Adult 表不入库；`.gitignore` 排除 `*.csv` / `*.data`）。
12. **四处状态副本**（`plan/00` 里程碑表 / `plan/05` 状态表 / `README` 状态行 / `plan/06` 覆盖对标表）
    M5 收尾时**四处一起改**；漏一处布局门即红。M5 收尾还要写 `plan/HANDOFF-M6.md`（七节）。
13. **`plan/06` 缺口表**：G1 的“缺口状态”列不得出现已 ✅ 的里程碑编号；关闭 M5 部分时同样
    **只描述、不点名文件**，缺口列不写 `M5`。G3（Adult 端到端）若已实跑，按“回填事实”关闭。
14. **`data/README.md` §4.6 是退出码唯一出处**；代码里只允许 `exit_codes.map_outcome` 一处映射（K2），
    gate 的组合优先级是**结论层**的判定，不另写退出码表。

## 三、下一棒待办（M5）

- [ ] 写 `src/anonymity_scanner/m5_gate.py`：纯函数优先（读判据/表由 CLI 传入；渲染 markdown 不读时钟/环境）。
      建议 API：`load_criteria(path)`（闭合校验）→ `evaluate(table, decl, criteria)` →
      `{declarations, scan, search?, violations, outcome, undefined_reason, ...}`；`render_markdown(document)`。
- [ ] 把 `_load_criteria` 的闭合校验补齐：未知顶层键 / 未知 `search` 键 / `thresholds.l` / `.t` 类型与范围
      （`l` 正整数、`t` 落在 `[0,1]`、`null` 表示未启用）；`l/t` 启用但无 sensitive 列 → `CriteriaError`。
- [ ] `_cmd_gate` 接上它：替换 `raise ModuleNotReady`；产出 `gate.json` + `gate.md`；返回真实结论。
- [ ] 判据文件（闭合示例）：
      `{"table": ..., "declaration": ..., "missing_policy": ..., "thresholds": {"k": 5, "l": null, "t": null},
        "search": {"enabled": true, "budget": 256, "require_exhaustive": false}}`
      默认（缺 `search`）= 不跑搜索；`enabled: false` 亦同。
- [ ] `gate.md`：首屏四项声明；扫描结论；违例三件套逐条；搜索边界集与完整性三态（非穷尽时**不得**写“最小崩塌集”）；
      末尾给退出码与“可复算说明”（命令 + 判据路径相对化）。
- [ ] 退出码三态用例：`pass`（小表全达标）/ `violation`（tiny 或 small）/ `undecidable`
      （坏判据、空表、`budget-truncated` + `require_exhaustive=true`）。
- [ ] 双跑 `gate.json` 逐字节一致、`gate.md` 逐字节一致；无绝对路径 / 时间戳 / 主机名。
- [ ] `tests/test_contract.py` 的 `test_gate_valid_criteria_is_module_not_ready` 改成断言真实结果；
      保留缺文件 / 缺策略 / 非法 k 的契约断言，并新增未知键、非法 l/t、坏 `search` 块。
- [ ] Adult 端到端：`examples/adult/`（`run.sh` + `criteria.json` + `EXPECTED.md`），实测回填；
      `data/README.md` §二 已有读入基线（32561 × 15，sha256 已回填），不要重下载到仓库。
- [ ] 收尾：四处状态副本改 ✅ → 关闭 G1/G3 的对应部分（只描述）→ 写 `plan/HANDOFF-M6.md`（七节）→ commit。

## 四、既定口径清单（K 编号，动了会打挂测试）

| K | 口径 | 唯一位置 | 改动后果 |
| --- | --- | --- | --- |
| K1 | k/l/t 与 QI 打分公式只有一个实现 | `data/README.md` §4.2–4.3；`m2_classes`（已落地） | 全部数值断言与四组真值同时失效 |
| K2 | 退出码映射单点 | `exit_codes.map_outcome` | `tests/test_contract.py` 整组红 |
| K3 | 序列化冻结参数 | `canonical.dumps` | `tests/test_determinism.py` 逐字节断言红 |
| K4 | 缺失值集合 | `tableio.missing_set` | 三策略用例与真值全部偏一格 |
| K5 | 完整性三态闭合互斥 | `data/README.md` §4.5；`m3_search.completeness`（已落地） | M3 的“不得冒充穷尽”断言失效 |
| K6 | 行号语义（1 起、不含表头、空行不占号） | `tableio.read_table` | 真值里的 `row_numbers` 与 M4 逐记录输出全错位 |
| K7 | 报告无时间戳/主机名/绝对路径 | `canonical.relativize` + 序列化单点 | `test_output_has_no_timestamp_hostname_or_abs_path` 红 |
| K8 | 计算层禁 import CLI、禁读时钟/随机 | M2/M3/M4 的同型守门测试 | 确定性承诺失效 |
| K9 | 版本号单一来源 | `__init__.__version__` | `tools/scaffold_selftest.py` 的 `VERSION.SINGLE_SOURCE` 红 |
| K10 | 真值由生成器独立 oracle 写出，不 import 生产模块 | `plan/04 §二`；`tools/fixture_oracle.py` | 真值变成“自证”，基准永久全绿 |
| K11 | 攻击者阈值 `1 / 2 / 3` 只写在 §4.8 表里 | `data/README.md` §4.8；`m4_risk.classify`（已落地） | 三口径边界互串，测试名失去意义 |

## 五、本机环境坑（只写实测过的）

- **`python` 是商店占位符**：本机一律 `py -3.12 ...` / `py -3.8 ...`。两条通道都能跑全量测试。
- **子进程测试不要整份替换 `env`**：Windows 上用 `dict(os.environ)` 起底，只覆盖编码与 `PYTHONPATH`
  （见 `tests/test_fixtures.py::_clean_env`）。
- **跨盘符 `relpath` 抛 ValueError**：一律走 `canonical.relativize`。
- **`.gitignore` 排除 `*.csv` / `*.data` / `*.names`**：`data/fixtures/*/table.csv` 不入库。
  依赖表格的测试必须 `pytest.skip` 而不是 fail；干净树里 **155 passed + 72 skipped** 是预期。
  其中 M4 新增 9 项 skip（四组真值 4 + 类 id 复算 2 + CLI 真值 1 + 双跑 1 + 序列化 1）；
  其余 63 项是 M1–M3 既有 skip。
- **`canonical.dumps(sort_keys=True)` 会打乱声明键序**：复算等价类键时读真值的 `declaration_order`。
- **`.gitignore` 里的 `.pytest_cache` / `__pycache__`**：干净树复制时排除它们，否则会带上上一轮的缓存。
- **`tests/conftest.py` 已把 `src/` 注入 `sys.path`**：未安装也能跑 pytest，别删。
- **`gate.md` 是新增的文本产物**：不要用 `json.dumps` 的缩进风格硬拼；用固定模板 + 已排序的列表，
  并像 JSON 一样用 `canonical.write_text_atomic` 落盘（强制 LF）。
- **Adult 数据不在仓库**：M5 的端到端演示只读本地文件；脚本不得联网下载。

## 六、DoD 逐项 checklist（M5）

- [ ] `anonymity-scanner gate --criteria ... --out-dir ...` 产出 `gate.json` + `gate.md`，返回真实的 `0/1/2`
- [ ] 判据闭合：未知顶层键 / 未知 `search` 键 / 非法 `thresholds.l` / `.t` → `CriteriaError` + 退出码 `2`
- [ ] `pass` / `violation` / `undecidable` 三态各有用例；空表与 `require_exhaustive` 截断都落到 `2`
- [ ] `gate.md` 首屏四项声明齐；每条违例给“分组键 + 计数 + 行号”
- [ ] 非穷尽搜索不得写成“最小崩塌集”；完整性三态在报告里显式
- [ ] 双跑 `gate.json` / `gate.md` 均逐字节一致；无绝对路径 / 时间戳 / 主机名
- [ ] 计算层纪律：`m5_gate` 不 import CLI、不读时钟/随机；CLI 之外无第二份判据解析
- [ ] `tests/test_contract.py` 的 gate 组按实际更新（保留契约面断言）
- [ ] Adult 端到端演示落盘并实测（`examples/adult/`），G3 按事实回填
- [ ] 四处状态副本改 ✅ 后布局门绿；`verify_layout_gate.py` 10/10 变红
- [ ] 双通道（3.8 / 3.12）全量 pytest 绿；干净树 skip 数如实记录
- [ ] `plan/HANDOFF-M6.md` 落盘（七节齐）

## 七、关键命令速查

```bash
# 门（顺序固定：先布局门，再变异验证）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/verify_layout_gate.py
py -3.12 tools/scaffold_selftest.py

# 测试（双通道）
py -3.12 -m pytest
py -3.8  -m pytest
py -3.12 -m pytest tests/test_m4_risk.py -q    # M4 回归
py -3.12 -m pytest tests/test_m5_gate.py -q    # M5 落地后

# 夹具（表不入库；真值与 manifest 入库）
py -3.12 tools/gen_fixtures.py
py -3.12 tools/gen_fixtures.py --check

# scan / search / risk 冒烟（M2–M4 已落地）
anonymity-scanner scan --table data/fixtures/small/table.csv \
    --decl <decl.json> --missing-policy drop --k 5 --out-dir out/
anonymity-scanner search --table data/fixtures/small/table.csv \
    --decl <decl.json> --missing-policy drop --k 5 --budget 256 --out-dir out/
anonymity-scanner risk --table data/fixtures/small/table.csv \
    --decl <decl.json> --missing-policy drop --attacker journalist --out-dir out/

# gate 契约冒烟（当前应 rc=2 且报 MODULE_NOT_READY；M5 落地后改为真实结论）
anonymity-scanner gate --criteria <criteria.json> --out-dir out/

# 收尾顺序（硬约束）
# DoD 验证 → plan/00·05·06 + README 四处状态回写 → 写 HANDOFF-M6 → commit
```
