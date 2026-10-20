"""组合攻击面搜索（M3）：子集枚举、反单调剪枝、预算、最小崩塌集、完整性三态。

口径唯一出处：`data/README.md` §4.5（下文逐条对应）。纪律：

  * **纯函数**（K8）：不写盘、不读时钟 / 随机源 / 环境变量、不 import `cli`。
  * **分组只走 M2**（K1）：`m2_classes.group_rows` / `k_of` 是分组与 k 的唯一实现，
    本模块不再写一份等价类 / 缺失判定。
  * **候选池 = 声明为 qi 的列**（当前 CLI 契约）；枚举按子集大小升序，同大小按列名码位序。
  * **单调性前提**（K5）：`drop` 且候选池含缺失 → 加列会改变参与分组的行集，
    `k(S ∪ {c}) ≤ k(S)` 不再由定义保证 → `monotonicity-not-applicable` 且**不剪枝**。
  * **完整性三态闭合互斥**：`completeness()` 是唯一判定点；`non_exhaustive` 与
    `collapse_sets_status` 都由它派生（非穷尽时不得称"最小崩塌集"）。
  * 预算按**已评估子集数**计数（含空集）；剪枝与预算分开计数，绝不混为一谈。

边界语义（`plan/00` 勘误 E2）：

  * 空集不安全（参与分组的行数 < 阈值）或候选池为空 → `verdict = "no_solution"`；
  * 没有任何单列安全 → 空集是边界集 → `minimal_collapse_sets: [[]]` + `empty_set_witness: true`，
    语义 = **一个 QI 列都不能加**（不是"什么都不用声明"）。
"""
from __future__ import annotations

from itertools import combinations

from .exit_codes import CriteriaError
from .m2_classes import group_rows, k_of, require_policy
from .tableio import is_missing

# 完整性三态（`data/README.md` §4.5）：闭合集合，互斥。
COMPLETENESS_STATES = ("exhausted", "budget-truncated", "monotonicity-not-applicable")


def _require_positive_int(label, value):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CriteriaError("%s必须是正整数" % label, repr(value))
    return value


def monotonicity_holds(table, pool, policy):
    """单调性前提（§4.5 / §4.4 末条）：`drop` 下候选池含缺失即不成立。

    只看**本次候选池**：空集没有列参与分组，故空集的 k 不受缺失影响；
    一旦把含缺失的列加进 S，含缺失的行就会被丢弃，行集改变。
    """
    require_policy(policy)
    if policy != "drop":
        return True
    for name in pool:
        if any(is_missing(value) for value in table.values(name)):
            return False
    return True


def completeness(monotone, exhausted, required=True):
    """完整性三态的唯一判定点（K5）。

    * 预算截断优先：存在"本应评估但没评估"的子集 → `budget-truncated`；
    * `required=False`（无解：就连空集都不安全，没有任何子集需要评估）→ `exhausted`，
      这与真值一致：没有枚举就没有"未评估"，也没必要再谈单调性；
    * 否则单调性不成立 → `monotonicity-not-applicable`；
    * 两者都不触发 → `exhausted`。
    """
    if not exhausted:
        return "budget-truncated"
    if not required:
        return "exhausted"
    if not monotone:
        return "monotonicity-not-applicable"
    return "exhausted"


def collapse_sets_status(completeness_state):
    """真值 `collapse_sets_status` 的同口径派生：只有 `exhausted` 才敢写 `exhaustive`。"""
    return "exhaustive" if completeness_state == "exhausted" else "non-exhaustive"


def _exposed_rows(classes, threshold):
    """落入 `k < threshold` 的等价类中的行数（§M3 输出项 3）。

    `drop` 下未参与分组的行不在任何类里，因此既不计入"暴露"也不计入"受保护"。
    """
    return sum(len(numbers) for numbers in classes.values() if len(numbers) < threshold)


def search(table, pool, sensitive, policy, threshold, budget=None, require_exhaustive=False):
    """求候选池上的崩塌边界集（= 最小崩塌集的本项目口径）。

    `sensitive` 是为 M5 复用预留的位置：当前 `search` 只按 k 判定（l/t 门限未接入
    `search` 的 CLI 契约），因此它不参与计算，也不影响任何数值。

    返回的 `verdict` 与真值同口径：`"ok"`（搜索完成，无论是否找到边界集）或
    `"no_solution"`（空集自身不安全 / 候选池为空）。退出码由 CLI 按 §4.6 另行映射
    （`search.json` 里的 `outcome`）——搜索结论不是隐私裁决本身。

    `evaluated_subsets` 只统计**本次搜索实算过的子集**（含空集）；为给出
    `declared_k` 而对完整声明集合做的单独计算**不计入**其中，也不进 `subsets` 清单。
    """
    require_policy(policy)
    _require_positive_int("k 门限", threshold)
    if budget is not None:
        _require_positive_int("搜索预算", budget)
    candidates = sorted(pool)
    if len(set(candidates)) != len(candidates):
        raise CriteriaError("候选池里有重复列", ", ".join(sorted({n for n in candidates if candidates.count(n) > 1})))

    monotone = monotonicity_holds(table, candidates, policy)
    cache = {}          # 子集 -> k（实算过的）
    classes_cache = {}  # 子集 -> 等价类（供暴露行数与分层曲线复用）
    pruned = set()      # 单调性下因父集不安全而跳过的子集
    exhausted = True

    def k_for(combo):
        combo = tuple(combo)
        if combo in pruned:
            return None
        if combo not in cache:
            classes, _undecided, _values = group_rows(table, list(combo), policy)
            cache[combo] = k_of(classes)
            classes_cache[combo] = classes
        return cache[combo]

    def is_safe(combo):
        combo = tuple(combo)
        if combo in pruned:
            return False
        value = k_for(combo)
        return value is not None and value >= threshold

    def budget_hit():
        return budget is not None and len(cache) >= budget

    base = k_for(())
    subset_space = 2 ** len(candidates) - 1

    if not candidates or base is None or base < threshold:
        # 无解：空集本身不安全时，任何超集只会更小（或同样 undefined）→ 不存在安全集合。
        # 单调性不适用也在这里提前返回：没有枚举，就没有"未评估"的子集。
        minimal_collapse_sets = []
        verdict = "no_solution"
        state = completeness(monotone, True, required=False)
    else:
        for size in range(1, len(candidates) + 1):
            for combo in combinations(candidates, size):
                if monotone:
                    # 父集不安全 ⇒ 超集必不安全（只增加分组列的语义）。
                    if any(not is_safe(parent) for parent in combinations(combo, size - 1)):
                        pruned.add(combo)
                        continue
                if budget_hit():
                    exhausted = False
                    break
                is_safe(combo)
            if not exhausted:
                break

        safe_sets = {combo for combo, value in cache.items() if value is not None and value >= threshold}
        minimal_collapse_sets = []
        for combo in sorted(safe_sets, key=lambda item: (len(item), item)):
            if any(
                tuple(sorted(combo + (column,))) in safe_sets
                for column in candidates
                if column not in combo
            ):
                continue
            # 单调性不成立时，扩展可能没算过 → 不得断言它不安全（跳过该 S）。
            if not monotone:
                unevaluated = any(
                    tuple(sorted(combo + (column,))) not in cache
                    for column in candidates
                    if column not in combo
                )
                if unevaluated:
                    continue
            minimal_collapse_sets.append(list(combo))
        verdict = "ok"
        state = completeness(monotone, exhausted)

    if require_exhaustive and state == "budget-truncated":
        raise CriteriaError(
            "搜索被预算截断，无法声称穷尽",
            "提高 --budget 或缩小候选池；--require-exhaustive 下截断结果不能当结论",
        )

    # 分层曲线（§M3 输出项 2）：只聚合实算过的子集；同层 min_k 相同时取字典序最小的子集，
    # 让 exposed_rows 与 worst_subset 一一对应、可复算。
    levels = {}
    for combo in sorted(cache, key=lambda item: (len(item), item)):
        size = len(combo)
        level = levels.setdefault(size, {"size": size, "evaluated": 0, "min_k": None, "worst_subset": None})
        level["evaluated"] += 1
        value = cache[combo]
        if value is not None and (level["min_k"] is None or value < level["min_k"]):
            level["min_k"] = value
            level["worst_subset"] = list(combo)

    strata = []
    for size in sorted(levels):
        level = levels[size]
        worst = tuple(level["worst_subset"]) if level["worst_subset"] is not None else None
        strata.append({
            "size": size,
            "evaluated": level["evaluated"],
            "min_k": level["min_k"],
            "exposed_rows": _exposed_rows(classes_cache[worst], threshold) if worst is not None else 0,
            "worst_subset": level["worst_subset"],
        })

    # 每个被评估子集的结论（§M3 输出项 3），按枚举顺序（大小升序、同大小码位序）。
    subsets = []
    for combo in sorted(cache, key=lambda item: (len(item), item)):
        value = cache[combo]
        subsets.append({
            "columns": list(combo),
            "k": value,
            "safe": value is not None and value >= threshold,
            "exposed_rows": _exposed_rows(classes_cache[combo], threshold),
        })

    # 声明集合本身的 k：用于 §4.6 的退出码（"所有声明阈值是否满足"）。
    # 它可能因剪枝/预算从未进入 cache，因此单独计算；不计入 evaluated_subsets。
    declared = tuple(candidates)
    if declared in cache:
        declared_k = cache[declared]
    else:
        declared_classes, _undecided, _values = group_rows(table, list(declared), policy)
        declared_k = k_of(declared_classes)

    return {
        "verdict": verdict,
        "completeness": state,
        "collapse_sets_status": collapse_sets_status(state),
        "non_exhaustive": state != "exhausted",
        "minimal_collapse_sets": minimal_collapse_sets,
        "empty_set_witness": [] in minimal_collapse_sets,
        "empty_set_k": base,
        "declared_k": declared_k,
        "candidate_count": len(candidates),
        "subset_space": subset_space,
        "budget": budget,
        "monotonicity_applicable": monotone,
        "evaluated_subsets": len(cache),
        "pruned_subsets": len(pruned),
        "pool": candidates,
        "qi_columns": list(pool),
        "policy": policy,
        "threshold": threshold,
        "strata": strata,
        "subsets": subsets,
    }


def outcome_for(result):
    """把搜索结论映射为 §4.6 的 CLI 结论（`pass` / `violation` / `undecidable`）。

    判据 = **声明集合本身**的 k（搜索是诊断，不是隐私裁决）：

      * `declared_k is None`（没有参与分组的行）→ `undecidable`；
      * `declared_k < threshold` → `violation`（声明阈值确实被打破，搜索已定位边界）；
      * 满足阈值但完整性不是 `exhausted` → `undecidable`（§4.6：0 要求穷尽，
        非穷尽结果不得冒充通过）；
      * 其余 → `pass`。
    """
    declared_k = result["declared_k"]
    if declared_k is None:
        return "undecidable"
    if declared_k < result["threshold"]:
        return "violation"
    if result["completeness"] != "exhausted":
        return "undecidable"
    return "pass"
