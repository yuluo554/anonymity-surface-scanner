"""表格读取（CSV / TSV）。

纪律：
  * 行号 = **数据行序号，1 起，不含表头**（`data/README.md` §4.3）。
  * 缺失值集合是**单点定义**（K4）：`missing_set()` 是唯一出口，其他模块不得再写一份。
  * 不做隐式清洗、不做类型推断、不猜编码以外的任何东西。
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

from .exit_codes import InputError

# K4：缺失值集合（`data/README.md` §4.4 旁注）。大小写敏感，原样比较。
_MISSING_TOKENS = ("", "NA", "N/A", "null", "NULL", "-")


def missing_set():
    """缺失值判定集合的**唯一出口**。返回 frozenset，调用方不得修改。"""
    return frozenset(_MISSING_TOKENS)


def is_missing(value: str) -> bool:
    return value in missing_set()


class Table(object):
    """已读入的表：表头顺序 + 数据行（行号 + 值列表）。"""

    __slots__ = ("header", "rows", "source")

    def __init__(self, header, rows, source=None) -> None:
        self.header = list(header)
        self.rows = list(rows)  # [(row_number: int, values: list[str])]
        self.source = source

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def column_index(self, name: str):
        try:
            return self.header.index(name)
        except ValueError:
            return None

    def has_column(self, name: str) -> bool:
        return self.column_index(name) is not None

    def values(self, name: str):
        """返回该列的原始值（含缺失标记原样），缺失判定交给 `is_missing`。"""
        idx = self.column_index(name)
        if idx is None:
            raise InputError("表中不存在列", name)
        return [row[1][idx] for row in self.rows]


def _delimiter_for(path: Path) -> str:
    return "\t" if path.suffix.lower() in (".tsv", ".tab") else ","


def read_table(path) -> Table:
    """读取表。编码固定 utf-8-sig（容忍 Excel 导出的 BOM），不猜其他编码。"""
    target = Path(path)
    if not target.is_file():
        raise InputError("表文件不存在", str(target))
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise InputError("表文件无法读取", str(exc))
    if not raw.strip():
        raise InputError("表文件为空（连表头都没有）", str(target))
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputError("表文件不是 UTF-8 编码", "%s @ byte %d" % (target.name, exc.start))
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=_delimiter_for(target))
    try:
        header = next(reader)
    except StopIteration:  # pragma: no cover - raw.strip() 已拦截
        raise InputError("表文件没有表头", str(target))
    header = [cell.strip() for cell in header]
    if not header or all(cell == "" for cell in header):
        raise InputError("表头为空", str(target))
    duplicates = sorted({name for name in header if header.count(name) > 1})
    if duplicates:
        raise InputError("表头有重复列名", ", ".join(duplicates))

    rows = []
    for physical_line, record in enumerate(reader, start=2):  # 第 1 行是表头
        if not record or (len(record) == 1 and record[0].strip() == ""):
            continue  # 完全空行不是数据行，也不占"数据行序号"
        row_number = len(rows) + 1
        if len(record) != len(header):
            raise InputError(
                "数据行宽度与表头不一致",
                "文件第 %d 行（数据行 %d）：%d 列（表头 %d 列）"
                % (physical_line, row_number, len(record), len(header)),
            )
        rows.append((row_number, record))
    return Table(header, rows, source=str(target))
