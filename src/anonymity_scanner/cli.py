"""命令行入口（CLI 层）：

只做四件事——解析参数、校验输入、分派到模块、把结果/异常映射成退出码。
**不做统计，也不写裁决逻辑**（判据在 `m5_gate`，口径在 `data/README.md` §四）。

骨架期约定：五个子命令在**真正开始计算之前**完成全部输入校验，然后抛 `ModuleNotReady`（退出码 2）。
这样"契约面"（参数形态、缺项、缺策略、坏表）现在就能被测试锁定，而计算面不会用空结果冒充通过。
M2–M5 已落地；仅 `schema`（M1 计算实现）仍按 `MODULE_NOT_READY` fail-closed。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, canonical, m2_classes, m3_search, m4_risk, m5_gate
from .declaration import load_declaration, require_missing_policy
from .exit_codes import (
    CriteriaError,
    DeclarationError,
    ModuleNotReady,
    ScannerError,
    map_outcome,
)
from .report import render_header
from .tableio import read_table

PROG = "anonymity-scanner"


def _ensure_utf8_stdio() -> None:
    """按 stream.encoding 探针决定是否 reconfigure（中文控制台 cp936 保持不动）。

    本机习惯 `py -X utf8` 只改了"我们敲的那条命令"的 stdio，改不了 CI / 子进程通路；
    这里做的是用户侧兜底，不是全局免疫力。
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        encoding = (getattr(stream, "encoding", None) or "").lower()
        if encoding and encoding.replace("-", "") not in ("utf8", "utf8mb4"):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                try:
                    reconfigure(encoding="utf-8", errors="replace")
                except (ValueError, OSError):  # pragma: no cover - 非可重配流
                    pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="匿名性攻击面搜索器：找出「哪几列组合会让 k 崩塌」。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "数值口径与退出码定义见 data/README.md §四；\n"
            "退出码 0 = 通过 / 1 = 有违例 / 2 = 无法裁决（fail-closed）。"
        ),
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    def add_common(sub):
        sub.add_argument("--table", required=True, help="CSV/TSV 表文件")
        sub.add_argument("--decl", required=True, help="列角色声明 JSON")
        sub.add_argument("--out-dir", required=True, help="产物输出目录")
        sub.add_argument("--root", default=None, help="报告中路径的相对化基准（默认当前目录）")

    schema = subparsers.add_parser("schema", help="M1：归一化 schema 与 QI 候选打分")
    add_common(schema)

    scan = subparsers.add_parser("scan", help="M2：等价类引擎（k/l/t + 违例行号）")
    add_common(scan)
    scan.add_argument("--missing-policy", default=None, help="drop | single-column | separate-class（必填）")
    scan.add_argument("--k", type=int, default=None, help="k 门限（必填）")
    scan.add_argument("--l", type=int, default=None, help="可选 l 门限")
    scan.add_argument("--t", type=float, default=None, help="可选 t 门限")

    search = subparsers.add_parser("search", help="M3：组合攻击面搜索（最小崩塌集）")
    add_common(search)
    search.add_argument("--missing-policy", default=None, help="drop | single-column | separate-class（必填）")
    search.add_argument("--k", type=int, default=None, help="k 门限（必填）")
    search.add_argument("--budget", type=int, default=None, help="搜索预算：已评估子集数上限（必填）")
    search.add_argument("--require-exhaustive", action="store_true", help="被预算截断即视为无法裁决（退出码 2）")

    risk = subparsers.add_parser("risk", help="M4：逐记录风险与攻击者模型")
    add_common(risk)
    risk.add_argument("--missing-policy", default=None, help="drop | single-column | separate-class（必填）")
    risk.add_argument("--attacker", default=None, help="prosecutor | journalist | marketer（必填）")

    gate = subparsers.add_parser("gate", help="M5：判据文件驱动的可复算 gate")
    gate.add_argument("--criteria", required=True, help="判据文件 JSON")
    gate.add_argument("--out-dir", required=True, help="产物输出目录")
    gate.add_argument("--root", default=None, help="报告中路径的相对化基准（默认当前目录）")

    return parser


def _resolve_root(raw):
    return Path(raw).resolve() if raw else Path.cwd().resolve()


def _echo_declarations(decl, table, policy, root):
    """报告首屏必须回显四项声明（`plan/01` §六 结论纪律）——骨架期以 stderr 摘要形式给出。"""
    sys.stderr.write("%s %s\n" % (PROG, __version__))
    for line in render_header(decl, table, policy, root):
        sys.stderr.write(line + "\n")


def _prepare(args):
    """公共输入校验：先读表，再验声明。失败一律抛 ScannerError（→ 退出码 2）。"""
    table = read_table(args.table)
    decl = load_declaration(args.decl, table.header)
    if not decl.qi_columns() and args.command in ("scan", "search", "risk"):
        raise DeclarationError(
            "未声明任何 qi 列，无法分组",
            "在声明文件里给参与分组的列标 {\"role\": \"qi\"}",
        )
    return table, decl


def _cmd_schema(args):
    table, decl = _prepare(args)
    _echo_declarations(decl, table, "n/a", _resolve_root(args.root))
    raise ModuleNotReady("M1（角色声明与 QI 候选）", "plan/03 §模块 M1 · 落地里程碑 M1")


def _cmd_scan(args):
    table, decl = _prepare(args)
    policy = require_missing_policy(args.missing_policy)
    if args.k is None:
        raise CriteriaError("k 门限未指定", "scan 需要 --k <正整数>")
    if args.k <= 0:
        raise CriteriaError("k 门限必须是正整数", repr(args.k))
    if args.l is not None and args.l <= 0:
        raise CriteriaError("l 门限必须是正整数", repr(args.l))
    if args.t is not None and not (0.0 <= args.t <= 1.0):
        raise CriteriaError("t 门限必须落在 [0, 1]", repr(args.t))
    sensitive = [column.name for column in decl.sensitive_columns()]
    if (args.l is not None or args.t is not None) and not sensitive:
        raise CriteriaError(
            "声明了 l/t 门限但没有 sensitive 列",
            "l/t 只在 sensitive 列上定义；给至少一列标 {\"role\": \"sensitive\"}",
        )
    root = _resolve_root(args.root)
    _echo_declarations(decl, table, policy, root)

    qi = [column.name for column in decl.qi_columns()]
    result = m2_classes.summarize(
        table, qi, sensitive, policy, args.k, l_threshold=args.l, t_threshold=args.t
    )
    metrics = result["k_l_t"]
    document = {
        "tool": PROG,
        "version": __version__,
        "command": "scan",
        "table": canonical.relativize(table.source, root),
        "rows": table.row_count,
        "columns": list(table.header),
        "qi_columns": qi,
        "sensitive_columns": sensitive,
        "missing_policy": policy,
        "thresholds": {"k": args.k, "l": args.l, "t": args.t},
        "k_l_t": metrics,
        "violations": result["violations"],
        "unique_records": result["unique_records"],
        "unparticipating": decl.unparticipating(),
        "direct_identifier_warning": decl.direct_identifier_warning(),
        "undefined_reason": result["undefined_reason"],
        "verdict": result["verdict"],
        "exit_code": map_outcome(result["verdict"]),
    }
    out_dir = Path(args.out_dir)
    canonical.write_json(out_dir / "scan.json", document)
    sys.stderr.write(
        "scan        : k=%r l=%r t=%r classes=%d violations=%d → %s (exit %d)\n"
        % (
            metrics["k"], metrics["l"], metrics["t"], metrics["class_count"],
            len(result["violations"]), result["verdict"], document["exit_code"],
        )
    )
    return result["verdict"]


def _cmd_search(args):
    table, decl = _prepare(args)
    policy = require_missing_policy(args.missing_policy)
    if args.k is None:
        raise CriteriaError("k 门限未指定", "search 需要 --k <正整数>")
    if args.k <= 0:
        raise CriteriaError("k 门限必须是正整数", repr(args.k))
    if args.budget is None:
        raise CriteriaError("搜索预算未指定", "search 需要 --budget <正整数>；没有预算就不是可复算的搜索")
    if args.budget <= 0:
        raise CriteriaError("搜索预算必须是正整数", repr(args.budget))
    root = _resolve_root(args.root)
    _echo_declarations(decl, table, policy, root)

    qi = [column.name for column in decl.qi_columns()]
    sensitive = [column.name for column in decl.sensitive_columns()]
    result = m3_search.search(
        table, qi, sensitive, policy, args.k,
        budget=args.budget, require_exhaustive=args.require_exhaustive,
    )
    outcome = m3_search.outcome_for(result)
    document = {
        "tool": PROG,
        "version": __version__,
        "command": "search",
        "table": canonical.relativize(table.source, root),
        "rows": table.row_count,
        "columns": list(table.header),
        "sensitive_columns": sensitive,
        "missing_policy": policy,
        "thresholds": {"k": args.k},
        "search": result,
        "outcome": outcome,
        "exit_code": map_outcome(outcome),
        "unparticipating": decl.unparticipating(),
        "direct_identifier_warning": decl.direct_identifier_warning(),
    }
    out_dir = Path(args.out_dir)
    canonical.write_json(out_dir / "search.json", document)
    sys.stderr.write(
        "search      : k=%r budget=%r pool=%d evaluated=%d pruned=%d completeness=%s sets=%d → %s (exit %d)\n"
        % (
            result["threshold"], result["budget"], result["candidate_count"],
            result["evaluated_subsets"], result["pruned_subsets"], result["completeness"],
            len(result["minimal_collapse_sets"]), outcome, document["exit_code"],
        )
    )
    if result["non_exhaustive"]:
        # `data/README.md` §4.5：非穷尽时结果不得称"最小崩塌集"。
        sys.stderr.write(
            "collapse    : %s（非穷尽结果，不是最小崩塌集；状态 %s）\n"
            % (result["collapse_sets_status"], result["completeness"])
        )
    return outcome


def _cmd_risk(args):
    table, decl = _prepare(args)
    policy = require_missing_policy(args.missing_policy)
    allowed = m4_risk.ATTACKERS
    if args.attacker is None:
        raise CriteriaError("攻击者模型未指定", "risk 需要 --attacker（%s 之一）" % " / ".join(allowed))
    if args.attacker not in allowed:
        raise CriteriaError("未知的攻击者模型", "%r（可选 %s）" % (args.attacker, " / ".join(allowed)))
    root = _resolve_root(args.root)
    _echo_declarations(decl, table, policy, root)

    qi = [column.name for column in decl.qi_columns()]
    sensitive = [column.name for column in decl.sensitive_columns()]
    result = m4_risk.risk(table, qi, policy, args.attacker)
    document = {
        "tool": PROG,
        "version": __version__,
        "command": "risk",
        "table": canonical.relativize(table.source, root),
        "rows": table.row_count,
        "columns": list(table.header),
        "qi_columns": qi,
        "sensitive_columns": sensitive,
        "missing_policy": policy,
        "attacker": result["attacker"],
        "threshold": result["threshold"],
        "rule": result["rule"],
        "class_count": result["class_count"],
        "records": result["records"],
        "flagged_rows": result["flagged_rows"],
        "by_class_size": result["by_class_size"],
        "unparticipating": decl.unparticipating(),
        "direct_identifier_warning": decl.direct_identifier_warning(),
        "undefined_reason": result["undefined_reason"],
        "verdict": result["verdict"],
        "exit_code": map_outcome(result["verdict"]),
    }
    out_dir = Path(args.out_dir)
    canonical.write_json(out_dir / "risk.json", document)
    sys.stderr.write(
        "risk        : attacker=%s rule=%s classes=%d flagged=%d/%d → %s (exit %d)\n"
        % (
            result["attacker"], result["rule"], result["class_count"],
            len(result["flagged_rows"]), table.row_count,
            result["verdict"], document["exit_code"],
        )
    )
    if result["undefined_reason"] is not None:
        sys.stderr.write("risk        : undefined_reason=%s（无法裁决，不是通过）\n" % result["undefined_reason"])
    return result["verdict"]


def _cmd_gate(args):
    # 判据解析只有一处（m5_gate.load_criteria）——CLI 不再自己读 JSON。
    criteria = m5_gate.load_criteria(args.criteria)
    # 判据里的相对路径以判据文件所在目录为基准解析——判据是政策输入，必须自包含、可搬移。
    base = Path(criteria["base"])
    table_path = Path(criteria["table"])
    if not table_path.is_absolute():
        table_path = base / table_path
    decl_path = Path(criteria["declaration"])
    if not decl_path.is_absolute():
        decl_path = base / decl_path
    table = read_table(table_path)
    decl = load_declaration(decl_path, table.header)
    if not decl.qi_columns():
        raise DeclarationError("未声明任何 qi 列，无法分组", "判据文件引用的声明里没有任何 qi 列")
    root = _resolve_root(args.root)
    _echo_declarations(decl, table, criteria["missing_policy"], root)

    document = m5_gate.evaluate(
        table,
        decl,
        criteria,
        table_label=canonical.relativize(table.source, root),
        criteria_label=canonical.relativize(Path(args.criteria).resolve(), root),
    )
    out_dir = Path(args.out_dir)
    canonical.write_json(out_dir / "gate.json", document)
    canonical.write_text_atomic(out_dir / "gate.md", m5_gate.render_markdown(document))
    sys.stderr.write(
        "gate        : policy=%s k=%r l=%r t=%r search=%s violations=%d → %s (exit %d)\n"
        % (
            document["declarations"]["missing_policy"],
            document["declarations"]["thresholds"]["k"],
            document["declarations"]["thresholds"]["l"],
            document["declarations"]["thresholds"]["t"],
            document["declarations"]["search"]["enabled"],
            len(document["violations"]),
            document["outcome"], document["exit_code"],
        )
    )
    if document["undefined_reason"] is not None:
        sys.stderr.write(
            "gate        : undefined_reason=%s（无法裁决，不是通过）\n" % document["undefined_reason"]
        )
    return document["outcome"]


_HANDLERS = {
    "schema": _cmd_schema,
    "scan": _cmd_scan,
    "search": _cmd_search,
    "risk": _cmd_risk,
    "gate": _cmd_gate,
}


def main(argv=None) -> int:
    _ensure_utf8_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help(sys.stderr)
        return map_outcome("undecidable")  # 没给子命令 = 无从裁决，不是"通过"
    handler = _HANDLERS.get(args.command)
    if handler is None:  # pragma: no cover - argparse 已拦截
        sys.stderr.write("未知子命令: %r\n" % (args.command,))
        return map_outcome("undecidable")
    try:
        outcome = handler(args)
    except ScannerError as exc:
        sys.stderr.write("%s: %s\n" % (type(exc).__name__, exc))
        return map_outcome(exc)
    except KeyboardInterrupt:  # pragma: no cover
        sys.stderr.write("interrupted\n")
        return map_outcome("undecidable")
    except Exception as exc:  # 内部错误绝不退化为 0
        sys.stderr.write("internal error: %r\n" % (exc,))
        return map_outcome("undecidable")
    # 计算面落地的子命令返回真实结论；其余（尚未落地）只会抛异常，走到这里时按"通过"处理。
    return map_outcome("pass" if outcome is None else outcome)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
