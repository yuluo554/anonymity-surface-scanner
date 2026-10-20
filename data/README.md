# data/README.md — 依据查证、数据源与数值口径

> 本文件是本题的**查证台账**与**数值口径唯一出处**。
> `plan/01`、代码注记、CLI 输出文案、README 一律引用本文件 **§四**，不得另立第二套口径。
> **基准日：2026-10-20**。所有星数 / fork / 日期 / 下载量为该日快照；后续变化以当日页面为准。

## 一、依据查证记录（三态）

三态定义：**✅ 已核对**（有可直连来源，附渠道）／**⬜ 软论据**（检索快照或推断，可回溯但未逐条取证，**不得写成绝对结论**）／**❌ 未取得**（不得作论据）。

### 1.1 ⚠️ 数据来源口径说明（必须如实标注）

**Reddit 直连超时、pullpush 限流，故本项目的需求证据全部来自 GitHub issue 与 Hacker News；没有任何 Reddit 原话。** 任何文档、README、Release 说明、issue 回复中**不得**出现"Reddit 上有人说…"这类转述——没有原话就没有引用权。若后续补到 Reddit 原话，须新增一节并标注取得渠道与日期，不改写本节。

### 1.2 需求侧原话（✅ 原话可回溯）

| # | 来源 | 原话（照抄，不改写） | 链接 |
| --- | --- | --- | --- |
| N1 | OpenSAFELY cohort-extractor **#126**（2020-05-26 开，**至今 open、0 评论**） | "It would be helpful to understand disclosure risk for tier 3 data… know that an individual is a member of the dataset (membership disclosure)… **Identify a suitable set of quasi-identifiers**… Plot the distribution of k… and include a count of how many classes/patients breach a given privacy threshold. Low k is bad." | https://github.com/opensafely-core/cohort-extractor/issues/126 |
| N2 | sdcMicro **#354** | "kAnon (k = 3) makes 3 suppressions, while **1 suppression would have been enough**" | https://github.com/sdcTools/sdcMicro/issues/354 |
| N3 | sdcMicro **#349** | "Maartje Boer mentioned **to speed up kAnon** by parallelization" | https://github.com/sdcTools/sdcMicro/issues/349 |
| N4 | sdcMicro **#350** | "what is and how it is computed rk" | https://github.com/sdcTools/sdcMicro/issues/350 |
| N5 | sdcMicro **#356** | "I tried my best to read through SUDA2.h code and find out how these values of contribution can be calculated by hand **but nothing seems to be working**" | https://github.com/sdcTools/sdcMicro/issues/356 |
| N6 | HN **39484777**（2024-02-23） | "most 'anonymized' data is **a few additional data points away from being re-identified**" | https://news.ycombinator.com/item?id=39484777 |
| N7 | HN **29736185**（2021-12-30） | "All anonymisation algorithms… have at least one parameter that states to what degree the data has been anonymised. **This parameter should not be kept secret**" | https://news.ycombinator.com/item?id=29736185 |

- N1 的 issue 状态（open、0 评论）为基准日快照；**"至今 open"只到基准日**。
- 引文只作"存在这个诉求"的证据，**不推断诉求规模**。

### 1.3 竞品能力矩阵（✅ 实测，基准日 2026-10-20）

| 项目 | 规模 / 最近活动 | 覆盖能力 | 缺口 |
| --- | --- | --- | --- |
| arx（arx-deidentifier/arx） | **738★ / 237 fork**，2025-10-01 | k/l/t/δ-presence、(ε,δ)-DP、泛化/抑制、风险分析 | **Java 桌面 GUI 为中心，无 CLI 流水线契约**；#469 升 Java 21 仍开、#449 用户找不到随机串替换 |
| sdcMicro | **95★**，2026-09-10 | kAnon / ldiv / tcloseness / SUDA2 / record swapping + Shiny | R 生态；#349 慢、#354 过度抑制、#363 缺失值下 l 值算错、#366 文档与实现不一致 |
| SDV | **3580★**，2026-10-19 | 表格合成数据 | 不给形式化隐私保证（#779 DP 参数 2022 开到现在） |
| faker | **19449★** | 造假数据 | 无度量 |
| IBM diffprivlib | **919★** | DP 机制库 | 无表格层 QI 组合分析 |
| OpenDP | **444★** | DP 机制库 | 同上 |
| anonymeter | **110★**，2026-07-23 | 只评**合成数据**的三类攻击 | 不评原始发布表 |
| pycanon | **54★**，2026-09-21 | k/l/(α,k)/β/δ/t 数值计算 | QI 列表由用户给，不搜索组合，无门禁 |
| piiscope（barissozudogru） | **2★**，2026-10-11 | PII 检测 + k/l/t + SARIF + `--fail-on` | QI 靠列名关键词猜（源码 `_QI_NAME_HINTS` 硬编码 age/zip/sex…），无组合搜索，PyPI 月下载仅 **58** |
| SDMetrics | **264★** | 合成数据质量度量 | 测量层已占位 |
| SACRO-ML | **42★** | 安全研究工具 | 不提供发布前组合面扫描 |
| prv_accountant | **78★**（2024-02 停更） | ε 账本 | 组合数学商品化且停更 |

**判定（⬜ 软论据）**：公式层已商品化；未被占的是 **(a) QI 组合搜索与最小崩塌集**、**(b) 跨流程 ε 账本与 fail-closed 门禁**、**(c) 声明阈值 vs 实测值的可复算证书**。这是由能力矩阵反推的空隙，不是用户原话的直接诉求。

### 1.4 开源空白（`gh api`，基准日 2026-10-20）

| 检索式 | `total_count` | 头部仓库 | 三态 |
| --- | --- | --- | --- |
| `quasi identifier discovery` | **0** | — | ⬜ 软论据 |
| `minimal quasi-identifier` | **0** | — | ⬜ 软论据 |
| `k-anonymity violation` | **0** | — | ⬜ 软论据 |
| `attribute combination re-identification scan` | **0** | — | ⬜ 软论据 |
| `anonymization linter` | **0** | — | ⬜ 软论据 |
| `quasi identifier` | 42 | 最高 7★ | ✅ 已核对 |
| `k-anonymity l-diversity t-closeness` | 34 | arx **738★** | ✅ 已核对 |
| `k-anonymity CLI` | 88 | pycanon **54★** | ✅ 已核对 |
| `"k-anonymity" language:python` | 420 | Mondrian **177★** | ✅ 已核对 |
| `statistical disclosure control` | 44 | synthpop **60★** | ✅ 已核对 |
| `re-identification risk` | 64 | arx **738★** | ✅ 已核对 |
| `privacy risk quantification` | 19 | anonymeter **110★** | ✅ 已核对 |

**⚠️ 关键词污染提示（单独检索不可用）**：

| 检索式 | `total_count` | 头部仓库 | 说明 |
| --- | --- | --- | --- |
| `privacy metrics` | 510 | DNS 黑名单项目 **27552★** | 与本域无关，**不得作空白或竞品证据** |
| `privacy budget accounting` | 91 | 记账 / 财务类 App | 同上 |
| `privacy gate` | 1050 | AI 网关 **3065★** | 同上 |

这三个词的检索结果被其他语义域占满；任何文档引用它们作为"竞品多 / 空白"的证据都属误用。

### 1.5 PyPI 月下载旁证（✅ 基准日快照）

sdv **53,772** ／ sdmetrics **71,380** ／ opendp **36,323** ／ diffprivlib **10,912** ／ pycanon **1,924** ／ anonymeter **1,133** ／ **piiscope 58**。

解读边界：只能说明"库层有流量、发布前扫描产品层流量低"，**不能**用于推算本题的市场规模或收入。

### 1.6 未取得项（❌ 不作论据）

| 项 | 状态 | 原因 |
| --- | --- | --- |
| Reddit 侧需求原话 | ❌ 未取得 | 直连超时、pullpush 限流（基准日 2026-10-20） |
| 商业产品销量 / 定价 | ❌ 未核对 | 未查证，不作论据 |
| 上述 5 个 0 命中的"绝对空白" | ⬜ 不成立 | 检索未穷尽；只写"检索式为 0"，不写"无人做过" |

## 二、数据源可获取性

| 数据源 | 获取方式 | 是否必需 | 状态 |
| --- | --- | --- | --- |
| 合成夹具（本项目生成） | `data/fixtures/` 由生成器程序化产出 | **是**（默认路径） | ✅ 无外部依赖 |
| UCI Adult（Census Income） | UCI Machine Learning Repository 公开下载（`adult.data` / `adult.test` / `adult.names`） | 否（仅演示） | ✅ 公开可下载（基准日核对可获取路径；**具体下载 URL、文件哈希与列定义以 M1 实测回填，不在此预写**） |
| 真实个人数据 | — | **否，且禁止** | ❌ 明令禁止 |

- **安装后零网络**：`pip install` 之后，从 `--help` 到报告生成全程不得发起出站请求；Adult 演示需要用户**自行**提前下载数据（脚本只读本地文件，不替我下载）。
- **仓库不入库任何数据表**：`.gitignore` 排除 `*.csv` 示例数据目录（见根 `.gitignore`）；`examples/adult/` 只入库脚本、判据与期望输出摘要。

## 三、合成数据纪律

1. **程序化植入已知违例**：夹具生成器必须显式构造可陈述的违例，例如"`zip` + `dob` 组合后，类大小分布中出现 **N** 个单例类（N 由生成器参数写入真值文件）"。
2. **真值同时产出**：生成器一次运行产出 ① 合成表 ② 真值文件（最小 k、最小崩塌集、违例等价类键、违例行号、唯一记录行号）。真值由生成器的**独立判定式**写出，**不 import 生产模块**，不得由扫描器自证。
3. **可重跑**：生成器使用固定种子；同种子同参数 → 逐字节相同的表与真值。种子、参数与真值同时入库。
4. **不引用真实敏感数据**：夹具中的姓名、证件号、地址、电话一律为**明显虚构**的合成值；不得从真实数据集摘取个人行（Adult 只作为**演示规模**，不作为真值来源，且不入库）。
5. **规模分层**：夹具至少覆盖三种规模（小型可手算、中型触发剪枝、大型触发预算截断），每种规模的真值都必须可被人工按输出复核。
6. **缺测注入**：夹具必须显式包含缺失值，用于覆盖 §四 的三种缺失策略；缺失的植入位置写入真值。

## 四、数值口径（单点定义，代码 / 文案 / 文档一律引用本文件）

> **本节是唯一出处。** 任何模块、测试、报告文案不得自行解释以下任一概念；口径变更须改本节 + 升 `plan/01` 版本史，不得在代码注释里悄悄改。

### 4.1 列角色（枚举，闭合集合）

`qi` ／ `sensitive` ／ `direct-identifier` ／ `date-precision` ／ 未声明。

- `qi`：参与等价类键。
- `sensitive`：不参与键，参与 l 与 t。
- `direct-identifier`：**默认不参与** k/l/t（参与则 k 恒为 1，结论无信息量）；报告中单列"若泄露即直接重识别"提示。
- `date-precision`：声明日期粒度（`year` / `month` / `day`），归一化时**只按声明粒度截断**，不做隐式猜测。
- **未声明即不参与**，并在"未参与清单"中列出，不静默丢弃。

### 4.2 QI 候选打分

对每个 `qi`（或候选）列，报告两个**原始统计量**与一个分数：

- `cardinality` = 该列（按声明粒度归一化后）的**不同取值数**（缺失值不计入）。
- `uniqueness_ratio` = `cardinality / 非缺失行数`（非缺失行数为 0 时该列标记 `undefined`，不参与打分）。
- `qi_score` = `uniqueness_ratio`（保留 6 位小数，`ROUND_HALF_EVEN`），**仅此一个公式**。

打分只用于**排序候选**与提示"这列值得声明为 QI"，**不自动改变角色**。"该不该算 QI"由人在声明中决定（D2）。

> 反例纪律：**禁止按列名关键词判定**（对照 piiscope 的 `_QI_NAME_HINTS`）。若将来增加启发式，必须先在报告里输出该启发式的输入统计量，且不得改变上述 `qi_score` 定义。

### 4.3 等价类与 k / l / t 定义

- **等价类键** = 按声明顺序（`qi` 列在声明文件中的先后）拼接的取值元组；元组的规范化文本用于稳定排序与输出。
- **k** = 全部等价类中**最小类大小**。空表 → `undefined`（不是 0，也不是无穷）。
- **l** = 对形如"类内 `sensitive` 列的不同取值数"的定义，取**全部等价类中的最小值**。多个 `sensitive` 列时：**逐列计算，然后取最小值**（不做联合取值数）；报告必须写明"l 为逐列最小"这一口径。
- **t** = 对每个等价类，计算类内 `sensitive` 分布与全表分布的最大距离；**t 取全部等价类中的最大值**。距离口径：对每个 `sensitive` 列分别计算（离散列用**总变差距离**：`0.5 × Σ|p_class − p_all|`），多列时取**该类的最大列距离**，再对类取最大。t 只在单列 `sensitive` 时给出一个数；多列时逐列输出并在顶层取最大，报告中必须逐列列出。
- **违例** = 满足 `class_size < k_threshold`（或声明了 l/t 门限时 `l < l_threshold` / `t > t_threshold`）的等价类。每条违例输出：**分组键 + 计数 + 行号清单**（行号 = 输入文件的数据行序号，1 起，不含表头；报告须注明此定义）。

### 4.4 缺失值策略（显式三选一，无默认）

**缺失值 token 集合（K4，唯一出处）**：某个单元格的值**逐字等于**下列任一 token 即视为缺失——
`""`（空串）／`NA`／`N/A`／`null`／`NULL`／`-`。大小写敏感，**不做**去空格、不做大小写归一
（`na`、`Null`、`" "` 都不是缺失）。实现单点：`tableio.missing_set()`。

| 策略名 | 语义 | 报告要求 |
| --- | --- | --- |
| `drop` | 含缺失的行**不参与**任何分组；单独统计"未裁决行数" | 首行打印策略名 + 未裁决行数 |
| `single-column` | 缺失值作为该列的普通取值（`NULL` 自成一级）参与分组 | 首行打印策略名 + 含缺失的等价类数 |
| `separate-class` | 含缺失的全部行合并为**一个独立等价类**，与正常类分开报告，其 k 单独给出 | 首行打印策略名 + 该类的 k 与行数 |

- 未指定策略 → **报错退出（退出码 2）**，不猜、不默认。
- 三种策略的结果分别计算、分别可复算；不得把某策略的结论套用到另一策略。

### 4.5 组合搜索：剪枝、预算与完整性三态

**单调性前提（剪枝成立的唯一条件）**：在"**固定行集 + 只做分组**"的语义下，向 QI 集合 S 增加一列，任何等价类只能被**细分或保持不变**，故 `k(S ∪ {c}) ≤ k(S)`。剪枝据此实现：若 `k(S) < k_threshold`，则跳过 S 的全部超集。

**枚举顺序**：按子集大小升序；同大小按列的规范化名（Unicode 码位序）排序。结果不依赖剪枝顺序。

**预算**：以"已评估子集数"计数，上限由判据文件给出。到达上限即停止，剩余子集**不评估**。

**完整性三态（闭合集合，必须出现在 CLI 输出 + JSON + README 三处）**：

| 状态 | 含义 |
| --- | --- |
| `exhausted`（已穷尽） | 在 §4.5 的单调性前提下，候选子集空间中所有**需要**评估的子集都已评估 |
| `budget-truncated`（被预算截断） | 存在本应评估但因预算未评估的子集；**不得声称穷尽** |
| `monotonicity-not-applicable`（单调性不适用） | 启用了会破坏单调性的操作（泛化、抑制、行过滤、或 `drop` 策略下加列改变被丢行集等），**不得声称穷尽**，也不得把剪枝结果当结论 |

**最小崩塌集**：子集 S 满足 `k(S) ≥ k_threshold`，且对候选池中任一 `c ∉ S`，`k(S ∪ {c})` 为 `undefined` 或 `< k_threshold`。若单列已达阈值，最小崩塌集为**空集**（报告中显式表达，不输出空数组冒充"无结果"）；若独立候选池全部不达标，明确报**无解**。存在多个最小崩塌集时**全部列出**（按枚举顺序），不得只显示第一个。

**歧义纪律**：`budget-truncated` 与 `monotonicity-not-applicable` 下的任何"最小崩塌集"都必须**标注为非穷尽结果**，措辞不得写成"最小"。

### 4.6 退出码（闭合集合）

| 退出码 | 含义 | 触发 |
| --- | --- | --- |
| `0` | 通过 | 所有声明阈值满足，且完整性状态为 `exhausted`（或结果未被裁剪） |
| `1` | 有违例（fail-closed） | 存在 `k < k_threshold`（或 l/t 越界） |
| `2` | 无法裁决 | 输入无效、判据文件缺项、缺失策略未指定、完整性为 `budget-truncated` 且用户要求"必须穷尽"（`--require-exhaustive`）等 |

**硬规则**：任何"算不出来 / 没算完 / 输入有误"一律 `2`，**绝不退化为 `0`**。退出码的映射在代码中只允许一处实现（单一函数），测试直接断言该函数。

### 4.7 可复算输出纪律

- 键序固定（按字典序），数组顺序固定（按 §4.3 / §4.5 定义的排序），浮点统一 `round(x, 6)` + `ROUND_HALF_EVEN`。
- 报告**不含**时间戳、主机名、绝对路径（路径以 `--root` 相对化）；同一输入两次运行 → 逐字节相同的 JSON。
- 每条违例必须给"分组键 + 计数 + 行号"，三件套缺一即视为不可复核（对照 sdcMicro #350 / #356 的失败点）。

### 4.8 攻击者口径（M4，闭合三态）

三种口径的判定**只依赖等价类大小**，不依赖敏感列取值——这是"攻击者能否从类里定位个体"的形式化。
实现单点：`m4_risk.classify()`（M4 交付）；测试名必须带口径名。

| 口径 | 攻击者知道什么 | 判定（`k_c` = 该记录所在等价类大小） | 措辞 |
| --- | --- | --- | --- |
| `prosecutor` | 目标**在表里** | `k_c == 1` → 该记录被识别；否则未识别 | 类内唯一定位 |
| `journalist` | **不知道**目标是否在表里 | `k_c <= 2` → 可锁定具体个体（`k_c == 2` 时另一人可被反推） | 含成员推断的保守处理 |
| `marketer` | 只关心人群大小 | `k_c < 3`（即 `<= 2`）→ 可归入小人群 | 不关心具体是谁 |

三项阈值（`1` / `2` / `3`）**写死在本节**，改它们属于口径变更：必须同步改本节 + `m4_risk`（M4 交付）+ 真值 + 测试名。
