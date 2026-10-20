"""确定性测试：序列化冻结参数、双跑逐字节一致、报告不含敏感元信息。

这些断言保护的是**产品承诺**（`plan/02 §六`）而不是实现细节：
同输入两次运行必须产出逐字节相同的文件，且产物里不能出现时间戳/主机名/绝对路径。
"""
from __future__ import annotations

import json
import os
import socket
from datetime import datetime
from pathlib import Path

import pytest

from anonymity_scanner import canonical


def test_dumps_is_sorted_and_utf8():
    text = canonical.dumps({"b": 1, "a": "中文"})
    assert text == '{\n  "a": "中文",\n  "b": 1\n}\n'
    assert "\\u" not in text, "ensure_ascii=False：中文必须原样输出"


def test_dumps_rejects_nan():
    with pytest.raises(ValueError):
        canonical.dumps({"x": float("nan")})


def test_dumps_ends_with_exactly_one_lf():
    text = canonical.dumps({"a": 1})
    assert text.endswith("\n") and not text.endswith("\n\n")


@pytest.mark.parametrize(
    "raw,expected",
    [
        (0.1234564, 0.123456),
        (0.1234565, 0.123456),   # 半偶：末位 6 是偶数 → 不进位
        (0.1234575, 0.123458),   # 半偶：末位 7 是奇数 → 进位
        (-0.0, 0.0),             # -0.0 归一，否则双跑会出现字节差异
        (2.675, 2.675),          # 不是六位边界，应原样保留
    ],
)
def test_round6_half_even(raw, expected):
    assert canonical.round6(raw) == expected


def test_write_json_is_atomic_and_lf(tmp_path):
    target = tmp_path / "nested" / "out.json"
    canonical.write_json(target, {"a": "行一"})
    raw = target.read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")
    assert not list(target.parent.glob(".tmp-*")), "临时文件必须清理干净"


def test_double_run_is_byte_identical(tmp_path):
    document = {
        "columns": {"age": {"role": "qi"}},
        "scores": [canonical.round6(1 / 3), canonical.round6(2 / 7)],
        "classes": [{"key": "age=30", "count": 2, "rows": [1, 3]}],
    }
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    canonical.write_json(first, document)
    canonical.write_json(second, document)
    assert first.read_bytes() == second.read_bytes()


def test_output_has_no_timestamp_hostname_or_abs_path(tmp_path):
    """产物不得含时间戳 / 主机名 / 绝对路径（D7）。"""
    document = {
        "tool": "anonymity-scanner",
        "table": canonical.relativize(tmp_path / "data" / "x.csv", tmp_path),
    }
    text = canonical.dumps(document)
    assert str(tmp_path).replace(os.sep, "/") not in text
    assert str(tmp_path) not in text
    assert socket.gethostname() not in text
    today = datetime.now().strftime("%Y-%m-%d")
    assert today not in text


def test_relativize_cross_drive_falls_back_to_name(tmp_path):
    """跨盘符（Windows）时 relpath 抛 ValueError → 回落；任何平台上结果都必须是相对形态。"""
    other = "Z:/nope/x.csv" if os.name == "nt" else "/nonexistent-root/x.csv"
    result = canonical.relativize(other, tmp_path)
    assert not os.path.isabs(result), "报告里的路径永不为绝对路径"
    assert not result.startswith("Z:")
    assert result.endswith("x.csv")


def test_relativize_uses_forward_slashes(tmp_path):
    path = tmp_path / "a" / "b.csv"
    assert canonical.relativize(path, tmp_path) == "a/b.csv"
