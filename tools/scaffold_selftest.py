"""脚手架自检：安装形态、版本一致性、口径单点。

用法：py -3.12 tools/scaffold_selftest.py
退出码：0 全绿 / 1 有 FAIL。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anonymity_scanner import __version__  # noqa: E402
from anonymity_scanner import canonical, declaration, exit_codes, tableio  # noqa: E402


def main() -> int:
    results = []

    def check(name, ok, detail):
        results.append((name, bool(ok), detail))

    # 1. 版本号单点：pyproject 用 dynamic attr，不得出现手抄的 version = "x.y.z"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    check(
        "VERSION.SINGLE_SOURCE",
        'version = {attr = "anonymity_scanner.__version__"}' in pyproject
        and not re.search(r'^version\s*=\s*"[0-9]', pyproject, re.M),
        "pyproject 用 dynamic attr，无手抄版本",
    )

    # 2. 零运行时依赖
    block = pyproject.split("dependencies = [", 1)[-1].split("]", 1)[0]
    check("DEPS.ZERO_RUNTIME", block.strip() == "", "运行时依赖为空: %r" % block.strip())

    # 3. 契约入口可达
    from anonymity_scanner.cli import _build_parser

    names = sorted(_build_parser()._subparsers._group_actions[0].choices)  # noqa: SLF001
    check(
        "CLI.SUBCOMMANDS",
        names == ["gate", "risk", "scan", "schema", "search"],
        "子命令: %s" % ",".join(names),
    )

    # 4. 退出码映射单点 + 闭合
    table = {
        "pass": 0,
        "violation": 1,
        "undecidable": 2,
        "": 2,
        None: 2,
        "something-unknown": 2,
    }
    bad = {k: (v, exit_codes.map_outcome(k)) for k, v in table.items() if exit_codes.map_outcome(k) != v}
    mapped = sorted({v for v in (exit_codes.map_outcome(k) for k in table)} | {exit_codes.UNDECIDABLE})
    check("EXIT.SINGLE_MAP", not bad and mapped == [0, 1, 2], "异常映射: %s" % (bad or "无"))

    # 5. 序列化冻结参数
    text = canonical.dumps({"b": 1, "a": canonical.round6(0.1234565)})
    check(
        "CANONICAL.FROZEN",
        text == '{\n  "a": 0.123456,\n  "b": 1\n}\n',
        "序列化输出: %r" % text,
    )
    check(
        "CANONICAL.ROUND_HALF_EVEN",
        canonical.round6(0.0000005) == 0.0 and canonical.round6(0.0000015) == 0.000002,
        "半偶舍入: 0.0000005→%r, 0.0000015→%r"
        % (canonical.round6(0.0000005), canonical.round6(0.0000015)),
    )

    # 6. 缺失值集合单点
    check(
        "MISSING.SINGLE_SOURCE",
        "def missing_set()" in (ROOT / "src" / "anonymity_scanner" / "tableio.py").read_text(encoding="utf-8")
        and tableio.is_missing("") and tableio.is_missing("NA") and not tableio.is_missing("na"),
        "缺失集合: %s" % ",".join(sorted(tableio.missing_set())),
    )

    # 7. 缺失策略无默认值
    try:
        declaration.require_missing_policy(None)
        ok = False
    except exit_codes.CriteriaError:
        ok = True
    check("MISSING_POLICY.NO_DEFAULT", ok, "None → CriteriaError")

    # 8. 版本身份可读
    check("VERSION.FORMAT", re.match(r"^\d+\.\d+\.\d+$", __version__) is not None, __version__)

    width = max(len(r[0]) for r in results)
    for name, ok, detail in results:
        sys.stdout.write("%-4s  %-*s  %s\n" % ("PASS" if ok else "FAIL", width, name, detail))
    failed = [r for r in results if not r[1]]
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("结论: %s\n" % ("全绿" if not failed else "%d 项 FAIL" % len(failed)))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
