"""自述测试数的守门（D6）。

`v0.1.0` 的 277 被手抄在 4 处文档里，**没有任何门抓住漂移**：加一条测试，
文档就悄悄过期。本文件把「文档里写的数」与「实际收集到的数」钉在一起。

两段判据：

  1. **四处副本互相一致**（同一版本的自述数不得各写各的）；
  2. **与 `pytest --collect-only` 的实收集数相等**。

第 2 段只在**开发树**里成立：sdist 解包树里没有 `*.csv`（`.gitignore` 排除），
带表格参数的夹具用例会被收集但不执行/不收集，收集数天然比开发树小。
因此在缺表格时如实 `skip`，不写成一个能过但什么都没证明的断言。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# 显式清单：只钉**描述当前状态**的那一处。历史里程碑清单（`plan/05` 的 M5/M6 达成栏、
# `plan/RELEASE-M6.md` §一/§二 的当轮实测）保留当轮数字，不参与本判据——改它们等于改写历史。
# 统一标记串 `当前全量测试 N 项` 是唯一被机器读的自述位；换了措辞这里会红。
DECLARED = (
    ("plan/00-README总览.md", r"当前全量测试 (\d+) 项"),
    ("plan/05-里程碑与发布.md", r"当前全量测试 (\d+) 项"),
    ("plan/HANDOFF-M6.md", r"当前全量测试 (\d+) 项"),
    ("plan/RELEASE-M6.md", r"当前全量测试 (\d+) 项"),
)

# 夹具表格不入库；没有它时收集数会塌，判据不成立。
TABLES = ("data/fixtures/tiny/table.csv", "data/fixtures/budget/table.csv")


def _declared_numbers():
    found = {}
    for rel, pattern in DECLARED:
        text = (ROOT / rel).read_text(encoding="utf-8")
        hits = re.findall(pattern, text)
        assert hits, "%s 里找不到自述测试数（模式：%s）——文档结构变了，请同步本判据" % (rel, pattern)
        found[rel] = {int(h) for h in hits}
    return found


def test_declared_test_counts_agree_across_copies():
    """四处副本必须写同一个数。"""
    found = _declared_numbers()
    values = set().union(*found.values())
    assert len(values) == 1, "自述测试数在各副本间不一致：%s" % {
        rel: sorted(v) for rel, v in sorted(found.items())
    }


def test_declared_test_count_equals_collected_count():
    """文档里的数必须等于实际收集数（`--collect-only`，不执行、无副作用）。"""
    missing = [rel for rel in TABLES if not (ROOT / rel).is_file()]
    if missing:
        pytest.skip("缺夹具表格（sdist 解包树 / 干净 clone）：%s" % ", ".join(missing))

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
    )
    output = completed.stdout.decode("utf-8", "replace")
    assert completed.returncode == 0, "收集阶段就失败了：\n%s" % output
    collected = sum(int(n) for n in re.findall(r":\s*(\d+)\s*$", output, re.MULTILINE))
    assert collected > 0, "收集数为 0（解析口径失效）：\n%s" % output

    declared = set().union(*_declared_numbers().values())
    assert declared == {collected}, (
        "自述测试数 %s 与实际收集数 %d 不一致——加/删测试后请同步四处文档"
        % (sorted(declared), collected)
    )
