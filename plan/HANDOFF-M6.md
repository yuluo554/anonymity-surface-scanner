# HANDOFF-M6 · 第 6 棒启动包（发布）

> **用法**：新对话第一件事 = 跑 `py -3.12 tools/check_sprint_layout.py`（闸门在 `AGENTS.md`）。
> 本文件由 M5 棒收尾时写，是 M6 的**唯一启动上下文**；`plan/` 里的计划文件是背景，本文件是现状。
> 交付里程碑：**M6 = 发布**（`git tag` + GitHub Release（附 sdist）+ `plan/RELEASE-M6.md`）。

## 一、当前进度与证据

| 项 | 状态 | 证据（可复跑） |
| --- | --- | --- |
| M0：装订 + 计划套件 + 可运行骨架 | ✅ | `py -3.12 tools/check_sprint_layout.py` → 全绿；`verify_layout_gate.py` → 10/10 变红 |
| M1：夹具生成器 + 独立真值 + Adult 基线 | ✅ | `py -3.12 tools/gen_fixtures.py --check` → 四组逐字节一致 |
| M2：等价类引擎（k/l/t + 三策略 + 违例三件套） | ✅ | `pytest tests/test_m2_classes.py` |
| M3：组合搜索（剪枝 / 预算 / 边界集 / 三态 / 曲线） | ✅ | `pytest tests/test_m3_search.py` |
| M4：逐记录风险（三口径 + `risk.json`） | ✅ | `pytest tests/test_m4_risk.py` |
| **M5：可复算 gate（判据闭合 + `gate.json` + `gate.md` + 退出码）** | ✅ | `pytest tests/test_m5_gate.py tests/test_contract.py`；Adult 实跑见 `examples/adult/EXPECTED.md` |
| 计算实现模块 M1（`schema` 子命令） | ⬜ | `anonymity-scanner schema ...` → `MODULE_NOT_READY` + 退出码 `2`（**设计如此**，不在 M6 范围） |
| 全量测试 | ✅ | `py -3.12 -m pytest` → **277 passed**；`py -3.8 -m pytest` → **277 passed**；干净树（无 `*.csv`）→ **205 passed + 72 skipped** |
| 布局门 | ✅ | 全绿（`LAYOUT.RELEASE` 为 `SKIP`：M6 未完成，发布留档尚不适用） |

**M5 实测命令与输出摘要**（2026-10-20，本机）：

```text
py -3.12 -m pytest            → 277 passed in 7.45s
py -3.8  -m pytest            → 277 passed in 10.61s
# 干净树（复制时排除 *.csv / *.data / out / __pycache__ / .pytest_cache / .git）
py -3.12 -m pytest            → 205 passed, 72 skipped
py -3.12 tools/check_sprint_layout.py → 全绿（LAYOUT.RELEASE 为 SKIP）
```

Adult 端到端（`PYTHON="py -3.12" bash examples/adult/run.sh`）：

```text
gate        : policy=drop k=5 l=None t=None search=True violations=762 → violation (exit 1)
k=1  l=1  t=0.75919  classes=1703  rows=32561
search      : completeness=exhausted  evaluated=5  pruned=3  minimal_collapse_sets=[["education","sex"]]
双跑 gate.json / gate.md 逐字节一致（cmp 实测）
```

## 二、当前事实 · 状态不变量（下一棒动手前必须知道）

1. **M5 的判据解析只有一处**：`m5_gate.load_criteria(path)`。CLI 不再 `import json`，也不自己校验判据；
   `tests/test_m5_gate.py::test_criteria_parsing_lives_only_in_m5_gate` 锁定这条。
2. **判据闭合键集**：顶层 `table / declaration / missing_policy / thresholds / search`；
   `thresholds` 只允许 `k / l / t`；`search` 只允许 `enabled / budget / require_exhaustive`。
   未知键、非法 `l`（正整数或 null）、非法 `t`（`[0,1]` 或 null）、`enabled=true` 缺 `budget`、
   `enabled=false` 却 `require_exhaustive=true` → 一律 `CriteriaError`（退出码 `2`）。
3. **判据内相对路径以判据文件所在目录为基准**（`criteria["base"]`），不是 cwd。专项测试：
   `test_gate_resolves_relative_paths_against_criteria_directory`。
4. **退出码优先级**：`combine_outcomes` 实现 `undecidable > violation > pass`；
   退出码仍只由 `exit_codes.map_outcome` 映射（K2）。`budget-truncated + require_exhaustive=true` → `2`，
   即使同时存在违例也取 `2`（fail-closed），测试名带 `require_exhaustive`。
5. **gate 调 M3 时固定传 `require_exhaustive=False`**：gate 需要先拿到"被截断"的事实写进 `gate.json`，
   再按结论层优先级合并；不要让 M3 的异常抹掉证据。
6. **非穷尽措辞是硬约束**：`gate.md` 只有 `completeness == "exhausted"` 才写
   `最小崩塌集（穷尽结果）`；其余写 `崩塌边界集（非穷尽结果…不得称为最小崩塌集）`。
   测试断言 `"最小崩塌集（穷尽结果）" not in markdown`。
7. **`undefined_reason` 与违例的互斥**：已经有违例（outcome=`violation`）时不再挂
   `search_not_exhausted`；只有 outcome 为 `undecidable` 且搜索非穷尽时才挂。
8. **`gate.md` 的类大小直方图只列 `< k` 的部分**（完整直方图在 `gate.json`）；
   这样 Adult 规模下首屏仍可读。
9. **`gate.md` 由固定模板渲染**（`m5_gate.render_markdown`），纯函数、LF 结尾、无时间戳 / 主机名 / 绝对路径；
   双跑逐字节一致有测试。落盘走 `canonical.write_text_atomic`。
10. **`gate.json` 走 `canonical.write_json`**（K3）；`criteria` / `table` 两个路径字段已相对化。
11. **Adult 数据不在仓库**：`examples/adult/adult.csv` 与 `adult.data` 都被 `.gitignore` 排除；
    `run.sh` 只读本地、脚本内无下载命令（测试 `test_adult_example_is_closed_and_offline` 锁定）。
    `prepare.py` 把行尾空字段丢弃、`?` 归一为空串（K4 缺失 token）。
12. **M6 开始前不要动交付面**：`src/`、`pyproject.toml`、`MANIFEST.in` 在 tag 后不得再改；
    发布留档与 README/plan 属 tag 后可动的非交付面（`plan/05` §二 M6 发布门）。
13. **四处状态副本**（`plan/00` 里程碑表 / `plan/05` 状态表 / `README` 状态行 / `plan/06` 覆盖对标表）
    目前 M0–M5 全 ✅、M6 ⬜；M6 收尾时**四处一起改**，漏一处布局门即红。
14. **`plan/06` 缺口表**：G1 只剩 `schema`（M1）未落地；G3（Adult 端到端）已关闭并已写实测事实。
    关闭缺口时只描述、不点名文件；缺口列不得出现已 ✅ 的里程碑编号。
15. **布局门的 `LAYOUT.RELEASE` 只在 M6 ✅ 后启用**：届时必须有 `plan/RELEASE-M6.md`（两栏
    `## 一、tag 前事实` + `## 二、tag 后…`）、含"覆盖对账"小节、且三态行（实现 / 不适用 / 待首推）≥ 3。

## 三、下一棒待办（M6）

- [ ] **发布前最后一遍交付面检查**：`git status` 干净；`git ls-files` 里无 `*.csv` / `*.data` / `out/`；
      `data/README.md` §二 的 Adult sha256 与实际下载件一致（已实测一致，M6 复查即可）。
- [ ] **干净环境验证**：`git archive` 导出树 → 新建 venv → `pip install .` →
      逐条敲 README 命令（`--version`、`scan`、`search`、`risk`、`gate`，含 `examples/adult/run.sh`）。
- [ ] **写 `plan/RELEASE-M6.md`**（tag 前入库）：两栏 + 覆盖对账小节 + 三态行 ≥ 3；
      字面 digest 只写进 Release 正文或 tag 后提交（`plan/05` §五）。
- [ ] **构建 sdist**：`py -3.12 -m build`（或 `pip wheel`），记录 sha256；确认包内**不含表格**。
- [ ] **打 tag**：`git tag -a v0.1.0 -m "..."`；推送 `main` + tag（需用户确认远端与凭据）。
- [ ] **GitHub Release**：附 sdist；正文写 digest、命令示例、退出码表、`EXPECTED.md` 数字（注明判据）。
- [ ] **CI 首推验证**：ubuntu/windows × 3.8/3.12 四个 run；把真实 run 链接/结论回填
      `plan/05` §四"CI 实际运行"与 `plan/06` G2。
- [ ] **tag 后只动非交付面**：`POST_TAG_SCOPE` ⊆ `plan/ README AGENTS tests tools docs`；
      `DELIVERABLE_UNCHANGED` = `src/ pyproject.toml MANIFEST.in` 零差异。
- [ ] **品牌隔离复查**：全文不提姊妹项目；首屏三行定位宣言仍在。
- [ ] **收尾**：四处状态副本改 M6 ✅ → 写 `plan/WRAPUP-M6.md`（或 RELEASE 留档）→ 布局门全绿
      （此时 `LAYOUT.RELEASE` 必须 PASS，不得 SKIP）→ `verify_layout_gate.py` 10/10 变红 → commit。

## 四、既定口径清单（K 编号，动了会打挂测试）

| K | 口径 | 唯一位置 | 改动后果 |
| --- | --- | --- | --- |
| K1 | k/l/t 与 QI 打分公式只有一个实现 | `data/README.md` §4.2–4.3；`m2_classes` | 全部数值断言与四组真值同时失效 |
| K2 | 退出码映射单点 | `exit_codes.map_outcome` | `tests/test_contract.py` / `test_m5_gate.py` 整组红 |
| K3 | 序列化冻结参数 | `canonical.dumps` / `write_json` / `write_text_atomic` | `tests/test_determinism.py` 逐字节断言红 |
| K4 | 缺失值集合 | `tableio.missing_set` | 三策略用例、真值与 `prepare.py` 的 `?` 归一全部偏一格 |
| K5 | 完整性三态闭合互斥 | `data/README.md` §4.5；`m3_search.completeness` | M3/M5 的"不得冒充穷尽"断言失效 |
| K6 | 行号语义（1 起、不含表头、空行不占号） | `tableio.read_table` | 真值与 `gate.md` 行号全错位 |
| K7 | 报告无时间戳/主机名/绝对路径 | `canonical.relativize` + 渲染纯函数 | `test_output_has_no_*` 与 `test_gate_outputs_have_no_*` 红 |
| K8 | 计算层禁 import CLI、禁读时钟/随机 | M2/M3/M4/M5 的同型守门测试 | 确定性承诺失效 |
| K9 | 版本号单一来源 | `__init__.__version__` | `tools/scaffold_selftest.py` 的 `VERSION.SINGLE_SOURCE` 红 |
| K10 | 真值由生成器独立 oracle 写出，不 import 生产模块 | `plan/04 §二`；`tools/fixture_oracle.py` | 真值变成"自证"，基准永久全绿 |
| K11 | 攻击者阈值 `1 / 2 / 3` 只写在 §4.8 表里 | `data/README.md` §4.8；`m4_risk.classify` | 三口径边界互串，测试名失去意义 |

**M5 新增的冻结口径**：判据闭合键集（上 §二 第 2 条）、相对路径基准（第 3 条）、
结论优先级（第 4 条）、非穷尽措辞（第 6 条）。改任一条都要同步 `plan/03 §模块 M5` 与 `tests/test_m5_gate.py`。

## 五、本机环境坑（只写实测过的）

- **`python` 是商店占位符**：本机一律 `py -3.12 ...` / `py -3.8 ...`；`examples/adult/run.sh` 已按
  `PYTHON="py -3.12"` 处理（默认优先 `py -3.12`，再回落 `python3`）。
- **子进程测试不要整份替换 `env`**：Windows 上用 `dict(os.environ)` 起底，只覆盖编码与 `PYTHONPATH`。
- **跨盘符 `relpath` 抛 ValueError**：一律走 `canonical.relativize`（跨盘时回落文件名）。
- **`.gitignore` 排除 `*.csv` / `*.data` / `*.names`**：夹具表与 Adult 原始件都不入库；
  依赖表格的测试必须 `pytest.skip`；干净树 205 passed + 72 skipped 是预期。
  M5 新增的 50 项全部用 `tmp_path` 造表，干净树里**不 skip**。
- **`canonical.dumps(sort_keys=True)` 会打乱声明键序**：复算等价类键时读真值的 `declaration_order`。
- **`.pytest_cache` / `__pycache__` / `out/`**：干净树复制时排除，否则带上上一轮缓存。
- **`tests/conftest.py` 已把 `src/` 注入 `sys.path`**：未安装也能跑 pytest，别删。
- **`gate.md` 是文本产物**：必须走 `canonical.write_text_atomic`（强制 LF），不要用 `print` 直接写。
- **Adult 数据不入库**：M6 干净环境验证时，Adult 演示要么由用户先下载，要么如实标注"未跑数据部分"；
  不要把 `adult.csv` 打进 sdist / Release / git。
- **`gate.md` 体量**：Adult 规模下约 55 KB / 803 行（762 条违例）；`gate.json` 约 240 KB。
  不要在测试里断言文件大小（不同判据会变），断言结构与数字。
- **退出码 1 不是失败**：`examples/adult/run.sh` 会原样透出 gate 的 `1`；CI 里要按"gate 结论"解读，
  不能把 `set -e` 的脚本退出码当成"脚本坏了"。

## 六、DoD 逐项 checklist（M6）

- [ ] `git tag -a v0.1.0` 已打并推送；GitHub Release 附 sdist 可下载
- [ ] `plan/RELEASE-M6.md` 落库（两栏 + 覆盖对账 + 三态行 ≥ 3），字面 digest 符合放置规则
- [ ] 干净环境：`git archive` → venv → `pip install .` → README 命令逐条跑通
- [ ] sdist 内容检查：含 `plan/`、`data/README.md`、`src/`；**不含**任何 `*.csv` / `*.data`
- [ ] CI 首推验证：ubuntu/windows × 3.8/3.12 全绿（或如实记录红与修复）
- [ ] tag 后 `src/ pyproject.toml MANIFEST.in` 零差异（`DELIVERABLE_UNCHANGED`）
- [ ] 四处状态副本 M6 ✅ 一致；布局门全绿且 `LAYOUT.RELEASE` 为 PASS（不是 SKIP）
- [ ] `tools/verify_layout_gate.py` 10/10 变红；`tools/scaffold_selftest.py` 全绿
- [ ] 双通道（3.8 / 3.12）全量 pytest 绿；干净树 skip 数如实记录
- [ ] 品牌隔离与隐私红线复查（无姊妹项目提名、无真实数据入库）

## 七、关键命令速查

```bash
# 门（顺序固定：先布局门，再变异验证）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/verify_layout_gate.py
py -3.12 tools/scaffold_selftest.py

# 测试（双通道 + M5 回归）
py -3.12 -m pytest
py -3.8  -m pytest
py -3.12 -m pytest tests/test_m5_gate.py tests/test_contract.py -q

# 夹具（表不入库；真值与 manifest 入库）
py -3.12 tools/gen_fixtures.py
py -3.12 tools/gen_fixtures.py --check

# gate 冒烟（小表；判据内相对路径以判据文件目录为基准）
anonymity-scanner gate --criteria <criteria.json> --out-dir out/ --root .

# Adult 端到端（数据自备；脚本不联网）
PYTHON="py -3.12" bash examples/adult/run.sh
# → out/adult/gate.json + out/adult/gate.md；退出码 1（有违例）

# 发布（M6；推送与 tag 需用户确认）
git status && git ls-files | grep -Ei '\.(csv|data|names)$' || true
py -3.12 -m build
git tag -a v0.1.0 -m "v0.1.0"
git push origin main --follow-tags
gh release create v0.1.0 dist/*.tar.gz --title v0.1.0 --notes-file plan/RELEASE-M6.md

# 收尾顺序（硬约束）
# DoD 验证 → plan/00·05·06 + README 四处状态回写 → 写 plan/RELEASE-M6.md/WRAPUP → 布局门（RELEASE 必须 PASS）→ commit
```
