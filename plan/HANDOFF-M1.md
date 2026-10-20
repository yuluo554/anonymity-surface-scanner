# HANDOFF-M1 · 第 1 棒启动包（数据先行）

> **用法**：新对话第一件事 = 跑 `py -3.12 tools/check_sprint_layout.py`（闸门在 `AGENTS.md`）。
> 本文件由 M0 棒收尾时写，是 M1 的**唯一启动上下文**；`plan/` 里的计划文件是背景，本文件是现状。
> 交付里程碑：**M1 = 数据先行**（夹具生成器 + 植入已知违例的合成表 + 独立真值 + Adult 基线）。

## 一、当前进度与证据

| 项 | 状态 | 证据（可复跑） |
| --- | --- | --- |
| 方法论装订（AGENTS.md + 布局门 + `plan/00` 装订行） | ✅ | `py -3.12 tools/check_sprint_layout.py` → 全绿（`LAYOUT.RELEASE` 为 SKIP，M6 未完成） |
| 布局门变异验证 10 组 | ✅ | `py -3.12 tools/verify_layout_gate.py` → 10/10 如期变红 |
| 计划套件 `plan/00`–`06` + `data/README.md` | ✅ | 布局门 `LAYOUT.FILES` / `LAYOUT.SECTIONS` |
| 可运行骨架（CLI 契约 / 序列化 / 退出码映射） | ✅ | `anonymity-scanner --version` → `0.1.0`；双解释器 80 项测试全绿；无 `.git` 解包树同样 80 项全绿 |
| 计算实现 M1–M5 | ⬜ | 五条子命令当前返回 `MODULE_NOT_READY` + 退出码 `2`（**设计如此**，不是缺陷） |

**本轮实测命令与输出摘要**（2026-10-20，本机）：

```text
py -3.12 -m pip install -e ".[dev]"      → anonymity-scanner-0.1.0 (editable)
anonymity-scanner --version              → anonymity-scanner 0.1.0  (rc=0)
py -3.12 tools/check_sprint_layout.py    → 12 份文件 / 4 处状态副本 / 3 个 tools 引用；全绿
py -3.12 tools/verify_layout_gate.py     → 10/10 全部如期变红
py -3.12 tools/scaffold_selftest.py      → 8 项口径自检全绿
py -3.12 -m pytest                       → 全绿（见 §六 的命令速查复跑）
```

## 二、当前事实 · 状态不变量（下一棒动手前必须知道）

1. **五条子命令的"未实现"是刻意设计**：`schema/scan/search/risk/gate` 全部**先完成输入校验**再抛
   `ModuleNotReady`，退出码 `2`。实现模块时替换的是**最后那一步**（`raise ModuleNotReady`），
   **不要**动前面的校验顺序——契约测试（`tests/test_contract.py`）逐条钉住了它们。
2. **退出码映射只有一处**：`exit_codes.map_outcome()`。新增任何"结论 → 退出码"的分支都必须改这个函数，
   并在 `tests/test_contract.py` 里补断言；在 CLI 里另写 `return 1` 会让 `EXIT.SINGLE_MAP` 语义失效。
3. **序列化只有一处**：`canonical.dumps()` / `write_json()`。任何产物落盘都走它——这是"双跑逐字节一致"
   的唯一支点。`round6()` 用 `Decimal(str(x))`，**不要**改成 `Decimal(x)`（会带进二进制尾差）。
4. **缺失值集合只有一处**：`tableio.missing_set()`（`("", "NA", "N/A", "null", "NULL", "-")`，大小写敏感）。
   缺失策略本身**没有默认值**，`declaration.require_missing_policy()` 是唯一入口。
5. **行号 = 数据行序号，1 起，不含表头**，且**完全空行不占行号**（`tableio.read_table` 已实现，有测试）。
   M1 生成夹具时必须按这个语义写真值里的 `row_numbers`，否则 M2 的违例行号会整段错位。
6. **`plan/00`–`06` 与 `README.md` 的里程碑状态四处副本必须一致**（布局门 `LAYOUT.STATUS` 逐副本采集，
   不以任何单一副本为真值）。M1 收尾时**四处一起改**，漏一处即红。
7. **`plan/06` 缺口表**：关闭 G1/G3 时**只描述、不点名 `.md` 文件名**（门会剥掉行内代码与 `*.md`
   形态，但点文件名仍是最容易踩的形态）。
8. **文档里不许出现未实现的 `tools/*.py` 路径**：`LAYOUT.DOC_TOOLS` 会逐个断言存在。
   M1 落地生成器后**才**把路径回填进 `plan/04 §六`（回填时同步跑门）。
9. **`.gitignore` 已排除 `*.csv` / `*.tsv` / `*.parquet`**：夹具表格因此**不会入库**，入仓的是
   `data/fixtures/*/truth.json` 与 `manifest.json`。生成器的 `--check` 必须能在"表格不存在"的干净
   clone 里重生成并比对——这是 M1 的 DoD 之一。

## 三、下一棒待办（M1）

- [ ] 写夹具生成器：固定种子、自研确定性随机（禁 `random` 模块的跨版本序列）、产出 tiny/small/prune/budget 四组。
- [ ] 写**独立 oracle**：从已生成的行用朴素实现复算 `truth.json` 的期望值；与被测实现互不 import（AST 守门）。
- [ ] `truth.json` 结构照 `plan/04 §二`；只存输入与期望，**不得出现 `observed_*` 字段**。
- [ ] `manifest.json`：生成器 sha256 + 每份真值 sha256 + 种子 + 参数；`--check` 重生成到临时目录后逐字节比对。
- [ ] 局部生成（`--only`）**不得改写全集清单**（写盘条件要把"部分运行"这一维也列进去，并配一条测试）。
- [ ] UCI Adult 读入基线：只读本地文件、不代下载；报告行数与列数；不入库。
- [ ] 回填 `plan/04 §六` 的真实命令与路径（并跑布局门）。
- [ ] 收尾：四处状态副本改 ✅ → 写 `plan/HANDOFF-M2.md`（七节）→ commit。

## 四、既定口径清单（K 编号，动了会打挂测试）

| K | 口径 | 唯一位置 | 改动后果 |
| --- | --- | --- | --- |
| K1 | k/l/t 与 QI 打分公式 | `data/README.md` §4.2–4.3；实现 `m1_candidates` / `m2_classes`（M1/M2 落地） | 全部数值断言失效 |
| K2 | 退出码映射单点 | `exit_codes.map_outcome` | `tests/test_contract.py` 整组红 |
| K3 | 序列化冻结参数 | `canonical.dumps` | `tests/test_determinism.py` 逐字节断言红 |
| K4 | 缺失值集合 | `tableio.missing_set` | 三策略用例与真值全部偏一格 |
| K5 | 完整性三态闭合互斥 | `data/README.md` §4.5；`m3_search.completeness`（M3 落地） | M3 的"不得冒充穷尽"断言失效 |
| K6 | 行号语义（1 起、不含表头、空行不占号） | `tableio.read_table` | 真值里的 `row_numbers` 全错位 |
| K7 | 报告无时间戳/主机名/绝对路径 | `canonical.relativize` + 序列化单点 | `test_output_has_no_timestamp_hostname_or_abs_path` 红 |
| K8 | 计算层禁 import CLI、禁读时钟/随机 | `plan/03 §K` | 确定性承诺失效 |
| K9 | 版本号单一来源 | `__init__.__version__`（`pyproject` 用 dynamic attr） | `tools/scaffold_selftest.py` 的 `VERSION.SINGLE_SOURCE` 红 |
| K10 | 真值由生成器独立 oracle 写出，不 import 生产模块 | `plan/04 §二` | 真值变成"自证"，基准永久全绿 |

## 五、本机环境坑（只写实测过的）

- **`python` 是商店占位符**：本机一律 `py -3.12 ...` 或 `py -3.8 ...`。`py -0p` 实测两条通道：
  3.8.8（pytest 7.4.4）/ 3.12.10（pytest 8.4.2）。
- **`py -X utf8` 只救"我们敲的命令"**：CI 与子进程编码是另一条通路。项目里已有
  `cli._ensure_utf8_stdio()` 做用户侧兜底；CI 里另设 `PYTHONUTF8=1`（`.github/workflows/ci.yml`）。
- **venv 在 Git Bash 下**用 `./.venv/Scripts/python.exe` 相对形式（不要写绝对盘符路径）。
- **跨盘符 `relpath` 抛 ValueError**（C: → D:）：已在 `canonical.relativize` 里 try/except 回落文件名，
  新增路径展示一律复用它，不要直接 `os.path.relpath`。
- **安装时如遇 pip 代理污染**：`NO_PROXY="*" no_proxy="*" py -m pip install -e ".[dev]" --no-index --no-build-isolation`
  （本项目零运行时依赖，离线可装）。
- **干净 clone 里没有 `.git` 之外的东西**：`tests/conftest.py` 已把 `src/` 注入 `sys.path`，
  所以**未安装也能跑 pytest**——这是发布包（tarball）验证的通路，别删。

## 六、DoD 逐项 checklist（M1）

- [ ] 生成器全集运行一次 → 四组夹具真值落盘
- [ ] `--check` 重生成逐字节一致（在**干净目录**里也成立）
- [ ] 独立 oracle 复算的期望值 == 生成器写入的期望值
- [ ] `truth.json` 无 `observed_*` 字段（扫描断言）
- [ ] 局部生成不改写 `manifest.json`（专项测试）
- [ ] Adult 读入基线跑通（只读本地，不联网）
- [ ] `plan/04 §六` 回填真实路径/命令，布局门 `LAYOUT.DOC_TOOLS` 绿
- [ ] 四处状态副本改 ✅ 后布局门绿
- [ ] 双通道（3.8 / 3.12）全量 pytest 绿
- [ ] `plan/HANDOFF-M2.md` 落盘（七节齐）

## 七、关键命令速查

```bash
# 环境
py -3.12 -m pip install -e ".[dev]"
py -3.12 -m pytest
py -3.8  -m pytest

# 门（顺序固定：先布局门，再变异验证）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/verify_layout_gate.py
py -3.12 tools/scaffold_selftest.py

# CLI 契约冒烟（当前应全部 rc=2 且报 MODULE_NOT_READY，除 --version）
anonymity-scanner --version
anonymity-scanner schema --table <f.csv> --decl <d.json> --out-dir out/

# 收尾顺序（硬约束）
# DoD 验证 → plan/00·05·06 + README 四处状态回写 → 写 HANDOFF-M2 → commit
```
