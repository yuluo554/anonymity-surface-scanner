# Anonymity Surface Scanner

> **k/l/t 公式是商品，没人回答「哪几列组合会让 k 崩塌」。**
>
> 本工具输入一张表 + 列角色声明，输出**最小 k**、**最小崩塌集**（再加一列 k 就跌破阈值）、
> 每处违例的**等价类键 + 计数 + 行号清单**（可手算复核），以及可挂 CI 的 gate 结论。
> 护城河在**搜索层**，不在公式层。

**纯本地 Python CLI**：零运行时依赖、无 GPU、无云、**安装后零网络调用**、**不需要任何真实敏感数据**。

---

## 它回答什么

| 现有工具 | 本工具 |
| --- | --- |
| arx / sdcMicro / pycanon 给你 k/l/t **数值**，QI 列表由你手填 | 在候选池上**搜索**「哪几列一起用会把 k 打穿」，并给出**最小崩塌集** |
| 报告只给一个总数，算不清怎么来的 | 每处违例给 **分组键 + 计数 + 行号**，可被第三方按报告复算 |
| 没有完整性声明 | 显式三态：`已穷尽` / `被预算截断` / `单调性不适用`，三者不合并 |
| 缺失值默默按某种默认处理 | 缺失策略**必须显式三选一**，不指定即报错 |

## 撞域切割（三行）

1. **不产检查单**：本工具不评制度与流程，不给"合规/不合规"结论。
2. **不读政策文本**：输入是数据行，不是条款。
3. **只输出可计算量**：数值、行号、列组合——每一条都能被人按输出重算一遍。

## 状态

| 里程碑 | 内容 | 状态 |
| --- | --- | --- |
| **M0** | 出题定稿 + 方法论装订 + 计划套件 + 可运行骨架（CLI 契约 / 确定性序列化 / 退出码映射 / CI） | ✅ 2026-10-20 |
| **M1** | 数据先行：植入已知违例的合成夹具 + 独立真值 + Adult 基线 | ✅ 2026-10-20 |
| **M2** | 等价类引擎：k / l / t、三种缺失策略、违例行号 | ✅ 2026-10-20 |
| **M3** | 组合攻击面搜索：反单调剪枝、最小崩塌集、三态完整性 | ⬜ |
| **M4** | 逐记录风险与三种攻击者口径 | ⬜ |
| **M5** | gate + 判据文件：JSON + 人读报告 + 退出码 | ⬜ |
| **M6** | 发布：tag + Release + 留档 | ⬜ |

> **当前进度：M0–M2 完成。** `scan` 已能算出真实结果：`<out-dir>/scan.json` 给出 k/l/t、类大小直方图、
> 违例三件套（分组键 + 计数 + 行号）与未裁决行，并按 `0/1/2` 返回退出码。
> 其余计算实现（`schema` / `search` / `risk` / `gate`）尚未落地——调用会明确返回 `MODULE_NOT_READY`
> 与退出码 `2`（fail-closed），**不会**用空结果冒充通过。M1 已交付：四组植入已知违例的合成夹具
> + **独立 oracle** 复算的真值 + `manifest.json`。

## 安装

```bash
git clone https://github.com/yuluo554/anonymity-surface-scanner.git
cd anonymity-surface-scanner
python -m pip install -e ".[dev]"
anonymity-scanner --version
```

Python ≥ 3.8。运行时零第三方依赖；`[dev]` 只装 `pytest`。

## 命令一览

```text
anonymity-scanner schema --table <f> --decl <f> --out-dir <d> [--root <d>]
anonymity-scanner scan   --table <f> --decl <f> --missing-policy <策略> --k <int> \
                         [--l <int>] [--t <float>] --out-dir <d>
anonymity-scanner search --table <f> --decl <f> --missing-policy <策略> --k <int> \
                         --budget <int> [--require-exhaustive] --out-dir <d>
anonymity-scanner risk   --table <f> --decl <f> --missing-policy <策略> \
                         --attacker <prosecutor|journalist|marketer> --out-dir <d>
anonymity-scanner gate   --criteria <f> --out-dir <d> [--root <d>]
```

`--missing-policy` 三选一，**无默认值**：`drop` / `single-column` / `separate-class`。

## 退出码

| 码 | 含义 |
| --- | --- |
| `0` | 通过：全部声明阈值满足，且完整性未被裁剪 |
| `1` | 有违例（fail-closed） |
| `2` | **无法裁决**：输入/判据无效、缺失策略未指定、结果被预算截断且要求穷尽 |

**硬规则**：任何"算不出来 / 没算完 / 输入有误"一律 `2`，绝不退化为 `0`。

## 可复算承诺

- 同一表 + 同一声明 + 同一策略 + 同一阈值 → **逐字节相同**的 JSON 与相同退出码。
- 报告**不含**时间戳、主机名、绝对路径（路径以 `--root` 相对化），可直接贴进 CI 日志。
- 每条违例可被第三方按「分组键 + 计数 + 行号」手工复算。

## 数值口径

k / l / t 的定义、QI 候选打分、缺失策略语义、剪枝与完整性三态、退出码、攻击者口径，
**全部单点定义在 [`data/README.md` §四](data/README.md)**。代码、文档、报告文案一律引用该节，不另立第二套。

## 开发

```bash
python -m pytest                        # 全量测试（无需安装，conftest 已把 src/ 放进路径）
py -3.12 tools/check_sprint_layout.py   # 布局门（方法论装订）
py -3.12 tools/verify_layout_gate.py    # 布局门的变异验证（10 组，必须全部变红）
py -3.12 tools/scaffold_selftest.py     # 口径单点自检（版本 / 依赖 / 退出码 / 序列化）

# 夹具（M1）：表不入库，真值与 manifest 入库
py -3.12 tools/gen_fixtures.py              # 全集生成（表 + 真值 + manifest）
py -3.12 tools/gen_fixtures.py --check      # 重生成并与入仓真值逐字节比对
py -3.12 tools/adult_baseline.py --table <adult.data>   # Adult 读入基线（只读本地，不代下载）
```

本仓库遵循 `ai-tool-project-sprint` 方法论：先计划（`plan/`）再实现，每个里程碑有交接单，
门必须能被变异验证打红。入口见 [`AGENTS.md`](AGENTS.md)。

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [`plan/00-README总览.md`](plan/00-README总览.md) | 索引 / 决策记录（含弃选项）/ 承诺-证据台账 / 里程碑 |
| [`plan/01-题目文档.md`](plan/01-题目文档.md) | 十段式题目定稿（需求证据、竞品矩阵、开源空白） |
| [`plan/02-架构与技术选型.md`](plan/02-架构与技术选型.md) | 分层 / 模块边界 / CLI 契约 / 确定性设计 |
| [`plan/03-模块详设.md`](plan/03-模块详设.md) | M1–M5 详设 + 既定口径 K1–K10 |
| [`plan/04-数据计划.md`](plan/04-数据计划.md) | 夹具清单 / 真值纪律 / 植入纪律 |
| [`plan/05-里程碑与发布.md`](plan/05-里程碑与发布.md) | 逐里程碑 DoD / 风险登记 / 发布路径 |
| [`plan/06-交付对标与决策.md`](plan/06-交付对标与决策.md) | 评分对标 / 未闭合项 |
| [`data/README.md`](data/README.md) | 依据查证三态 / 数据源 / **数值口径单点定义** |
| [`data/fixtures/README.md`](data/fixtures/README.md) | 合成夹具怎么用：目录 / 命令 / truth.json 结构 / 行号语义 |

## 隐私与数据

- 仓库**不收录**任何真实个人数据（`.gitignore` 排除 `*.csv` / `*.tsv` / `*.parquet` / UCI Adult 的 `*.data` / `*.names`）。
- 示例与夹具全部为**明显虚构的合成值**，由 `tools/gen_fixtures.py` 程序化产出（固定种子 + 自研 splitmix64）；
  表格本体不入库，入库的是**真值**（由不 import 生产模块的独立 oracle 复算）。
- UCI Adult 只作**演示规模基线**，脚本只读本地文件、**不代下载**（`data/README.md` §二）。
- 安装后从 `--help` 到报告生成**全程无出站请求**。

## 许可证

[MIT](LICENSE) © 2026 yuluo554
