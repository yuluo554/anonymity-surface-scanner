"""列角色声明（M1 的输入端）。

角色枚举是闭合集合（`data/README.md` §4.1）：qi / sensitive / direct-identifier / date-precision。
**未声明即不参与**——本模块不做任何"猜它可能是 QI"的自动纳入（D2）。
"""
from __future__ import annotations

import json
from pathlib import Path

from .exit_codes import DeclarationError

ROLES = ("qi", "sensitive", "direct-identifier", "date-precision")
PRECISIONS = ("year", "month", "day")
TOP_LEVEL_KEYS = frozenset(["columns"])
COLUMN_KEYS = {
    "qi": frozenset(["role"]),
    "sensitive": frozenset(["role"]),
    "direct-identifier": frozenset(["role"]),
    "date-precision": frozenset(["role", "precision"]),
}


class ColumnDeclaration(object):
    __slots__ = ("name", "role", "precision", "order")

    def __init__(self, name: str, role: str, precision=None, order: int = 0) -> None:
        self.name = name
        self.role = role
        self.precision = precision
        self.order = order

    def as_dict(self):
        out = {"role": self.role}
        if self.precision is not None:
            out["precision"] = self.precision
        return out

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return "ColumnDeclaration(%r, %r, %r)" % (self.name, self.role, self.precision)


class Declaration(object):
    """不可变的声明集合。`qi_columns()` 的顺序 = 声明文件里的书写顺序（即等价类键序）。"""

    __slots__ = ("columns", "table_columns")

    def __init__(self, columns, table_columns) -> None:
        self.columns = tuple(columns)  # 按声明文件书写顺序
        self.table_columns = tuple(table_columns)

    def by_role(self, role: str):
        return [c for c in self.columns if c.role == role]

    def qi_columns(self):
        """声明为 qi 的列，**按声明书写顺序**。

        `date-precision` 列只是标注粒度，不自动成为 QI（D2：不猜、不自动改角色）；
        要它参与键，必须在声明里同时出现该列的 qi 声明——当前格式每列只能有一个角色，
        因此日期列参与键的做法是：把该列声明为 `qi` 并在 `precision` 上标注粒度。
        """
        return [c for c in self.columns if c.role == "qi"]

    def sensitive_columns(self):
        return [c for c in self.columns if c.role == "sensitive"]

    def unparticipating(self):
        """未参与 k/l/t 的列：未声明的 + direct-identifier 的（附原因）。"""
        declared = {c.name for c in self.columns}
        out = []
        for name in self.table_columns:
            if name not in declared:
                out.append({"column": name, "reason": "undeclared"})
        for col in self.by_role("direct-identifier"):
            out.append({"column": col.name, "reason": "direct-identifier"})
        for col in self.by_role("date-precision"):
            out.append({"column": col.name, "reason": "date-precision-only"})
        return out

    def direct_identifier_warning(self):
        return [c.name for c in self.by_role("direct-identifier")]


def load_declaration(path, table_columns):
    """读取并校验声明文件。任何不合规都抛 `DeclarationError`（退出码 2）。"""
    target = Path(path)
    if not target.is_file():
        raise DeclarationError("声明文件不存在", str(target))
    raw = target.read_text(encoding="utf-8-sig")
    try:
        document = json.loads(raw)
    except ValueError as exc:
        raise DeclarationError("声明文件不是合法 JSON", str(exc))
    if not isinstance(document, dict):
        raise DeclarationError("声明文件顶层必须是对象")
    unknown_top = sorted(set(document) - TOP_LEVEL_KEYS)
    if unknown_top:
        raise DeclarationError("声明文件有未知顶层键", ", ".join(unknown_top))
    columns = document.get("columns")
    if not isinstance(columns, dict) or not columns:
        raise DeclarationError("声明文件缺 `columns` 对象（或为空）")

    table_set = set(table_columns)
    missing_in_table = sorted(name for name in columns if name not in table_set)
    if missing_in_table:
        raise DeclarationError("声明了表中不存在的列", ", ".join(missing_in_table))

    parsed = []
    for order, (name, spec) in enumerate(columns.items()):
        if not isinstance(spec, dict):
            raise DeclarationError("列声明必须是对象", name)
        role = spec.get("role")
        if role not in ROLES:
            raise DeclarationError("角色不在枚举内", "%s → %r（可选 %s）" % (name, role, "/".join(ROLES)))
        unknown = sorted(set(spec) - COLUMN_KEYS[role])
        if unknown:
            raise DeclarationError("列声明有该角色不允许的键", "%s → %s" % (name, ", ".join(unknown)))
        precision = None
        if role == "date-precision":
            precision = spec.get("precision")
            if precision not in PRECISIONS:
                raise DeclarationError(
                    "date-precision 列必须声明 precision", "%s → %r（可选 %s）" % (name, precision, "/".join(PRECISIONS))
                )
        parsed.append(ColumnDeclaration(name, role, precision, order))

    return Declaration(parsed, table_columns)


def require_missing_policy(value):
    """缺失策略无默认值：未指定即报错（`data/README.md` §4.4）。"""
    from .exit_codes import CriteriaError

    allowed = ("drop", "single-column", "separate-class")
    if value is None:
        raise CriteriaError(
            "缺失值策略未指定",
            "必须显式给出 --missing-policy（%s 之一）；本工具不猜、不设默认。" % " / ".join(allowed),
        )
    if value not in allowed:
        raise CriteriaError("未知的缺失值策略", "%r（可选 %s）" % (value, " / ".join(allowed)))
    return value
