"""可复算 gate（M5）：判据文件 → 扫描（+ 可选搜索）→ `gate.json` / `gate.md` / 退出码。

口径唯一出处：`data/README.md` §4.6（退出码）与 §4.7（可复算输出纪律）。纪律：

  * **判据解析只此一处**（`load_criteria`）：未知顶层键 / 未知 `thresholds` 键 / 未知 `search` 键
    一律 `CriteriaError`——判据是政策输入，**闭合**才可复算。
  * **计算只复用既有实现**（K1）：k/l/t 与违例三件套走 `m2_classes.summarize`；
    组合搜索走 `m3_search.search`。本模块不重写任何统计。
  * **结论优先级显式**：`undecidable > violation > pass`（`combine_outcomes`）。
    退出码仍只由 `exit_codes.map_outcome` 映射（K2）。
  * **渲染是纯函数**：`render_markdown(document)` 不读时钟 / 环境 / 文件系统；
    `evaluate()` 只吃已读入的表与声明。报告不含时间戳、主机名、绝对路径（K7）。
  * **非穷尽不得称"最小"**：`gate.md` 里只有 `completeness == "exhausted"` 才写
    "最小崩塌集（穷尽结果）"；其余状态写"崩塌边界集（非穷尽结果…）"。
"""
from __future__ import annotations

import json
from pathlib import Path

from . import __version__, m2_classes, m3_search
from .declaration import require_missing_policy
from .exit_codes import CriteriaError, map_outcome

TOOL = "anonymity-scanner"

# 判据文件的闭合键集（`plan/03 §模块 M5`）。
TOP_LEVEL_KEYS = frozenset(["table", "declaration", "missing_policy", "thresholds", "search"])
THRESHOLD_KEYS = frozenset(["k", "l", "t"])
SEARCH_KEYS = frozenset(["enabled", "budget", "require_exhaustive"])

# gate 层的"无法裁决"原因（与 m2 的 empty_table / no_participating_rows 同列）。
REASON_REQUIRE_EXHAUSTIVE = "search_budget_truncated_require_exhaustive"
REASON_SEARCH_NOT_EXHAUSTED = "search_not_exhausted"

_OUTCOME_RANK = {"pass": 0, "violation": 1, "undecidable": 2}
OUTCOME_MEANING = {
    "pass": "通过：全部声明阈值满足，且完整性未被裁剪",
    "violation": "有违例：至少一个等价类未满足声明阈值",
    "undecidable": "无法裁决（fail-closed）：输入/判据无效、算不出来或未算完",
}


def _require_positive_int(label, value):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CriteriaError("%s必须是正整数" % label, repr(value))
    return value


def _require_bool(label, value):
    if not isinstance(value, bool):
        raise CriteriaError("%s必须是布尔值" % label, repr(value))
    return value


def load_criteria(path):
    """读取并**闭合校验**判据文件。任何不合规都抛 `CriteriaError`（退出码 2）。

    返回的是**已验证的归一化结构**（不是原始 JSON），并带上 `base`：
    判据内的相对路径一律以**判据文件所在目录**为基准（判据可搬移）。
    """
    target = Path(path)
    if not target.is_file():
        raise CriteriaError("判据文件不存在", str(target))
    try:
        document = json.loads(target.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise CriteriaError("判据文件不是合法 JSON", str(exc))
    if not isinstance(document, dict):
        raise CriteriaError("判据文件顶层必须是对象")

    unknown = sorted(set(document) - TOP_LEVEL_KEYS)
    if unknown:
        raise CriteriaError("判据文件有未知顶层键", ", ".join(unknown))
    for key in ("table", "declaration", "missing_policy", "thresholds"):
        if key not in document:
            raise CriteriaError("判据文件缺必填项", key)

    for key in ("table", "declaration"):
        value = document[key]
        if not isinstance(value, str) or not value.strip():
            raise CriteriaError("判据文件 %s 必须是非空字符串" % key, repr(value))
    policy = require_missing_policy(document["missing_policy"])

    thresholds = document["thresholds"]
    if not isinstance(thresholds, dict):
        raise CriteriaError("判据文件 thresholds 必须是对象")
    unknown = sorted(set(thresholds) - THRESHOLD_KEYS)
    if unknown:
        raise CriteriaError("判据文件 thresholds 有未知键", ", ".join(unknown))
    if "k" not in thresholds:
        raise CriteriaError("判据文件缺 thresholds.k", "k 门限是闸门的必要条件")
    k = _require_positive_int("thresholds.k", thresholds["k"])

    l_threshold = thresholds.get("l")
    if l_threshold is not None:
        _require_positive_int("thresholds.l", l_threshold)
    t_threshold = thresholds.get("t")
    if t_threshold is not None:
        if isinstance(t_threshold, bool) or not isinstance(t_threshold, (int, float)):
            raise CriteriaError("thresholds.t 必须是 [0, 1] 内的数或 null", repr(t_threshold))
        if not (0.0 <= float(t_threshold) <= 1.0):
            raise CriteriaError("thresholds.t 必须落在 [0, 1]", repr(t_threshold))

    search = document.get("search")
    enabled = False
    budget = None
    require_exhaustive = False
    if search is not None:
        if not isinstance(search, dict):
            raise CriteriaError("判据文件 search 必须是对象")
        unknown = sorted(set(search) - SEARCH_KEYS)
        if unknown:
            raise CriteriaError("判据文件 search 有未知键", ", ".join(unknown))
        if "enabled" in search:
            enabled = _require_bool("search.enabled", search["enabled"])
        if "budget" in search:
            budget = _require_positive_int("search.budget", search["budget"])
        if "require_exhaustive" in search:
            require_exhaustive = _require_bool("search.require_exhaustive", search["require_exhaustive"])
        if enabled and budget is None:
            raise CriteriaError(
                "search.enabled=true 时必须给 search.budget",
                "没有预算的搜索不是可复算的搜索（§4.5）",
            )
        if not enabled and require_exhaustive:
            raise CriteriaError(
                "search.require_exhaustive=true 但 search.enabled=false",
                "没有搜索就没有'必须穷尽'的对象；二者不能互相矛盾",
            )

    return {
        "path": str(target),
        "base": str(target.resolve().parent),
        "table": document["table"],
        "declaration": document["declaration"],
        "missing_policy": policy,
        "thresholds": {"k": k, "l": l_threshold, "t": t_threshold},
        "search": {
            "enabled": enabled,
            "budget": budget,
            "require_exhaustive": require_exhaustive,
        },
    }


def combine_outcomes(*outcomes):
    """结论层优先级：`undecidable > violation > pass`。

    不认识的值按 `undecidable`（fail-closed）。这是**结论组合**，不是退出码映射——
    退出码仍然只走 `exit_codes.map_outcome`（K2）。
    """
    result = "pass"
    for outcome in outcomes:
        if outcome not in _OUTCOME_RANK:
            return "undecidable"
        if _OUTCOME_RANK[outcome] > _OUTCOME_RANK[result]:
            result = outcome
    return result


def _gate_undefined_reason(scan, search, require_exhaustive, outcome):
    if scan["undefined_reason"] is not None:
        return scan["undefined_reason"]
    if search is None:
        return None
    if search["completeness"] == "budget-truncated" and require_exhaustive:
        return REASON_REQUIRE_EXHAUSTIVE
    # 非穷尽只影响"能否判通过"：已经判出违例时，退出码是 1，不需要再挂"无法裁决"原因。
    if outcome == "undecidable" and search["completeness"] != "exhausted":
        return REASON_SEARCH_NOT_EXHAUSTED
    return None


def evaluate(table, decl, criteria, table_label, criteria_label):
    """组装 gate 结论（纯函数：不写盘、不读时钟/环境）。

    `table_label` / `criteria_label` 是**已相对化**的报告路径（CLI 用
    `canonical.relativize` 算好后传入），保证产物不含绝对路径（K7）。
    """
    policy = criteria["missing_policy"]
    thresholds = criteria["thresholds"]
    qi = [column.name for column in decl.qi_columns()]
    sensitive = [column.name for column in decl.sensitive_columns()]
    if not qi:
        raise CriteriaError("未声明任何 qi 列，无法分组", "判据文件引用的声明里没有任何 qi 列")
    if (thresholds["l"] is not None or thresholds["t"] is not None) and not sensitive:
        raise CriteriaError(
            "判据声明了 l/t 门限但没有 sensitive 列",
            "l/t 只在 sensitive 列上定义；给至少一列标 {\"role\": \"sensitive\"}",
        )

    scan = m2_classes.summarize(
        table, qi, sensitive, policy, thresholds["k"],
        l_threshold=thresholds["l"], t_threshold=thresholds["t"],
    )

    search = None
    search_outcome = None
    if criteria["search"]["enabled"]:
        # `require_exhaustive` 不交给 m3：gate 需要**先拿到**被截断的事实，
        # 再按结论优先级合并（否则异常会抹掉 gate.json 里的证据）。
        search = m3_search.search(
            table, qi, sensitive, policy, thresholds["k"],
            budget=criteria["search"]["budget"], require_exhaustive=False,
        )
        search_outcome = m3_search.outcome_for(search)

    outcomes = [scan["verdict"]]
    if search_outcome is not None:
        outcomes.append(search_outcome)
    if (
        search is not None
        and search["completeness"] == "budget-truncated"
        and criteria["search"]["require_exhaustive"]
    ):
        # §4.6：要求穷尽却被截断 → fail-closed 取 2，**不**让"有违例"覆盖这条。
        outcomes.append("undecidable")
    outcome = combine_outcomes(*outcomes)
    undefined_reason = _gate_undefined_reason(
        scan, search, criteria["search"]["require_exhaustive"], outcome
    )

    return {
        "tool": TOOL,
        "version": __version__,
        "command": "gate",
        "criteria": criteria_label,
        "table": table_label,
        "rows": table.row_count,
        "columns": list(table.header),
        "declarations": {
            "qi_columns": qi,
            "sensitive_columns": sensitive,
            "direct_identifiers": decl.direct_identifier_warning(),
            "unparticipating": decl.unparticipating(),
            "missing_policy": policy,
            "thresholds": {
                "k": thresholds["k"],
                "l": thresholds["l"],
                "t": thresholds["t"],
            },
            "search": {
                "enabled": criteria["search"]["enabled"],
                "budget": criteria["search"]["budget"],
                "require_exhaustive": criteria["search"]["require_exhaustive"],
            },
        },
        "scan": scan,
        "search": search,
        "violations": scan["violations"],
        "outcome": outcome,
        "undefined_reason": undefined_reason,
        "exit_code": map_outcome(outcome),
    }


# ── 人读报告（纯函数；固定模板，无时间戳 / 主机名 / 绝对路径） ─────────────

def _value(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _cell(text):
    """markdown 表格单元格转义：分组键里天然含 `|`。"""
    return str(text).replace("\\", "\\\\").replace("|", "\\|")


def _join(values):
    return ", ".join(values) if values else "(none)"


def _row_numbers(numbers):
    return ", ".join(str(number) for number in numbers) if numbers else "(none)"


def _render_declarations(document):
    declarations = document["declarations"]
    search = declarations["search"]
    thresholds = declarations["thresholds"]
    lines = [
        "## 一、声明（四项；所有数字只在这组上下文里成立）",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        "| 角色 · qi | %s |" % _cell(_join(declarations["qi_columns"])),
        "| 角色 · sensitive | %s |" % _cell(_join(declarations["sensitive_columns"])),
        "| 角色 · direct-identifier | %s |" % _cell(_join(declarations["direct_identifiers"])),
        "| 缺失策略 | %s |" % _cell(declarations["missing_policy"]),
        "| 阈值 | k=%s, l=%s, t=%s |"
        % (_value(thresholds["k"]), _value(thresholds["l"]), _value(thresholds["t"])),
        "| 预算 | search.enabled=%s, budget=%s, require_exhaustive=%s |"
        % (_value(search["enabled"]), _value(search["budget"]), _value(search["require_exhaustive"])),
        "",
        '> "最小 k" / "最小崩塌集" / "违例行数"都是上述声明下的结果，不是该表的绝对隐私水平。',
        "",
    ]
    return lines


def _render_scan(document):
    scan = document["scan"]
    metrics = scan["k_l_t"]
    threshold_k = document["declarations"]["thresholds"]["k"]
    below_k = [
        (int(size), count)
        for size, count in metrics["class_size_histogram"].items()
        if int(size) < threshold_k
    ]
    below_k.sort()
    histogram = ", ".join("%d×%d" % (size, count) for size, count in below_k)
    histogram_text = "%s（另有 ≥k 的类；完整直方图见 gate.json）" % (
        histogram if histogram else "(none)"
    )
    missing_class = metrics["missing_class"]
    if missing_class is None:
        missing_class_text = "(none)"
    else:
        missing_class_text = "%d 行（k=%d）" % (len(missing_class["row_numbers"]), missing_class["k"])
    unused = ", ".join(
        "%s(%s)" % (item["column"], item["reason"]) for item in document["declarations"]["unparticipating"]
    )
    lines = [
        "## 二、扫描结论",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        "| k | %s |" % _value(metrics["k"]),
        "| l | %s |" % _value(metrics["l"]),
        "| t | %s |" % _value(metrics["t"]),
        "| 等价类数 | %d |" % metrics["class_count"],
        "| 类大小直方图（<k 的部分） | %s |" % _cell(histogram_text),
        "| 未裁决行（drop） | %s |" % _cell(_row_numbers(metrics["undecided_rows"])),
        "| 缺失独立类（separate-class） | %s |" % _cell(missing_class_text),
        "| 未参与列 | %s |" % _cell(unused if unused else "(none)"),
        "| 结论 | %s |" % scan["verdict"],
        "",
    ]
    return lines


def _render_violations(document):
    violations = document["violations"]
    lines = [
        "## 三、违例（分组键 + 计数 + 行号；三件套缺一即不可复核）",
        "",
        "共 %d 条。" % len(violations),
        "",
    ]
    if not violations:
        lines.extend(["无违例。", ""])
        return lines
    lines.extend([
        "| # | 分组键 | 计数 | 行号 |",
        "| --- | --- | --- | --- |",
    ])
    for index, violation in enumerate(violations, start=1):
        lines.append(
            "| %d | `%s` | %d | %s |"
            % (index, _cell(violation["key"]), violation["count"], _row_numbers(violation["row_numbers"]))
        )
    lines.append("")
    return lines


def _render_search(document):
    search = document["search"]
    if search is None:
        return [
            "## 四、组合搜索",
            "",
            "未启用（判据里没有 `search` 块，或 `search.enabled=false`）。"
            "结论只覆盖声明集合本身，不包含组合攻击面。",
            "",
        ]
    exhaustive = search["completeness"] == "exhausted"
    lines = [
        "## 四、组合搜索",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        "| 候选池 | %s（%d 列，子集空间 %d） |"
        % (_cell(_join(search["pool"])), search["candidate_count"], search["subset_space"]),
        "| 预算 / 已评估 / 剪枝 | %s / %d / %d |"
        % (_value(search["budget"]), search["evaluated_subsets"], search["pruned_subsets"]),
        "| 完整性（三态之一） | %s |" % search["completeness"],
        "| 单调性前提 | %s |" % _value(search["monotonicity_applicable"]),
        "| 空集 k（参与分组的行数） | %s |" % _value(search["empty_set_k"]),
        "| 声明集合的 k | %s |" % _value(search["declared_k"]),
        "| 搜索结论 | %s |" % search["verdict"],
        "",
    ]
    if search["verdict"] == "no_solution":
        lines.append(
            "**无解**：空集本身不安全（参与分组的行数 < k 阈值，或没有任何行参与分组）；"
            "不用空数组冒充\"无结果\"。"
        )
    else:
        if exhaustive:
            lines.append("**最小崩塌集（穷尽结果）**：")
        else:
            lines.append(
                "**崩塌边界集（非穷尽结果，完整性 = `%s`；不得称为最小崩塌集）**："
                % search["completeness"]
            )
        lines.append("")
        if not search["minimal_collapse_sets"]:
            lines.append("(none) — 没有任何候选人子集是崩塌边界集。")
        else:
            for combo in search["minimal_collapse_sets"]:
                lines.append("- `%s`" % json.dumps(combo, ensure_ascii=False))
            if search["empty_set_witness"]:
                lines.append("")
                lines.append(
                    "空集 `[]` 在列**是**边界集：语义 = **一个 QI 列都不能加**"
                    "（不是\"什么都不用声明\"）。"
                )
            elif not exhaustive and [] in search["minimal_collapse_sets"]:
                lines.append("")
                lines.append(
                    "空集 `[]` 在列：**预算不足，无法判定**它是否为边界集"
                    "（完整性 = `%s`，没有把单列扩展算完；"
                    "`empty_set_witness` 因此为 `false`，不得读作"
                    "\"存在安全的单列扩展\"）。" % search["completeness"]
                )
    lines.append("")
    if search["strata"]:
        lines.extend([
            "分层曲线（只聚合实算过的子集）：",
            "",
            "| \\|S\\| | 已评估 | min_k | 暴露行数 | 最差子集 |",
            "| --- | --- | --- | --- | --- |",
        ])
        for level in search["strata"]:
            lines.append(
                "| %d | %d | %s | %d | `%s` |"
                % (
                    level["size"],
                    level["evaluated"],
                    _value(level["min_k"]),
                    level["exposed_rows"],
                    _cell(json.dumps(level["worst_subset"], ensure_ascii=False)),
                )
            )
        lines.append("")
    return lines


def _render_outcome(document):
    outcome = document["outcome"]
    reason = document["undefined_reason"]
    lines = [
        "## 五、退出码",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        "| 结论（outcome） | %s |" % outcome,
        "| 退出码 | %d |" % document["exit_code"],
        "| 说明 | %s |" % OUTCOME_MEANING.get(outcome, "未知结论（按无法裁决处理）"),
        "| 无法裁决原因 | %s |" % (reason if reason is not None else "(none)"),
        "",
    ]
    return lines


def _render_recompute(document):
    return [
        "## 六、可复算说明",
        "",
        "```bash",
        "anonymity-scanner gate --criteria %s --out-dir <out>" % document["criteria"],
        "```",
        "",
        "- 判据里的相对路径以**判据文件所在目录**为基准（`--root` 只影响报告里的路径相对化）。",
        "- 同一输入两次运行 → `gate.json` 与 `gate.md` 逐字节相同；报告不含时间戳、主机名、绝对路径。",
        "- 行号 = 数据行序号（1 起，不含表头，空行不占号）。",
        "",
    ]


def render_markdown(document):
    """渲染 `gate.md`（纯函数；固定模板 + 已排序列表；以单个 LF 结尾）。"""
    lines = [
        "# %s gate" % TOOL,
        "",
        "- tool     : %s %s" % (document["tool"], document["version"]),
        "- criteria : %s" % document["criteria"],
        "- table    : %s (%d 行 × %d 列)"
        % (document["table"], document["rows"], len(document["columns"])),
        "",
    ]
    lines.extend(_render_declarations(document))
    lines.extend(_render_scan(document))
    lines.extend(_render_violations(document))
    lines.extend(_render_search(document))
    lines.extend(_render_outcome(document))
    lines.extend(_render_recompute(document))
    return "\n".join(lines).rstrip("\n") + "\n"
