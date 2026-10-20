"""确定性序列化：**本项目唯一的写盘/序列化入口**（K3）。

为什么必须单点：多个子命令各自 ``open() + json.dump()`` 必然漂移（一个带 BOM、一个不排序、
一个 CRLF 一个 LF），而"同输入两次运行逐字节相同"是本项目的核心承诺。

冻结参数（改动即 K3 变更，须同步 `plan/02 §六` 与测试）：
    sort_keys=True / ensure_ascii=False / indent=2 / separators=(",", ": ") / allow_nan=False
    浮点一律先经 round6()（ROUND_HALF_EVEN，6 位） / 文本以单个 LF 结尾 / 写盘用 LF。
"""
from __future__ import annotations

import json
import os
import tempfile
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

_SIX = Decimal("0.000001")


def round6(value: float) -> float:
    """6 位定点，四舍六入五成双（`data/README.md` §4.7）。

    用 Decimal(str(x)) 而不是 Decimal(x)：后者会把二进制尾差带进来（0.1 → 0.1000000000000000055…），
    导致"同一个数在不同机器上舍入到不同的最后一位"。
    """
    if value is None:
        return None
    quantized = Decimal(str(float(value))).quantize(_SIX, rounding=ROUND_HALF_EVEN)
    result = float(quantized)
    # 归一 -0.0：JSON 里 "-0.0" 与 "0.0" 是两个字节串，会让双跑比对出现假差异。
    return 0.0 if result == 0.0 else result


def dumps(obj) -> str:
    """确定性 JSON 文本（含结尾换行）。任何产物都必须经此函数。"""
    text = json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
        separators=(",", ": "),
        allow_nan=False,
    )
    return text + "\n"


def write_text_atomic(path, text: str) -> None:
    """原子写（先写临时文件再 replace），强制 LF，UTF-8 无 BOM。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(prefix=".tmp-", dir=str(target.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(tmp_name, str(target))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def write_json(path, obj) -> None:
    write_text_atomic(path, dumps(obj))


def relativize(path, root) -> str:
    """把路径相对化后写进报告（D7：报告不含绝对路径）。

    跨盘符（C: → D:）时 ``os.path.relpath`` 在 Windows 抛 ValueError，此时回落到
    ``path.name``——报告仍然可读，且绝不泄露本机目录结构。
    """
    try:
        rel = os.path.relpath(str(path), str(root))
    except ValueError:
        return Path(path).name
    return rel.replace(os.sep, "/")
