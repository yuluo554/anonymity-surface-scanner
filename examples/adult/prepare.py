#!/usr/bin/env python3
"""把 UCI Adult 原始件转成本项目可读的 CSV。

只读本地文件，**不联网**。转换规则（与 `examples/adult/README.md` 一致）：

  * 每行 15 个逗号分隔字段，最后一个是行尾空字段（`,…,<=50K,`），丢弃；
  * 值两侧空白剥除；`?` 归一到空串（`tableio.missing_set()` 的缺失 token）；
  * 输出 UTF-8 + LF + 表头，其余列值原样保留（不做类型推断）。

用法：
    py -3.12 examples/adult/prepare.py --input adult.data --output examples/adult/adult.csv
"""
from __future__ import annotations

import argparse
import csv
import sys

HEADER = [
    "age", "workclass", "fnlwgt", "education", "education-num",
    "marital-status", "occupation", "relationship", "race", "sex",
    "capital-gain", "capital-loss", "hours-per-week", "native-country", "income",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Adult 原始件 → 本项目 CSV（只读本地，不联网）")
    parser.add_argument("--input", required=True, help="adult.data / adult.test 路径")
    parser.add_argument("--output", required=True, help="输出 CSV 路径（不入库）")
    args = parser.parse_args(argv)

    rows = 0
    with open(args.input, "r", encoding="utf-8", newline="") as source, \
            open(args.output, "w", encoding="utf-8", newline="\n") as target:
        reader = csv.reader(source)
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(HEADER)
        for line_number, record in enumerate(reader, start=1):
            if not record or all(cell.strip() == "" for cell in record):
                continue
            if len(record) == len(HEADER) and record[-1].strip() == "":
                record = record[:-1]
            if len(record) != len(HEADER):
                sys.stderr.write(
                    "bad width at line %d: %d fields (expected %d)\n"
                    % (line_number, len(record), len(HEADER))
                )
                return 2
            values = ["" if cell.strip() == "?" else cell.strip() for cell in record]
            writer.writerow(values)
            rows += 1
    sys.stderr.write("prepared %d rows -> %s\n" % (rows, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
