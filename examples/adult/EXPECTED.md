# Adult 端到端实测摘要（M5 · 2026-10-20）

> **只写实测事实，不预写 k 值。** 数字是**该判据下**的结果（角色 / 缺失策略 / 阈值 / 预算），
> 不是 Adult 表的"绝对隐私水平"。全部由 `bash examples/adult/run.sh` 在本机实跑得到。

## 输入

| 项 | 值 |
| --- | --- |
| 文件 | `adult.data`（不进仓库；`prepare.py` 转为 `adult.csv`） |
| 字节数 / sha256 | `3974305` / `5b00264637dbfec36bdeaab5676b0b309ff9eb788d63554ca0a249491c86603d` |
| 行 × 列 | `32561 × 15`（与 `data/README.md` §二 的读入基线一致） |
| 判据 | `criteria.json`：`drop`，`k=5`，`l=null`，`t=null`，搜索 `budget=256` + `require_exhaustive=true` |
| 角色 | QI = `age`, `education`, `sex`；sensitive = `income` |

## 命令与退出码

```bash
PYTHON="py -3.12" bash examples/adult/run.sh
# anonymity-scanner gate --criteria examples/adult/criteria.json --out-dir out/adult --root .
```

| 项 | 实测 |
| --- | --- |
| 退出码 | **1**（有违例） |
| `outcome` | `violation` |
| `undefined_reason` | `null`（算得出来、且搜索已穷尽） |
| 产物 | `out/adult/gate.json` + `out/adult/gate.md` |

## 扫描结论（声明集合 = `age + education + sex`）

| 项 | 实测 |
| --- | --- |
| k | **1** |
| l（逐 sensitive 列取最小） | **1** |
| t（总变差距离，取最大） | **0.75919** |
| 等价类数 | **1703** |
| 违例 | **762 个等价类 / 1616 行**（每条含分组键 + 计数 + 行号） |
| 未裁决行（`drop`） | 0（三个 QI 列在本口径下无缺失） |

前三条违例（`gate.md` 第三节原样摘录）：

```text
| 1 | `age=17|education=5th-6th|sex=Male`   | 1 | 336 |
| 2 | `age=17|education=7th-8th|sex=Male`   | 3 | 9972, 17475, 28771 |
| 3 | `age=17|education=HS-grad|sex=Female` | 3 | 8318, 16841, 31960 |
```

## 组合搜索（候选池 = 声明的 3 个 QI 列）

| 项 | 实测 |
| --- | --- |
| 子集空间 | 7 |
| 已评估 / 剪枝 | **5 / 3** |
| 完整性 | **`exhausted`**（`require_exhaustive=true` 未被触发） |
| 空集 k（参与分组的行数） | 32561 |
| 声明集合的 k | 1 |
| **最小崩塌集（穷尽结果）** | **`[["education", "sex"]]`** |

解读：`age` 单列即不安全（k=1）；`education + sex` 是安全的最小组合（k=16，见分层曲线 `|S|=2`），
再没有任何一列可以加而不使 k 跌破 5——因此它是边界集。完整分层曲线与逐子集清单见 `gate.json`。

## 可复算性

- 同一输入连跑两次（`out/adult` 与 `out/adult-b`）→ `gate.json`、`gate.md` **逐字节相同**（本机 `cmp` 实测）。
- 产物不含时间戳、主机名、绝对路径；行号 = 数据行序号（1 起，不含表头）。
- `adult.csv` / `adult.data` **不入库**；`run.sh` 只读本地文件，脚本内无下载命令。
