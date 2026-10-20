"""逐记录风险与攻击者模型（M4）。

口径出处只有一处：`data/README.md` §4.8（K11）。判定**只依赖等价类大小**，与敏感列取值无关。
分组与缺失判定复用 M2（K1）：本模块只调用 `m2_classes.group_rows` / `require_policy`，
不另写一份分组或缺失判定。

纪律（`plan/03 §模块 M4`、K7 / K8）：
  * **纯函数**：不写盘、不读时钟/随机源、不 import `cli`。
  * 记录按**行号升序**输出（行号语义见 K6）；每条记录都出现——`drop` 下未裁决的行
    也必须以 `participates: false` + `class_id: null` 显式出现，不得静默消失。
  * 空表 / 无参与分组的行 → `undefined_reason` + `verdict = "undecidable"`，绝不返回 `pass`。
  * `separate-class` 的缺失类键 = `m2_classes.MISSING_CLASS_KEY`，类大小照常参与判定。

三口径阈值（`data/README.md` §4.8 原表；改这里 = 口径变更）：
    prosecutor → class_size == 1
    journalist → class_size <= 2
    marketer   → class_size <  3
"""
from __future__ import annotations

import operator

from .exit_codes import CriteriaError
from .m2_classes import MISSING_CLASS_KEY, group_rows, require_policy

#: 攻击者模型枚举（顺序即 `--attacker` 帮助文案顺序）。
ATTACKERS = ("prosecutor", "journalist", "marketer")

#: 口径 → (比较符, 阈值)。比较符与阈值**写死在这张表里**，与 §4.8 一一对应。
ATTACKER_RULES = {
    "prosecutor": ("==", 1),
    "journalist": ("<=", 2),
    "marketer": ("<", 3),
}

_OPERATORS = {"==": operator.eq, "<=": operator.le, "<": operator.lt}

#: 单条记录的未裁决原因（只用于 `drop` 下含缺失 QI 的行；全局原因见 `undefined_reason`）。
UNDECIDED_ROW_REASON = "missing_value_in_qi"


def require_attacker(attacker):
    """纯函数层的攻击者校验；CLI 层另有一份同口径校验（早于计算、消息更具体）。"""
    if attacker not in ATTACKERS:
        raise CriteriaError(
            "未知的攻击者模型", "%r（可选 %s）" % (attacker, " / ".join(ATTACKERS))
        )
    return attacker


def rule_for(attacker):
    """返回该口径的判定规则（比较符 + 阈值）；`rule_text` 供人读报告与 stderr 使用。"""
    require_attacker(attacker)
    return ATTACKER_RULES[attacker]


def rule_text(attacker):
    """人读规则文本，例如 ``class_size <= 2``。"""
    compare, threshold = rule_for(attacker)
    return "class_size %s %d" % (compare, threshold)


def is_flagged(class_size, attacker):
    """单类判定：该类里的每条记录是否被该口径识别/锁定。"""
    compare, threshold = rule_for(attacker)
    return bool(_OPERATORS[compare](class_size, threshold))


def classify(classes, attacker):
    """每类判定（M4 的唯一判定实现）。

    返回按 `(class_size, class_id)` 升序排列的列表；每项：
    ``{"class_id": 键, "class_size": 类大小, "flagged": 是否命中口径}``。
    """
    require_attacker(attacker)
    rows = [
        {
            "class_id": key,
            "class_size": len(numbers),
            "flagged": is_flagged(len(numbers), attacker),
        }
        for key, numbers in classes.items()
    ]
    rows.sort(key=lambda item: (item["class_size"], item["class_id"]))
    return rows


def _by_class_size(judgements):
    """类大小直方图：每个大小给出类数 / 记录数 / 命中记录数（只列出现的大小）。"""
    histogram = {}
    for item in judgements:
        size = item["class_size"]
        bucket = histogram.setdefault(
            str(size), {"classes": 0, "records": 0, "flagged_records": 0}
        )
        bucket["classes"] += 1
        bucket["records"] += size
        if item["flagged"]:
            bucket["flagged_records"] += size
    return histogram


def risk(table, pool, policy, attacker):
    """一次策略 + 一个口径下的逐记录风险（M4 的唯一对外计算入口）。

    返回 ``attacker`` / ``threshold`` / ``rule`` / ``missing_policy`` / ``class_count`` /
    ``records`` / ``flagged_rows`` / ``by_class_size`` / ``undefined_reason`` / ``verdict``。
    """
    require_policy(policy)
    require_attacker(attacker)
    _, threshold = rule_for(attacker)

    classes, _undecided, _ = group_rows(table, pool, policy)
    judgements = classify(classes, attacker)
    by_key = {item["class_id"]: item for item in judgements}
    row_class = {}
    for key, numbers in classes.items():
        for row_number in numbers:
            row_class[row_number] = key

    records = []
    for row_number, _values in table.rows:
        key = row_class.get(row_number)
        if key is None:
            records.append(
                {
                    "row_number": row_number,
                    "class_id": None,
                    "class_size": None,
                    "flagged": False,
                    "attacker": attacker,
                    "participates": False,
                    "undefined_reason": UNDECIDED_ROW_REASON,
                }
            )
            continue
        judgement = by_key[key]
        records.append(
            {
                "row_number": row_number,
                "class_id": key,
                "class_size": judgement["class_size"],
                "flagged": judgement["flagged"],
                "attacker": attacker,
                "participates": True,
                "undefined_reason": None,
            }
        )

    if table.row_count == 0:
        undefined_reason = "empty_table"
    elif not classes:
        # 非空表但所有行都因缺失被丢弃：没有任何类可评估 → 无法裁决（不是 pass）。
        undefined_reason = "no_participating_rows"
    else:
        undefined_reason = None

    flagged_rows = [record["row_number"] for record in records if record["flagged"]]
    if undefined_reason is not None:
        verdict = "undecidable"
    elif flagged_rows:
        verdict = "violation"
    else:
        verdict = "pass"

    return {
        "attacker": attacker,
        "threshold": threshold,
        "rule": rule_text(attacker),
        "missing_policy": policy,
        "pool": list(pool),
        "class_count": len(classes),
        "records": records,
        "flagged_rows": flagged_rows,
        "by_class_size": _by_class_size(judgements),
        "undefined_reason": undefined_reason,
        "verdict": verdict,
    }


__all__ = [
    "ATTACKERS",
    "ATTACKER_RULES",
    "MISSING_CLASS_KEY",
    "UNDECIDED_ROW_REASON",
    "classify",
    "is_flagged",
    "require_attacker",
    "risk",
    "rule_for",
    "rule_text",
]
