# Adult 端到端演示（M5）

UCI Machine Learning Repository · Census Income（`adult.data`）上的 gate 演示。
**表不入库**（`.gitignore` 排除 `*.csv` / `*.data`），本目录只入库脚本、判据与实跑摘要。

## 1. 取得数据（用户自行下载；脚本不联网）

```bash
curl -sSL -o examples/adult/adult.data \
  https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data
```

实测基线（2026-10-20，与 `data/README.md` §二一致）：

| 项 | 值 |
| --- | --- |
| 字节数 | `3974305` |
| sha256 | `5b00264637dbfec36bdeaab5676b0b309ff9eb788d63554ca0a249491c86603d` |
| 行 × 列 | `32561 × 15`（原始件无表头，每行尾部带一个空字段） |

## 2. 一键运行

```bash
bash examples/adult/run.sh                       # 读 examples/adult/adult.data
PYTHON="py -3.12" bash examples/adult/run.sh     # 指定解释器（本机 `python` 是商店占位符）
OUT_DIR=out/adult-2 bash examples/adult/run.sh   # 换产物目录
```

脚本做两件事：

1. `prepare.py` 把 `adult.data` 转成 `adult.csv`（**不入库**）：
   丢弃行尾空字段、剥除值两侧空白、`?` 归一为空串（`tableio.missing_set()` 的缺失 token）。
2. `anonymity-scanner gate --criteria examples/adult/criteria.json --out-dir out/adult --root .`
   产出 `out/adult/gate.json` + `out/adult/gate.md`，退出码原样透出。

数据文件缺失时脚本以退出码 `3` 结束，并提示自行下载——**绝不代下载**。

## 3. 判据

`criteria.json`（判据闭合；改阈值只改这里）：

| 项 | 值 | 说明 |
| --- | --- | --- |
| `table` / `declaration` | `adult.csv` / `declaration.json` | 相对路径以**判据文件所在目录**为基准 |
| `missing_policy` | `drop` | 无默认值，必须显式 |
| `thresholds` | `k=5, l=null, t=null` | l/t 未启用 |
| `search` | `enabled=true, budget=256, require_exhaustive=true` | 候选池 = 声明的 3 个 QI 列；要求穷尽，被截断即退出码 `2` |

`declaration.json`：`age` / `education` / `sex` 为 QI，`income` 为 sensitive。
其余 11 列未声明 → 进 `unparticipating`（工具**不猜**角色）。

## 4. 实测结果

见 [`EXPECTED.md`](EXPECTED.md)。数字是**该判据下**的结果，不是 Adult 表的"绝对隐私水平"。
