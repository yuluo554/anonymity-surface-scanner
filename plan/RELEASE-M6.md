# RELEASE-M6 · v0.1.0 发布留档

> **两栏纪律**：§一 在 **tag 前**入库（只写 tag 前可复核的事实，**不含发布物 digest**）；
> §二 在 **tag 后**追加（tag 指向、sdist digest、Release、CI 首推、tag 后作用域）。
> 依据：`plan/05` §五「字面 digest 只写进 Release 正文或 tag 后提交」。

## 一、tag 前事实

### 1. 交付面

| 项 | 实测（2026-10-20，本机） |
| --- | --- |
| 待发布交付面 | `main` 快进到 M5 收尾提交 `0307260`（M0–M5 全 ✅） |
| 工作树 | `git status` 干净（本文件入库前的唯一新增即发布留档本身） |
| 入仓表格扫描 | `git ls-files` 中 `*.csv` / `*.data` / `*.names` = **0** |
| Adult 输入件 | `examples/adult/adult.data` 的 sha256 与 `data/README.md` §二 登记值**逐字符一致**（不在仓库内） |
| 版本单一来源 | `anonymity_scanner.__version__ = 0.1.0`；`pyproject` 走 `dynamic = ["version"]` |

### 2. 干净环境验证（`plan/05` §二 出口门第一条）

方法：`git archive HEAD` 导出到仓库外的临时目录 → 新建 venv → `pip install <tree>` →
**从导出目录之外**逐条执行 README 命令。

| 步骤 / 命令 | 实测 | 退出码 |
| --- | --- | --- |
| 导出树 | 60 个文件；`*.csv` / `*.data` = 0 | — |
| 建 venv + `pip install .` | 成功；`anonymity_scanner.__version__` = `0.1.0` | `0` |
| `anonymity-scanner --version` | `anonymity-scanner 0.1.0` | `0` |
| `schema` | 明确 `MODULE_NOT_READY`（M1 计算实现未落地，设计如此） | `2` |
| `scan`（tiny，`drop`，k=2） | `k=1 l=1 t=0.666667 classes=12 violations=12 → violation` | `1` |
| `search`（small，`single-column`，k=2，budget=64） | `pool=4 evaluated=6 pruned=10 completeness=exhausted sets=2` | `1` |
| `risk`（small，`prosecutor`） | `classes=54 flagged=49/60` | `1` |
| `gate`（small 判据，预算内） | `violations=49 → violation`；产物 `gate.json` + `gate.md` | `1` |
| gate 双跑 | `gate.json` / `gate.md` **逐字节一致**（`cmp`） | — |
| 产物路径扫描 | 无绝对路径 / 主机名 / 时间戳 | — |
| `bash examples/adult/run.sh`（干净树内、已装包） | `32561 × 15`；`violations=762`；`gate.json` / `gate.md` 与仓库留档**逐字节相同** | `1`（有违例，符合预期） |

> Adult 数据由本机既有副本临时放入导出树，仅用于验证；未进入任何入库路径。

### 3. 门与测试基线（tag 前）

| 项 | 实测 |
| --- | --- |
| `py -3.12 -m pytest` | **277 passed** |
| `py -3.8 -m pytest` | **277 passed** |
| 干净树（无表格）`pytest` | **205 passed + 72 skipped**（skip 均为缺表格的夹具用例，符合 `.gitignore` 纪律） |
| `tools/gen_fixtures.py --check`（干净树内） | 四组夹具真值**逐字节一致** |
| `tools/check_sprint_layout.py` | 全绿；此时 `LAYOUT.RELEASE` 为 `SKIP`（M6 尚未 ✅） |
| `tools/verify_layout_gate.py` | **10/10** 全部如期变红 |
| `tools/scaffold_selftest.py` | 全绿（版本 / 零依赖 / 子命令 / 退出码映射 / 序列化 / 缺失集合） |

### 4. 发布物内容纪律（tag 前声明）

- sdist **不含**任何 `*.csv` / `*.data` / `*.names`；只含 `src/`、`plan/`、`data/README.md`、`tools/`、元数据。
- Release 附件只挂 sdist；不挂 wheel（单平台构建的 wheel 会误导跨平台用户）。
- 发布正文写：命令示例、退出码表、Adult 实测摘要（**注明判据**）、sdist digest。
- tag 后只动非交付面：`POST_TAG_SCOPE` ⊆ `plan/ README AGENTS tests tools docs`；
  `DELIVERABLE_UNCHANGED` = `src/`、`pyproject.toml`、`MANIFEST.in` 零差异。

## 二、tag 后事实（tag 后追加）

> 本节在 tag 与首推完成后按实测追加；未发生的行保持「待首推验证」，不预写结论。

### 1. tag 指向

| 项 | 实测 |
| --- | --- |
| tag | `v0.1.0`（annotated，对象 `3349e6aa…bb67`） |
| tag 指向提交 | `eeda0cd9373387308ae97f7c3daa71dc8e673e0e`（`M6：发布留档（tag 前栏）`） |
| tagger | `yuluo554 <282769740+yuluo554@users.noreply.github.com>` |
| 远端 | `https://github.com/yuluo554/anonymity-surface-scanner`（PUBLIC，默认分支 `main`） |
| `main` 与 tag 的关系 | `main` 已快进到同一提交；`refs/heads/main` = `eeda0cd` |

> 首推时 `main` 曾停在 M1（`200c1c5`）：`git archive` 前的分支切换因本机 `python` 为商店占位符未生效。
> 已用 `git merge --ff-only` 快进（**非强推**）后重新推送，tag 未移动。

### 2. sdist 与 Release

| 项 | 实测 |
| --- | --- |
| 构建方式 | 从 `git archive v0.1.0` 导出树内 `py -3.12 -m build --sdist` |
| 附件 | `anonymity_scanner-0.1.0.tar.gz`（`155783` 字节） |
| sha256 | `e5f3dbc0c238e79b6d68bdafea221551b78bc65b18fcd448cf5ec59cd307e47b` |
| GitHub 侧 digest | `sha256:e5f3dbc0c238e79b6d68bdafea221551b78bc65b18fcd448cf5ec59cd307e47b`（一致） |
| 回下载核对 | `gh release download v0.1.0` → `sha256sum -c` → **OK** |
| 与 tag 构建件比对 | 解包后 `diff -r` 内容一致（归档时间戳差异不影响内容） |
| 解包自足 | 解包 → venv → `pip install <tar.gz>` → `--version` = `0.1.0`；从解包目录**之外**跑 `scan` → 退出码 `1`、产出 `scan.json` |
| 包内容 | `src/` `plan/` `data/README.md` `tools/` `tests/` + 元数据；**无** `*.csv` / `*.data` / `*.names` |
| Release | <https://github.com/yuluo554/anonymity-surface-scanner/releases/tag/v0.1.0>（非 draft、非 prerelease） |

> **sdist 不可逐字节重建**：setuptools 写入归档成员的 mtime，两次构建的 tar.gz 字节不同（解包内容一致）。
> 因此本留档只承诺"回下载件 = 已发布件"（`sha256sum -c` + GitHub 侧 digest 双证），
> 不承诺"任意时刻重建得到同一字节"。设 `SOURCE_DATE_EPOCH` 亦未消除该差异（实测）。

### 3. CI 首推对账

| 项 | 实测 |
| --- | --- |
| 对账不变式 | 每个 push 到 `main` / `v*` 的事件各产生一条 run，且该 run 的 `head_sha` = 该事件 sha |
| sha 台账 | `eeda0cd`（tag 与发布提交）→ run `39436441311` success；tag `v0.1.0` → run `39436117872` success；`8f4f895`（收尾）→ `39437106544` success；`275a507` → `39437349233` success；`111b230` → `39437685335` success |
| 台账快照纪律 | 台账为**快照式**：登记到 `111b230` 为止；其后纯文档提交不再追加（否则每改一次台账就多一个 sha，追不完）。判断"是否仍绿"看 GitHub 上该 sha 的 run，不看本表行数 |
| 矩阵 | 每个 run 4 个 job：`py3.8 · ubuntu-22.04` / `py3.8 · windows-latest` / `py3.12 · ubuntu-22.04` / `py3.12 · windows-latest`，**全部 success** |
| 步骤 | 布局门 → 变异验证（10/10）→ selftest → `pytest` → `anonymity-scanner --version` |
| 结论 | 首推即绿，无修复轮次；3.9–3.11 仍不作承诺 |

> 另有一次 `200c1c5`（快进前停在 M1 的旧 `main`）触发的 run `39436118278` 亦为 success；
> 它不代表发布提交，只作"CI 本身可用"的旁证。

### 4. tag 后作用域

| 项 | 实测 |
| --- | --- |
| `POST_TAG_SCOPE` | `plan/`（`00` `05` `06` `RELEASE-M6`）、`README.md`（实测 `git diff --name-only v0.1.0..HEAD` 只含这 5 个文件） |
| `DELIVERABLE_UNCHANGED` | `git diff --stat v0.1.0 -- src pyproject.toml MANIFEST.in` → **空**（零差异） |
| 表格入库 | 复查 `git ls-files` 中 `*.csv` / `*.data` / `*.names` = 0 |

## 覆盖对账

> 三态口径：**实现** = 已完成并有可复跑证据；**不适用** = 本项目明确不做（给理由）；
> **待首推验证** = 有路径、未取得外部证据，不作论据。

| `plan/05` §二 出口门 | 本项目的判据 | 三态 |
| --- | --- | --- |
| 干净环境验证 | `git archive` → venv → `pip install .` → README 命令逐条（§一.2 全表） | 实现 |
| 发布物本体 | `gh release download` 回下载 → `sha256sum -c` → 与 tag 重打包 `cmp` | 待首推验证 |
| 源码包自足 | sdist 解包 → 装 → 从解包目录之外跑 CLI | 待首推验证 |
| tag 后只动非交付面 | `POST_TAG_SCOPE` ⊆ `plan/ README AGENTS tests tools docs`；`DELIVERABLE_UNCHANGED` 零差异 | 待首推验证 |
| CI 对账 | 每次 push 事件 ↔ 一条 run（sha 台账，不写会自追的总数） | 待首推验证 |
| 门自变 | 留档入库后重跑布局门与变异验证（10/10），结果作为 tag 时点基线 | 实现 |
| PyPI 发布 | 本题发布形态 = GitHub 公开仓 + tag + Release；不发布 PyPI 包 | 不适用 |
| 多平台 wheel | 单平台构建的 wheel 会误导跨平台用户；只挂 sdist | 不适用 |
| 3.9 / 3.10 / 3.11 行为 | 不作承诺；CI 矩阵只覆盖下界（3.8）与当代（3.12） | 不适用 |

**覆盖对账结论**：六条出口门全部有归宿；tag 前两条已实现、其余在 tag 后逐条补实测。

---

## 三、v0.1.1（M6.1 二次迭代，2026-10-23）

> 触发：`v0.1.0` 的 Release 附件（sdist）**跑不了它自带的测试** —— 解包后
> `py -3.12 -m pytest` → **102 failed / 171 passed / exit 1**。
> 本节只记 v0.1.1 的修复与实测；`v0.1.0` 的 tag 与 Release **原样保留**（不移动、不删附件）。

### 1. 修了什么（逐条）

| 编号 | 缺陷 | 修法 | 证据 |
| --- | --- | --- | --- |
| **D1** | sdist 缺 `tests/conftest.py`、`data/fixtures/**`、`examples/adult/*` → 自带 pytest 102 failed | `MANIFEST.in` **追加**三行：`recursive-include tests *.py` / `recursive-include data/fixtures *.json *.md` / `recursive-include examples *.py *.json *.md *.sh` | sdist 解包树 → `pytest` **exit 0**；`gen_fixtures.py --check` → 逐字节一致 |
| **D1 反向红线** | 写成 `recursive-include examples *` 会把 3.4 MB `adult.csv` 打进包 | 只列后缀；新增 `tests/test_packaging.py`（4 项）断言三条规则存在且**任何 `recursive-include` 都不得用裸 `*`**（负控：改成裸 `*` 即 3 项红） | 包内 `*.csv`/`*.data`/`*.names` = 0（`tar tzf | grep` 无命中） |
| **D2** | tag 树的 README 自述「M0–M5 完成、M6 未发布」 | 文档已在 `v0.1.0` 之后回填；**本次只把新 tag 打在 HEAD** | 布局门 `LAYOUT.RELEASE` = PASS（两栏 / 覆盖对账 / 三态行 10） |
| **D3** | 预算截断时 `empty_set_witness=true` 印出可证伪结论 | `m3_search` 增加证据前提：**每个单列扩展都实算过**才允许 `true`；`m5_gate` 对「空集在列但证据不足」改印「预算不足，无法判定」 | `budget=1` 实测 `witness=False / sets=[[]] / completeness=budget-truncated`；穷尽路径 `witness=False / sets=[["education","sex"]]` 不变 |
| **D8** | 「安装后零网络」AST 守门只覆盖 2 个文件 | 扩到产品包 9 个模块 + 「清单 ↔ 盘上文件」互校 | 负控：往 `m4_risk.py` 插 `import urllib.request` → 该项立刻红 |
| **D6** | 自述测试数 277 硬编码 4 处、无守门 | 新增 `tests/test_doc_counts.py`：四处副本须一致，且等于 `pytest --collect-only` 实收集数 | 改文档数字 → 门红（实测：库里写 277、实际收集 295 时报「295」） |
| **DEC2** | floor `>=3.8`（已 EOL）与 SPDX license 互斥 | `requires-python = ">=3.12"`、`build-system.requires = ["setuptools>=77"]`、`license = "MIT"` + `license-files = ["LICENSE"]`、删 `License::` classifier | `PKG-INFO`：`License-Expression: MIT` + `Requires-Python: >=3.12`；构建输出**无** License deprecation warning |
| **D5/上游** | CI 用 `checkout@v4` / `setup-python@v5`（Node20 弃用注解） | 升 `checkout@v7` / `setup-python@v7`；加 `permissions: contents: read` 与 `concurrency`；矩阵 `{ubuntu-22.04, windows-latest} × 3.12` | 见 §三.4（待 CI 实跑确认） |
| **新增 CI job** | 发布物"坏"这件事本地没门能抓 | `packaging` job：build sdist → 无表格扫描 → 解包跑自带 pytest → 真值自检 → 布局门 | 见 §三.4 |

### 2. sdist 自足性口径（本节是这条口径的**单点定义**）

> **sdist 解包树的正确基线是「干净树基线」，不是开发树基线。**
> 因为 `.gitignore` 排除全部表格（`.csv` / `.tsv` / UCI 的 `.data` / `.names`），
> 依赖表格的夹具用例在 sdist 里必然 skip —— 写成一个"等于开发树全量数"的承诺，
> 会让人以为没修好。

| 树 | 收集数 | `py -3.12 -m pytest` 实测 |
| --- | --- | --- |
| 开发树（本机，有表格）—— 当前全量测试 295 项 | **295** | **295 passed**，exit 0 |
| sdist 解包树（无表格，只用装了 `pytest` 的 venv，**不装包**） | **295** | **222 passed + 73 skipped**，exit 0 |
| `git archive HEAD` 干净树（无表格） | **295** | 同 sdist 口径（222 passed + 73 skipped） |

两处 skip 的构成：4 组夹具的表格用例（需要 `table.csv`）+ 依赖真值但表格缺失的 CLI 对照用例；
`test_doc_counts.py::test_declared_test_count_equals_collected_count` 在缺表格时**如实 skip**，
不用一个能过但什么都没证明的断言充数。

### 3. 交付面与版本

| 项 | v0.1.1 实测 |
| --- | --- |
| 版本单一来源 | `anonymity_scanner.__version__ = "0.1.1"`；`pyproject` 仍走 `dynamic = ["version"]` |
| `anonymity-scanner --version` | `anonymity-scanner 0.1.1` |
| 表格入库 | `git ls-files` 中 `*.csv` / `*.data` / `*.names` = **0** |
| Adult 端到端 | `bash examples/adult/run.sh` → exit **1**；`k=1`、`1703` 类、`762` 条违例；搜索 `exhausted`、最小崩塌集 `[["education","sex"]]`、`empty_set_witness=false`（**与 v0.1.0 逐项相同**） |
| 门 | 布局门全绿（`LAYOUT.RELEASE` PASS 两栏:True 覆盖对账:True 三态行:10）；变异验证 10/10；`scaffold_selftest` 9 项全 PASS（`VERSION.FORMAT = 0.1.1`）；`gen_fixtures --check` 逐字节一致 |

### 4. tag、Release 与三方 digest

> **本节只写不变量与方法，不写本版附件的字面摘要。** 原因：本文件随 sdist 一起发布，
> 在文件里写"本包自己的 sha256"必然自相矛盾（写死的值一旦重打包就假）。字面摘要落在
> **Release 正文 / tag 消息 / `SHA256SUMS` 附件**三处，三处必须同值。

| 项 | v0.1.1 |
| --- | --- |
| tag | `v0.1.1`（annotated）；指向见 `git rev-parse v0.1.1^{commit}`（tag 消息里记了提交与摘要） |
| Release | <https://github.com/yuluo554/anonymity-surface-scanner/releases/tag/v0.1.1>（非 draft、非 prerelease、`latest`） |
| 附件 | `anonymity_scanner-0.1.1.tar.gz`（sdist）+ `SHA256SUMS` |
| 三方对撞方法 | ① `git archive <tag>` → `python -m build --sdist`；② `gh release download <tag>`；③ `gh api …/releases/tags/<tag>` 的 `assets[].digest`。**① 与 ②③ 必须逐字符相同** |
| `SHA256SUMS` 格式 | 两个空格 + 单 LF（无 `*`）。`sha256sum` 默认的 `*` 形式在 Windows CRLF 下会与 `sha256sum -c` 互相绊倒 |
| 回下载件自证 | 解包 → **只装 `pytest`** 的新 venv（不装包）→ `pytest` 必须 exit `0` |
| 包内表格 | `tar tzf | grep -E '\.csv|\.data$|\.names'` 必须无命中 |

**本轮实测结果（2026-10-23，执行时点）**：三方 digest **逐字符相同**且与重建件**逐字节 `cmp` 一致**；
`sha256sum -c SHA256SUMS` = OK；回下载件跑它自带测试 = **222 passed, 73 skipped / exit 0**；
包内表格 0；包条目 83。字面值见该 tag 的 Release 正文与 tag 消息。

**最终发布形态（tag 重指后）**：

| 项 | 值 |
| --- | --- |
| tag | `v0.1.1` → `65b3d86`（annotated 对象 `c983ef2`） |
| 附件 | `anonymity_scanner-0.1.1.tar.gz`（`238289` B）+ `SHA256SUMS`（`97` B） |
| 重建件 / 回下载件 / GitHub 侧 digest | 三者逐字符相同，`cmp` 逐字节相同 |

### 5. CI 实测（本版共 4 轮，各 3 job 全绿）

| run | 事件 | head | 结论 |
| --- | --- | --- | --- |
| `39897683566` | push → `main` | `4e1764c` | success（3 job） |
| `39897787880` | push → tag `v0.1.1`（首次指向） | `4e1764c` | success（3 job） |
| `39898099955` | push → `main`（tag 后回填） | `caca6a4` | success（3 job） |
| `39899133299` | push → tag `v0.1.1`（重指后） | `65b3d86` | success（3 job） |
| `39899154497` | push → `main`（RELEASE 去循环） | `65b3d86` | success（3 job） |

check-run 注解数：**0**（逐条 `gh api …/check-runs/<id>/annotations` 汇总；6 条 check-run 全 0）。
三个 job = `py3.12 · ubuntu-22.04` / `py3.12 · windows-latest` /
`sdist self-contained · py3.12`。`packaging` job 的六步（build sdist → 无表格扫描 →
解包跑自带 pytest → 真值自检 → 布局门）全部 `✓`。


### 6. 已知边界（v0.1.1 结束时点）

- **`v0.1.1` 的 tag 曾从 `4e1764c` 重指到其后一个纯文档提交**：`4e1764c` 的 README 写「v0.1.1 待发布」，
  而那棵树就是发布物 —— 与诊断 D2 给 `v0.1.0` 定 P1 的判据同形。处置 = 把 tag 移到"已回填 ✅"的提交
  （`POST_TAG_SCOPE` 只含 `README.md` / `plan/00` / `plan/05` / `plan/RELEASE-M6.md`，
  `DELIVERABLE_UNCHANGED` = `src/` `pyproject.toml` `MANIFEST.in` `.github/` `tests/` 零差异），
  并按 §三.4 的方法重打附件。`v0.1.0` 的 tag 与 Release 未动。
- `plan/05` §「发布路径」里仍写 `v0.1.0` 的具体命令；它记录的是 M6 当轮路径，不逐个版本复制。
- `v0.1.0` 的坏 sdist **保留在架**（DEC1-A）；其 Release 正文未加"已知问题"提示 —— 由本项目
  的 README 与 v0.1.1 正文承担指引，不改写上一版发布正文。




