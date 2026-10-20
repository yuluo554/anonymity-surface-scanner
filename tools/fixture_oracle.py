"""独立真值 oracle：从**已生成的行**用朴素实现复算夹具的期望值。

为什么单独一份：真值若由被测实现写出，等于自证（`plan/03` K10 / `plan/00` R3）。
本模块**不 import 任何生产模块**（`tests/test_fixtures.py` 有 AST 守门），也不 import
`tools/gen_fixtures.py`——生成器 import 本模块，依赖方向单向。

口径出处一律是 `data/README.md` §四（本文件只是它的一份朴素复写）：
  * §4.3 行号 = 数据行序号（1 起，不含表头）；等价类键 = 按给定顺序拼接的取值元组；
    k = 最小类大小；l = 逐 sensitive 列算类内不同取值数、再取全部类的最小值；
    t = 逐类逐列与全表分布的总变差距离，取最大。
  * §4.4 缺失 token 集合与三种策略（`drop` / `single-column` / `separate-class`），
    缺失判定按**整行**（任一分组参与列出现缺失 token，该行即"含缺失"）。
  * §4.5 子集枚举顺序（大小升序 → 列名码位序）、剪枝、预算、崩塌边界集。

朴素 = 不优化：每次都从头分组、用集合数不同取值、用 Fraction 算总变差距离。
"快"不是本文件的目标，"与生产实现无关地算对"才是。
"""
from __future__ import annotations

import itertools
import json
from collections import Counter
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction

MISSING_TOKENS = ("", "NA", "N/A", "null", "NULL", "-")
POLICIES = ("drop", "single-column", "separate-class")
NULL_TOKEN = "NULL"                 # `single-column` 下缺失值的占位取值
MISSING_CLASS_KEY = "__MISSING__"   # `separate-class` 的独立类键

_SIX = Decimal("0.000001")


def round6(value):
    """与 `anonymity_scanner.canonical.round6` 同口径（Decimal(str(x)) + ROUND_HALF_EVEN）。

    这里**刻意复写**而不是 import：本文件必须能在没有 `src/` 的树里独立跑。
    等价性由 `tests/test_fixtures.py::test_tool_round6_matches_canonical` 逐值钉住。
    """
    if value is None:
        return None
    quantized = Decimal(str(float(value))).quantize(_SIX, rounding=ROUND_HALF_EVEN)
    result = float(quantized)
    return 0.0 if result == 0.0 else result


def is_missing(value) -> bool:
    return value in MISSING_TOKENS


def row_has_missing(row, columns=None) -> bool:
    """该行是否"含缺失"。

    `columns` 给定时只看**参与分组的那些列**（语义：这一行会不会因为本列缺失而被丢出分组 /
    落进缺失独立类）。不给时看整行——用于"这份夹具含不含缺失"这类数据事实。

    为什么必须按参与列算：`drop` 下"加一列"可能改变被丢的行集，这正是 §4.5
    `monotonicity-not-applicable` 的触发点；若按整行算，"加列"根本不影响判定，
    单调性前提反而被看不见地破坏了。
    """
    values = row.values() if columns is None else (row[name] for name in columns)
    return any(is_missing(value) for value in values)


def subset_text(columns) -> str:
    """列子集的规范化文本：`json.dumps(sorted(cols), separators=(",", ":"))`。

    例：`[]` / `["age"]` / `["age","zip"]`。排序 = 码位序（与 §4.5 的枚举口径一致）。
    """
    return json.dumps(sorted(columns), ensure_ascii=False, separators=(",", ":"))


def class_key(row, columns, policy) -> str:
    """等价类键的规范化文本：`col=value|col=value`（列顺序 = 传入顺序）。"""
    parts = []
    for name in columns:
        value = row[name]
        if policy == "single-column" and is_missing(value):
            value = NULL_TOKEN
        parts.append("%s=%s" % (name, value))
    return "|".join(parts)


def group(rows, columns, policy):
    """把行分组。返回 `(classes, undecided)`：{key: [row_number, ...]} / [row_number]。

    * `drop`：含缺失的行不进任何类 → `undecided`；
    * `single-column`：缺失值在该列作为普通取值 `NULL` 参与分组；
    * `separate-class`：含缺失的全部行并入一个独立类 `__MISSING__`。
    """
    classes = {}
    undecided = []
    for number, row in enumerate(rows, start=1):
        if policy != "single-column" and row_has_missing(row, columns):
            if policy == "drop":
                undecided.append(number)
            else:
                classes.setdefault(MISSING_CLASS_KEY, []).append(number)
            continue
        classes.setdefault(class_key(row, columns, policy), []).append(number)
    return classes, undecided


def k_of(classes):
    """k = 全部等价类中的最小类大小；没有类（空表 / 全被丢）→ None（undefined，不是 0）。"""
    if not classes:
        return None
    return min(len(numbers) for numbers in classes.values())


def _normalized(row, column, policy):
    value = row[column]
    if policy == "single-column" and is_missing(value):
        return NULL_TOKEN
    return value


def l_detail(rows, classes, sensitive, policy):
    """l = 逐 sensitive 列算类内不同取值数，列间取最小，再取全部等价类的最小值。"""
    by_number = {number: row for number, row in enumerate(rows, start=1)}
    per_class = {}
    for key, numbers in classes.items():
        per_class[key] = {
            column: len({_normalized(by_number[n], column, policy) for n in numbers})
            for column in sensitive
        }
    if not per_class or not sensitive:
        return {"l": None, "by_class": per_class}
    return {"l": min(min(counts.values()) for counts in per_class.values()), "by_class": per_class}


def t_detail(rows, classes, sensitive, undecided, policy):
    """t = 逐类逐列与全表分布的总变差距离（0.5 × Σ|p_class − p_all|），取最大。

    全表分布口径 = 参与分组的行（`drop` 下不含未裁决行；其余策略含全部行）。
    """
    by_number = {number: row for number, row in enumerate(rows, start=1)}
    dropped = set(undecided)
    included = [number for number in range(1, len(rows) + 1) if number not in dropped]
    per_class = {}
    for key, numbers in classes.items():
        per_class[key] = {}
        for column in sensitive:
            class_counts = Counter(_normalized(by_number[n], column, policy) for n in numbers)
            all_counts = Counter(_normalized(by_number[n], column, policy) for n in included)
            class_total = sum(class_counts.values())
            all_total = sum(all_counts.values())
            distance = Fraction(0)
            for value in set(class_counts) | set(all_counts):
                distance += abs(
                    Fraction(class_counts.get(value, 0), class_total)
                    - Fraction(all_counts.get(value, 0), all_total)
                )
            per_class[key][column] = round6(float(distance / 2))
    if not per_class or not sensitive:
        return {"t": None, "by_class": per_class}
    return {"t": max(max(counts.values()) for counts in per_class.values()), "by_class": per_class}


def summarize(rows, columns, policy, threshold, sensitive):
    """一次策略下的完整摘要（k / l / t / 违例三件套 / 唯一记录 / 未裁决行）。"""
    classes, undecided = group(rows, columns, policy)
    violations = []
    for key in sorted(classes):
        numbers = classes[key]
        if len(numbers) < threshold:
            violations.append({"key": key, "count": len(numbers), "row_numbers": sorted(numbers)})
    unique = sorted(number for numbers in classes.values() if len(numbers) == 1 for number in numbers)
    missing_class = None
    if MISSING_CLASS_KEY in classes:
        numbers = classes[MISSING_CLASS_KEY]
        missing_class = {"k": len(numbers), "row_numbers": sorted(numbers)}
    diversity = l_detail(rows, classes, sensitive, policy)
    closeness = t_detail(rows, classes, sensitive, undecided, policy)
    histogram = Counter(len(numbers) for numbers in classes.values())
    return {
        "k": k_of(classes),
        "l": diversity["l"],
        "t": closeness["t"],
        "class_count": len(classes),
        # 类大小直方图：{"1": 3, "5": 2, ...}（键 = 类大小，值 = 有那么多个类）
        "class_size_histogram": {str(size): histogram[size] for size in sorted(histogram)},
        "violations": violations,
        "unique_records": unique,
        "undecided_rows": sorted(undecided),
        "missing_class": missing_class,
        "l_by_class": diversity["by_class"],
        "t_by_class": closeness["by_class"],
    }


def k_table(rows, subsets, policy):
    """对给定列子集逐个算 k，返回 {规范化子集文本: k}。"""
    table = {}
    for subset in subsets:
        classes, _ = group(rows, list(subset), policy)
        table[subset_text(subset)] = k_of(classes)
    return table


def candidate_subsets(pool, max_size=2):
    """真值 `k_by_columns` 的覆盖口径：空集 + 所有 ≤ max_size 的子集 + 全集。"""
    pool = sorted(pool)
    out = [()]
    for size in range(1, min(max_size, len(pool)) + 1):
        out.extend(itertools.combinations(pool, size))
    if len(pool) > max_size:
        out.append(tuple(pool))
    return out


def search_collapse_sets(rows, pool, threshold, policy, budget=None, monotone=True):
    """按 `data/README.md` §4.5 枚举并求**崩塌边界集**。

    口径（§4.5 的定义句，M1 起以它为准；见 `plan/00` 勘误 E2）：

        S 安全        ⇔ k(S) ≥ threshold（空集的 k = 参与分组的行数）
        S 是崩塌边界集 ⇔ S 安全，且 ∀c ∉ S，k(S ∪ {c}) 为 undefined 或 < threshold
        报告全部边界集（按枚举顺序）；边界集里出现空集时 `empty_set_witness = true`，
        语义 = **一个 QI 列都不能加**（不是"什么都不用声明"）。

    `monotone=False`（`drop` 策略 + 候选池含缺失）时**不做剪枝**：加列会改变被丢的行集，
    父集不安全推不出子集不安全。此时仍按"边界集"的定义逐个子集实算，但完整性状态是
    `monotonicity-not-applicable`，结论**不得**被当成穷尽结果。

    边界：
      * 空集都不安全（行数 < threshold）或候选池为空 → `verdict = "no_solution"`；
      * 预算耗尽 → `completeness = "budget-truncated"`，`non_exhaustive = true`。

    `evaluated_subsets` = 实际算过 k 的不同子集数（含空集）；`pruned_subsets` = 单调性成立时
    因某父集不安全而跳过的子集数。
    """
    pool = sorted(pool)
    cache = {}
    pruned = set()
    exhausted = [True]

    def k_for(combo):
        combo = tuple(sorted(combo))
        if combo not in cache and combo not in pruned:
            classes, _ = group(rows, list(combo), policy)
            cache[combo] = k_of(classes)
        return cache.get(combo)

    def is_safe(combo):
        combo = tuple(sorted(combo))
        if combo in pruned:
            return False
        value = k_for(combo)
        return value is not None and value >= threshold

    def budget_hit():
        return budget is not None and len(cache) >= budget

    base = k_for(())
    result = {
        "verdict": "ok",
        "completeness": "exhausted",
        "non_exhaustive": False,
        "minimal_collapse_sets": [],
        "empty_set_witness": False,
        "empty_set_k": base,
        "candidate_count": len(pool),
        "subset_space": 2 ** len(pool) - 1,
        "budget": budget,
        "monotonicity_applicable": bool(monotone),
        "evaluated_subsets": 0,
        "pruned_subsets": 0,
    }

    if not pool or base is None or base < threshold:
        result["verdict"] = "no_solution"
        result["evaluated_subsets"] = len(cache)
        return result

    for size in range(1, len(pool) + 1):
        for combo in itertools.combinations(pool, size):
            if monotone:
                parents = list(itertools.combinations(combo, size - 1))
                if any(not is_safe(parent) for parent in parents):
                    pruned.add(combo)   # 单调性下父集不安全 ⇒ 超集必不安全
                    continue
            if budget_hit():
                exhausted[0] = False
                break
            is_safe(combo)
        if not exhausted[0]:
            break

    # 边界判定：只看实算过的安全集合。单调性成立时未实算的都是被剪掉的（必然不安全）；
    # 单调性不成立时未实算的只能归入"没算"，由 completeness 如实标注。
    safe_sets = {combo for combo, value in cache.items() if value is not None and value >= threshold}
    for combo in sorted(safe_sets, key=lambda item: (len(item), item)):
        if any(
            tuple(sorted(combo + (column,))) in safe_sets
            for column in pool if column not in combo
        ):
            continue
        # 单调性不成立时，扩展可能没算过 → 不能断言它不安全。
        if not monotone:
            unevaluated = [
                tuple(sorted(combo + (column,)))
                for column in pool
                if column not in combo
                and tuple(sorted(combo + (column,))) not in cache
            ]
            if unevaluated:
                continue
        result["minimal_collapse_sets"].append(list(combo))

    result["empty_set_witness"] = [] in result["minimal_collapse_sets"]
    result["evaluated_subsets"] = len(cache)
    result["pruned_subsets"] = len(pruned)
    if not exhausted[0]:
        result["completeness"] = "budget-truncated"
    elif not monotone:
        result["completeness"] = "monotonicity-not-applicable"
    result["non_exhaustive"] = result["completeness"] != "exhausted"
    return result
