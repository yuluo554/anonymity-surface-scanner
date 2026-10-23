"""sdist 自足性守门（D1 回归）。

`v0.1.0` 的源码包解包后跑它自带的 pytest 是 **102 failed**：`tests/conftest.py`、
`data/fixtures/**`、`examples/adult/*` 都不在包里。原因不是打包钩子写错，而是
`MANIFEST.in` 只有 7 行 —— `test_*.py` 由 setuptools 默认规则顺带收进 sdist，
`conftest.py` 不匹配该模式，于是整片测试在解包树里 import 失败。

本文件把「哪三条规则必须在」钉成判据，同时守住反向红线：**不许用裸通配目录**，
否则本机 `examples/adult/adult.csv`（3.4 MB UCI Adult）会被打进发布物。

判据只读 `MANIFEST.in` 文本，不建包、不联网 —— 在 sdist 解包树里同样成立。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "MANIFEST.in"

# 用户解包源码包后必须能跑起来的三类文件。
REQUIRED_RULES = (
    ("recursive-include", "tests", "*.py"),
    ("recursive-include", "data/fixtures", "*.json"),
    ("recursive-include", "examples", "*.sh"),
)


def _rules():
    """把 MANIFEST.in 解析成 (指令, 目录, 后缀集合) 的列表，忽略注释与空行。"""
    rules = []
    for raw in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] in ("recursive-include", "recursive-exclude") and len(parts) >= 3:
            rules.append((parts[0], parts[1], set(parts[2:])))
    return rules


def test_manifest_in_exists_and_is_nonempty():
    assert MANIFEST.is_file(), "MANIFEST.in 缺失：sdist 会退化成 setuptools 默认规则"
    assert _rules(), "MANIFEST.in 里没有任何 recursive-include/exclude 规则"


def test_manifest_covers_self_contained_test_surface():
    """三条规则缺一不可：conftest、真值 json、示例脚本。"""
    rules = _rules()
    for directive, directory, pattern in REQUIRED_RULES:
        matched = any(
            d == directive and dirname == directory and pattern in patterns
            for d, dirname, patterns in rules
        )
        assert matched, "MANIFEST.in 缺规则：%s %s %s" % (directive, directory, pattern)


def test_manifest_never_uses_bare_directory_wildcard():
    """反向红线：`recursive-include examples *` 会把 3.4 MB 表格打进 sdist。

    表格本体（*.csv / *.data / *.names / *.tsv）是这个仓库的隐私红线，
    任何一条规则都不许用裸 `*`，也不许显式收表格后缀。
    """
    for directive, directory, patterns in _rules():
        if directive != "recursive-include":
            continue
        assert "*" not in patterns, (
            "MANIFEST.in 的 recursive-include %s 用了裸 * —— 会连带表格入包" % directory
        )
        banned = {p for p in patterns if re.fullmatch(r"\*\.(csv|tsv|data|names|parquet|xlsx)", p)}
        assert not banned, (
            "MANIFEST.in 的 recursive-include %s 显式收了表格后缀 %s" % (directory, sorted(banned))
        )


def test_manifest_does_not_exclude_test_surface():
    """排除规则不许把上面三条覆盖掉（`recursive-exclude` 的目录不得与必含目录同名）。"""
    required_dirs = {directory for _, directory, _ in REQUIRED_RULES}
    offending = {directory for directive, directory, _ in _rules()
                 if directive == "recursive-exclude" and directory in required_dirs}
    assert not offending, "MANIFEST.in 用 recursive-exclude 排除了必需目录：%s" % sorted(offending)
