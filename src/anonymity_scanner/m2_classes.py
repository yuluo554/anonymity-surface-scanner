"""等价类引擎（M2）：分组、k / l / t、违例三件套。

纪律（`plan/03 §模块 M2`、`data/README.md` §四）：
  * **纯函数**：不写盘、不读时钟、不读随机源、不 import `cli`（K8）。
  * 等价类键按**声明顺序**拼接（不是表头顺序）；键的规范化文本用于稳定排序与输出（§4.3）。
  * 行号 = `tableio.read_table` 给出的数据行序号（1 起，不含表头，空行不占号）——本模块原样透传（K6）。
  * 缺失判定只走 `tableio.is_missing`（K4）；"含缺失的行"只看本次参与分组的列（§4.4 末条）。
  * k/l/t 口径与 `data/README.md` §4.3 逐字对应；这里是**唯一实现**（K1）。
  * 空表 → `k = None` + `undefined_reason = "empty_table"`，结论按"无法裁决"处理——绝不返回 0 冒充通过。
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction

from .canonical import round6
from .exit_codes import CriteriaError
from .tableio import is_missing

POLICIES = ("drop", "single-column", "separate-class")
NULL_TOKEN = "NULL"               # `single-column`：缺失值作为该列的普通取值
MISSING_CLASS_KEY = "__MISSING__"  # `separate-class`：含缺失的行合并成的独立类键


def _indices(table, columns):
    """列名 → 列下标。声明已在 CLI 层校验过列存在，这里仍 fail-closed。"""
    indices = []
    for name in columns:
        index = table.column_index(name)
        if index is None:
            raise CriteriaError("分组列不在表头里", name)
        indices.append(index)
    return indices


def require_policy(policy):
    """纯函数层的策略校验（CLI 层另有 `declaration.require_missing_policy`，口径同源）。"""
    if policy not in POLICIES:
        raise CriteriaError("未知的缺失值策略", "%r（可选 %s）" % (policy, " / ".join(POLICIES)))
    return policy


def group_rows(table, columns, policy):
    """按缺失策略分组。

    返回 `(classes, undecided, values_by_key)`：
      * `classes`  = {规范化键: [行号, ...]}（行号升序）；
      * `undecided` = `drop` 下不参与任何分组的行号（升序）；
      * `values_by_key` = {键: 取值元组}，取值顺序 = `columns` 顺序。

    `columns` 为空（空集）时：所有行落进同一个类（键 = 空串），即"一张表就是一个类"——
    这是 §4.5 空集语义的实现基础（k(∅) = 参与分组的行数）。
    """
    require_policy(policy)
    indices = _indices(table, columns)
    classes = {}
    values_by_key = {}
    undecided = []
    for row_number, values in table.rows:
        selected = [values[index] for index in indices]
        if policy != "single-column" and any(is_missing(value) for value in selected):
            if policy == "drop":
                undecided.append(row_number)
            else:
                classes.setdefault(MISSING_CLASS_KEY, []).append(row_number)
                values_by_key.setdefault(MISSING_CLASS_KEY, [])
            continue
        rendered = []
        parts = []
        for name, value in zip(columns, selected):
            if policy == "single-column" and is_missing(value):
                value = NULL_TOKEN
            rendered.append(value)
            parts.append("%s=%s" % (name, value))
        key = "|".join(parts)
        classes.setdefault(key, []).append(row_number)
        values_by_key.setdefault(key, rendered)
    for numbers in classes.values():
        numbers.sort()
    return classes, sorted(undecided), values_by_key


def k_of(classes):
    """k = 全部等价类中的最小类大小；没有类（空表 / 全被丢）→ None（undefined，不是 0）。"""
    if not classes:
        return None
    return min(len(numbers) for numbers in classes.values())


def _value_lookup(table, policy):
    """行号 → 取值列表（含 single-column 的缺失归一），供 l/t 复用。"""
    by_number = {}
    for row_number, values in table.rows:
        if policy == "single-column":
            values = [NULL_TOKEN if is_missing(value) else value for value in values]
        by_number[row_number] = values
    return by_number


def l_detail(table, classes, sensitive, policy):
    """l = 逐 sensitive 列算类内不同取值数 → 列间取最小 → 全部类再取最小（§4.3）。

    返回 `(l, by_class)`；`by_class[key][column]` 保留逐列计数，供 l 门限判定使用。
    """
    if not classes or not sensitive:
        return None, {}
    indices = {name: table.column_index(name) for name in sensitive}
    lookup = _value_lookup(table, policy)
    by_class = {}
    for key, numbers in classes.items():
        by_class[key] = {
            name: len({lookup[number][indices[name]] for number in numbers}) for name in sensitive
        }
    return min(min(counts.values()) for counts in by_class.values()), by_class


def t_detail(table, classes, sensitive, undecided, policy):
    """t = 逐类逐 sensitive 列与全表分布的总变差距离（0.5 × Σ|p_class − p_all|），取最大。

    全表分布 = **参与分组的行**（`drop` 下不含未裁决行；其余策略含全部行 —— §4.3 / §4.4）。
    用 Fraction 做精确算术，最后才 `round6`，避免不同机器上的浮点尾差改变最后一位。
    """
    if not classes or not sensitive:
        return None, {}
    indices = {name: table.column_index(name) for name in sensitive}
    lookup = _value_lookup(table, policy)
    dropped = set(undecided)
    included = [row_number for row_number, _ in table.rows if row_number not in dropped]
    if not included:  # pragma: no cover - classes 非空时必有为空；防御性分支
        return None, {}
    by_class = {}
    for key, numbers in classes.items():
        by_class[key] = {}
        for name in sensitive:
            index = indices[name]
            class_counts = Counter(lookup[number][index] for number in numbers)
            all_counts = Counter(lookup[number][index] for number in included)
            class_total = sum(class_counts.values())
            all_total = sum(all_counts.values())
            distance = Fraction(0)
            for value in set(class_counts) | set(all_counts):
                distance += abs(
                    Fraction(class_counts.get(value, 0), class_total)
                    - Fraction(all_counts.get(value, 0), all_total)
                )
            by_class[key][name] = round6(float(distance / 2))
    return max(max(counts.values()) for counts in by_class.values()), by_class


def _violations(classes, k_threshold, l_threshold, t_threshold, l_by_class, t_by_class):
    """违例三件套（键 + 计数 + 行号）。l/t 门限按类逐列判定（§4.3 的违例定义）。"""
    out = []
    for key in sorted(classes):
        numbers = classes[key]
        hit = len(numbers) < k_threshold
        if not hit and l_threshold is not None and l_by_class:
            hit = min(l_by_class[key].values()) < l_threshold
        if not hit and t_threshold is not None and t_by_class:
            hit = max(t_by_class[key].values()) > t_threshold
        if hit:
            out.append({"key": key, "count": len(numbers), "row_numbers": list(numbers)})
    return out


def summarize(table, qi_columns, sensitive_columns, policy, k_threshold,
              l_threshold=None, t_threshold=None):
    """一次策略下的完整结论（M2 的唯一对外计算入口）。

    `k_threshold` 必填且为正整数（CLI 层已校验）；`l_threshold` / `t_threshold` 可选。
    """
    require_policy(policy)
    classes, undecided, _ = group_rows(table, qi_columns, policy)
    k = k_of(classes)
    l, l_by_class = l_detail(table, classes, sensitive_columns, policy)
    t, t_by_class = t_detail(table, classes, sensitive_columns, undecided, policy)
    histogram = Counter(len(numbers) for numbers in classes.values())
    violations = _violations(classes, k_threshold, l_threshold, t_threshold, l_by_class, t_by_class)
    unique_records = sorted(
        row_number for numbers in classes.values() if len(numbers) == 1 for row_number in numbers
    )
    missing_class = None
    if MISSING_CLASS_KEY in classes:
        numbers = list(classes[MISSING_CLASS_KEY])
        missing_class = {"k": len(numbers), "row_numbers": numbers}

    if table.row_count == 0:
        undefined_reason = "empty_table"
    elif not classes:
        # 非空表但所有行都因缺失被丢弃：同样算不出 k（不是 k=0，也不是通过）。
        undefined_reason = "no_participating_rows"
    else:
        undefined_reason = None

    if undefined_reason is not None:
        verdict = "undecidable"
    elif violations:
        verdict = "violation"
    else:
        verdict = "pass"

    return {
        "missing_policy": policy,
        "k_l_t": {
            "k": k,
            "l": l,
            "t": t,
            "class_count": len(classes),
            "class_size_histogram": {str(size): histogram[size] for size in sorted(histogram)},
            "undecided_rows": list(undecided),
            "missing_class": missing_class,
        },
        "violations": violations,
        "unique_records": unique_records,
        "undefined_reason": undefined_reason,
        "verdict": verdict,
    }
