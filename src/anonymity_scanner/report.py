"""人读报告渲染（M5 的 `gate.md` 与各子命令的首屏摘要共用）。

三条纪律（K7 / D7）：
  * **不含时间戳、主机名、绝对路径**——路径经 `canonical.relativize()` 相对化。
  * 首屏必须回显四项声明（角色 / 缺失策略 / 阈值 / 预算），禁止脱离上下文引用数字。
  * 渲染是**纯函数**：同输入 → 同字符串（不读时钟、不读环境变量）。
"""
from __future__ import annotations

from .canonical import relativize


def render_header(decl, table, missing_policy, root) -> list:
    """首屏声明回显。返回行列表（调用方决定写 stderr 还是落 md）。"""
    qi = [c.name for c in decl.qi_columns()]
    sensitive = [c.name for c in decl.sensitive_columns()]
    lines = [
        "table       : %s (%d 行 × %d 列)"
        % (relativize(table.source, root), table.row_count, len(table.header)),
        "qi columns  : %s" % (", ".join(qi) if qi else "(none)"),
        "sensitive   : %s" % (", ".join(sensitive) if sensitive else "(none)"),
        "missing     : %s" % missing_policy,
    ]
    direct = decl.direct_identifier_warning()
    if direct:
        lines.append(
            "direct-id   : %s（默认不参与 k/l/t；若该列泄露，行即被直接重识别）" % ", ".join(direct)
        )
    unparticipating = decl.unparticipating()
    if unparticipating:
        lines.append(
            "unused cols : %s"
            % ", ".join("%s(%s)" % (item["column"], item["reason"]) for item in unparticipating)
        )
    return lines
