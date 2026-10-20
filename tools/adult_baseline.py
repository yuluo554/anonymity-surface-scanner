"""UCI Adult 读入基线（M1）：**只读本地文件，不代下载、不联网**。

为什么单独一条命令：`data/README.md` §二 明确"脚本只读本地文件，不替我下载"。
把下载藏进工具里会让"安装后零网络"这条承诺失效，也会让 CI 意外联网。

用法：
    py -3.12 tools/adult_baseline.py --table <path/to/adult.data>
    py -3.12 tools/adult_baseline.py --table <path> --json      # 机读输出
    py -3.12 tools/adult_baseline.py                            # 不给路径 = 只报告"未取得"，退出码 3

退出码：
    0  成功读入并报告行数 / 列数
    2  文件存在但读不动（编码 / 宽度 / 空文件 —— 属于"无法裁决"，与本项目纪律一致）
    3  未取得本地文件（**不是错误**：`plan/05 §四` 允许"演示未实跑"，但必须如实标注）

本脚本只做"能不能读、有多少行多少列、哪些列有空值"这三件事。它**不**计算 k/l/t，
也**不**写任何产物到仓库（避免把数据表或统计结果入库）。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

# UCI Adult（Census Income）的原始 `adult.data` 是**无表头**的逗号分隔文件，
# 行尾是 ",\\n"（每行末尾有一个空字段），且缺失值写作 " ?"。
# 这两条是本脚本对外的**唯一**格式假设，写在文档里而不是靠猜。
ADULT_COLUMNS = [
    "age", "workclass", "fnlwgt", "education", "education-num", "marital-status",
    "occupation", "relationship", "race", "sex", "capital-gain", "capital-loss",
    "hours-per-week", "native-country", "income",
]
ADULT_TRAIN_ROWS = 32561   # `adult.data`
ADULT_TEST_ROWS = 16281    # `adult.test`（首行是表头注释，含 30 行 "|1x3 Cross validator" 说明）
UCI_URL = "https://archive.ics.uci.edu/dataset/2/adult"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def read_local(path: Path):
    """读入并返回 `(header, rows)`。空行跳过（与 `tableio.read_table` 同一语义）。"""
    raw = path.read_bytes()
    if not raw.strip():
        raise ValueError("文件为空")
    text = raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text, newline=""))
    records = [record for record in reader if record and any(cell.strip() for cell in record)]
    if not records:
        raise ValueError("文件里没有可读记录")
    # 无表头：UCI 原文即如此。判定依据 = 第一行首格能否解析为整数（age）。
    first = records[0][0].strip()
    has_header = not first.isdigit()
    if has_header:
        header = [cell.strip() for cell in records[0]]
        rows = records[1:]
    else:
        header = list(ADULT_COLUMNS)
        rows = records
    # 行尾多一个空字段（"age,...,income,\\n"）：只裁掉**恰好一个**尾空字段。
    trimmed = []
    for record in rows:
        cells = list(record)
        if len(cells) == len(header) + 1 and cells[-1].strip() == "":
            cells = cells[:-1]
        if len(cells) != len(header):
            raise ValueError("宽度不符：期望 %d 列，实测 %d 列" % (len(header), len(cells)))
        trimmed.append(cells)
    return header, trimmed


def survey(header, rows):
    """只报"有多少行、多少列、哪些列含空/问号"。不计算隐私指标。"""
    blank = {}
    for index, name in enumerate(header):
        count = sum(1 for record in rows if record[index].strip() in ("", "?"))
        if count:
            blank[name] = count
    return {
        "rows": len(rows),
        "columns": len(header),
        "column_names": header,
        "missing_like_cells_by_column": blank,
        "expected_train_rows": ADULT_TRAIN_ROWS,
        "matches_expected_train_rows": len(rows) == ADULT_TRAIN_ROWS,
    }


def main(argv=None) -> int:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        encoding = (getattr(stream, "encoding", None) or "").lower()
        if encoding and encoding.replace("-", "") not in ("utf8", "utf8mb4"):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                try:
                    reconfigure(encoding="utf-8", errors="replace")
                except (ValueError, OSError):  # pragma: no cover
                    pass

    parser = argparse.ArgumentParser(description="UCI Adult 读入基线（只读本地，不下载）")
    parser.add_argument("--table", default=None, help="本地 adult.data / adult.test 路径")
    parser.add_argument("--json", action="store_true", help="输出机读 JSON")
    args = parser.parse_args(argv)

    if not args.table:
        report = {
            "status": "not_obtained",
            "reason": "未提供 --table；本脚本不代下载（data/README.md §二）",
            "download_url": UCI_URL,
            "note": "演示未实跑时按 plan/05 §四 如实标注，不得编造行数",
        }
        if args.json:
            sys.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        else:
            sys.stdout.write("Adult：未取得本地文件（本脚本不代下载）\n")
            sys.stdout.write("  下载地址：%s\n" % UCI_URL)
            sys.stdout.write("  用法：py -3.12 tools/adult_baseline.py --table <adult.data>\n")
        return 3

    path = Path(args.table)
    if not path.is_file():
        sys.stderr.write("Adult：文件不存在 %s\n" % path)
        return 2
    try:
        header, rows = read_local(path)
    except (ValueError, UnicodeDecodeError, OSError) as exc:
        sys.stderr.write("Adult：无法读入 %s（%s）\n" % (path.name, exc))
        return 2

    result = survey(header, rows)
    result["file"] = path.name
    result["sha256"] = sha256_file(path)
    result["status"] = "read_ok"
    if args.json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    else:
        sys.stdout.write("Adult 读入基线（只读本地，无网络）\n")
        sys.stdout.write("  file   : %s\n" % result["file"])
        sys.stdout.write("  sha256 : %s\n" % result["sha256"])
        sys.stdout.write("  rows   : %d（期望 %d：%s）\n"
                         % (result["rows"], ADULT_TRAIN_ROWS,
                            "一致" if result["matches_expected_train_rows"] else "不一致（不是 adult.data？）"))
        sys.stdout.write("  columns: %d\n" % result["columns"])
        if result["missing_like_cells_by_column"]:
            sys.stdout.write("  含空/问号的列：%s\n" % ", ".join(
                "%s=%d" % (k, v) for k, v in sorted(result["missing_like_cells_by_column"].items())
            ))
        else:
            sys.stdout.write("  含空/问号的列：无\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
