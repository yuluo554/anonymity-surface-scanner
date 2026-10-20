"""退出码与错误分类（`data/README.md` §4.6 是本项目退出码的唯一出处）。

**唯一的映射函数** `map_outcome()`。测试直接断言它，CLI 只调用它——不做第二套映射。
"""
from __future__ import annotations

PASS = 0
VIOLATION = 1
UNDECIDABLE = 2


class ScannerError(Exception):
    """所有可预期失败的基类。默认语义 = 无法裁决（2），**绝不**退化为 0。"""

    code = UNDECIDABLE

    def __init__(self, message: str, detail=None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        if self.detail:
            return "%s: %s" % (self.message, self.detail)
        return self.message


class InputError(ScannerError):
    """表格无法读取或形态不符（缺列、宽度不符、编码错误、空文件）。"""


class DeclarationError(ScannerError):
    """列角色声明无效（未知列、角色不在枚举、日期精度缺失）。"""


class CriteriaError(ScannerError):
    """判据文件无效或不足以裁决（缺项、类型不符、缺缺失策略）。"""


class ModuleNotReady(ScannerError):
    """模块尚未实现。骨架期用这个码拦截，**不伪造空结果**；模块落地后整项退役。"""

    def __init__(self, module: str, location: str) -> None:
        super().__init__(
            "MODULE_NOT_READY",
            "%s 尚未实现（见 %s）。本工具不会用空结果冒充通过。" % (module, location),
        )
        self.module = module
        self.location = location


def map_outcome(outcome):
    """把结论映射到退出码。**只此一处**。

    outcome 取值：
      * ``"pass"`` → 0
      * ``"violation"`` → 1
      * ``"undecidable"`` 或任何 ``ScannerError`` → 2

    未知取值一律按 2 处理（fail-closed：不认识就不许判通过）。
    """
    if isinstance(outcome, ScannerError):
        return outcome.code
    if outcome == "pass":
        return PASS
    if outcome == "violation":
        return VIOLATION
    return UNDECIDABLE
