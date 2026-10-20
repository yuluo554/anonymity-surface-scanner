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
| 首次 push | `main` → `eeda0cd`；tag `v0.1.0` → `eeda0cd`（两个 push 事件） |
| run（`main`） | `39436441311` · success · <https://github.com/yuluo554/anonymity-surface-scanner/actions/runs/39436441311> |
| run（tag） | `39436117872` · success · <https://github.com/yuluo554/anonymity-surface-scanner/actions/runs/39436117872> |
| run（收尾提交 `8f4f895`） | `39437106544` · success · <https://github.com/yuluo554/anonymity-surface-scanner/actions/runs/39437106544> |
| 矩阵 | 每个 run 4 个 job：`py3.8 · ubuntu-22.04` / `py3.8 · windows-latest` / `py3.12 · ubuntu-22.04` / `py3.12 · windows-latest`，**全部 success** |
| 步骤 | 布局门 → 变异验证（10/10）→ selftest → `pytest` → `anonymity-scanner --version` |
| 结论 | 首推即绿，无修复轮次；3.9–3.11 仍不作承诺 |

> 另有一次 `200c1c5`（M1 时点的 `main`）触发的 run `39436118278` 亦为 success——那是快进前的旧 `main`，
> 不代表发布提交；发布提交的对账以上表两个 run 为准。

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
