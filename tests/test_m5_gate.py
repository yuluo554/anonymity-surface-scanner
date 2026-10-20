"""M5 gate 验收（`plan/05` M5 DoD / `plan/03 §模块 M5`）。

五条互不替代的判据：

  1. **三态退出码**：`pass`（0）/ `violation`（1）/ `undecidable`（2）；空表、
     `budget-truncated + require_exhaustive` 一律 2，绝不退化为 0。
  2. **判据闭合**：未知键 / 非法 `thresholds.l`·`.t` / 坏 `search` 块 → `CriteriaError`（2）。
     判据解析只存在于 `m5_gate.load_criteria`（CLI 不自己读 JSON）。
  3. **报告纪律**：首屏四项声明齐；每条违例给"分组键 + 计数 + 行号"；
     非穷尽时**不得**写"最小崩塌集（穷尽结果）"；完整性三态显式。
  4. **可复算**：双跑 `gate.json` / `gate.md` 逐字节一致；无绝对路径 / 时间戳 / 主机名。
  5. **分层纪律**（K8）：`m5_gate` 不 import CLI / 时钟 / 随机 / 网络。
"""
from __future__ import annotations

import ast
import json
import socket
from datetime import datetime
from pathlib import Path

import pytest

from anonymity_scanner import canonical
from anonymity_scanner.cli import main
from anonymity_scanner.exit_codes import PASS, UNDECIDABLE, VIOLATION
from anonymity_scanner.m5_gate import (
    REASON_REQUIRE_EXHAUSTIVE,
    REASON_SEARCH_NOT_EXHAUSTED,
    combine_outcomes,
    load_criteria,
    render_markdown,
)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "anonymity_scanner"


# ── 夹具构造 ──────────────────────────────────────────────────────────────

def write_table(tmp_path, rows, header=("age", "zip", "disease"), name="table.csv", directory=None):
    base = Path(directory) if directory is not None else tmp_path
    base.mkdir(parents=True, exist_ok=True)
    text = ",".join(header) + "\n" + "".join(",".join(row) + "\n" for row in rows)
    path = base / name
    path.write_bytes(text.encode("utf-8"))
    return path


def write_decl(tmp_path, columns, name="decl.json"):
    path = tmp_path / name
    path.write_text(json.dumps({"columns": columns}, ensure_ascii=False), encoding="utf-8")
    return path


def default_decl(tmp_path):
    return write_decl(
        tmp_path,
        {"age": {"role": "qi"}, "zip": {"role": "qi"}, "disease": {"role": "sensitive"}},
    )


def write_criteria(tmp_path, table, decl, **overrides):
    document = {
        "table": str(table),
        "declaration": str(decl),
        "missing_policy": "drop",
        "thresholds": {"k": 2, "l": None, "t": None},
    }
    document.update(overrides)
    path = tmp_path / "criteria.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def run_gate(tmp_path, criteria, out="out", root=None):
    argv = [
        "gate", "--criteria", str(criteria),
        "--out-dir", str(tmp_path / out),
        "--root", str(tmp_path if root is None else root),
    ]
    return main(argv)


def read_gate(tmp_path, out="out"):
    document = json.loads((tmp_path / out / "gate.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / out / "gate.md").read_text(encoding="utf-8")
    return document, markdown


# 4 行、两类各 2 人：k=2、l=2、t=0 → 在 k=2 下通过。
BALANCED = [("30", "100", "flu"), ("30", "100", "flu"), ("31", "101", "cold"), ("31", "101", "cold")]


# ── 三态退出码 ────────────────────────────────────────────────────────────

def test_gate_pass_when_all_thresholds_satisfied(tmp_path, capsys):
    table = write_table(tmp_path, BALANCED)
    decl = default_decl(tmp_path)
    criteria = write_criteria(tmp_path, table, decl)

    code = run_gate(tmp_path, criteria)
    captured = capsys.readouterr()

    assert "MODULE_NOT_READY" not in captured.err
    assert code == PASS
    document, markdown = read_gate(tmp_path)
    assert document["outcome"] == "pass"
    assert document["exit_code"] == PASS
    assert document["undefined_reason"] is None
    assert document["scan"]["verdict"] == "pass"
    assert document["scan"]["k_l_t"]["k"] == 2
    assert (tmp_path / "out" / "gate.json").is_file()
    assert (tmp_path / "out" / "gate.md").is_file()


def test_gate_violation_when_k_below_threshold(tmp_path):
    table = write_table(
        tmp_path,
        [("30", "100", "flu"), ("31", "100", "cold"), ("30", "101", "flu")],
    )
    decl = default_decl(tmp_path)
    criteria = write_criteria(tmp_path, table, decl)

    code = run_gate(tmp_path, criteria)

    assert code == VIOLATION
    document, markdown = read_gate(tmp_path)
    assert document["outcome"] == "violation"
    assert document["exit_code"] == VIOLATION
    assert document["scan"]["k_l_t"]["k"] == 1
    assert len(document["violations"]) == 3
    # 每条违例的三件套：分组键 + 计数 + 行号（markdown 里 `|` 必须转义）。
    first = document["violations"][0]
    assert first["key"] == "age=30|zip=100"
    assert first["count"] == 1
    assert first["row_numbers"] == [1]
    assert "age=30\\|zip=100" in markdown
    assert "| 1 | `age=30\\|zip=100` | 1 | 1 |" in markdown


def test_gate_empty_table_is_undecidable(tmp_path):
    table = write_table(tmp_path, [], header=("age", "zip", "disease"))
    decl = default_decl(tmp_path)
    criteria = write_criteria(tmp_path, table, decl)

    code = run_gate(tmp_path, criteria)

    assert code == UNDECIDABLE
    document, markdown = read_gate(tmp_path)
    assert document["outcome"] == "undecidable"
    assert document["undefined_reason"] == "empty_table"
    assert document["scan"]["k_l_t"]["k"] is None
    assert "empty_table" in markdown


def test_gate_all_rows_dropped_is_undecidable(tmp_path):
    table = write_table(
        tmp_path,
        [("NA", "100", "flu"), ("", "101", "cold")],
    )
    decl = default_decl(tmp_path)
    criteria = write_criteria(tmp_path, table, decl)

    code = run_gate(tmp_path, criteria)

    assert code == UNDECIDABLE
    document, _ = read_gate(tmp_path)
    assert document["undefined_reason"] == "no_participating_rows"
    assert document["scan"]["k_l_t"]["undecided_rows"] == [1, 2]


# ── l / t 门限走 M2（K1）：gate 不另写统计 ────────────────────────────────

def test_gate_l_threshold_violation_uses_m2(tmp_path):
    table = write_table(
        tmp_path,
        [("30", "100", "flu"), ("30", "100", "flu"), ("31", "101", "flu"), ("31", "101", "flu")],
    )
    decl = default_decl(tmp_path)
    criteria = write_criteria(tmp_path, table, decl, thresholds={"k": 2, "l": 2, "t": None})

    code = run_gate(tmp_path, criteria)

    assert code == VIOLATION, "k 达标但类内敏感值只有一种 → l=1 < 2"
    document, _ = read_gate(tmp_path)
    assert document["scan"]["k_l_t"]["l"] == 1
    assert len(document["violations"]) == 2


def test_gate_t_threshold_violation_uses_m2(tmp_path):
    table = write_table(tmp_path, BALANCED)  # 每类纯分布 → t=0.5
    decl = default_decl(tmp_path)
    criteria = write_criteria(tmp_path, table, decl, thresholds={"k": 2, "l": None, "t": 0.4})

    code = run_gate(tmp_path, criteria)

    assert code == VIOLATION, "t=0.5 > 0.4"
    document, _ = read_gate(tmp_path)
    assert document["scan"]["k_l_t"]["t"] == 0.5


# ── 搜索：完整性三态 / 非穷尽措辞 / 预算截断 ──────────────────────────────

def test_gate_search_exhaustive_writes_minimal_sets(tmp_path):
    table = write_table(tmp_path, BALANCED)
    decl = default_decl(tmp_path)
    criteria = write_criteria(
        tmp_path, table, decl,
        search={"enabled": True, "budget": 100, "require_exhaustive": False},
    )

    code = run_gate(tmp_path, criteria)

    assert code == PASS
    document, markdown = read_gate(tmp_path)
    assert document["search"]["completeness"] == "exhausted"
    assert document["search"]["minimal_collapse_sets"] == [["age", "zip"]]
    assert "最小崩塌集（穷尽结果）" in markdown
    assert "exhausted" in markdown
    assert "非穷尽结果" not in markdown


def test_gate_budget_truncated_with_require_exhaustive_is_undecidable(tmp_path):
    table = write_table(tmp_path, BALANCED)
    decl = default_decl(tmp_path)
    criteria = write_criteria(
        tmp_path, table, decl,
        search={"enabled": True, "budget": 1, "require_exhaustive": True},
    )

    code = run_gate(tmp_path, criteria)

    assert code == UNDECIDABLE, "要求穷尽却被截断 → fail-closed，即便 k 达标"
    document, markdown = read_gate(tmp_path)
    assert document["search"]["completeness"] == "budget-truncated"
    assert document["undefined_reason"] == REASON_REQUIRE_EXHAUSTIVE
    assert "budget-truncated" in markdown
    assert "非穷尽结果" in markdown
    assert "最小崩塌集（穷尽结果）" not in markdown, "非穷尽时不得称最小崩塌集"


def test_gate_require_exhaustive_truncation_wins_over_violation(tmp_path):
    """有违例 + 要求穷尽却被截断 → fail-closed 取 2（violation 不得覆盖这条）。"""
    table = write_table(
        tmp_path,
        [("30", "100", "flu"), ("31", "100", "cold"), ("30", "101", "flu")],
    )
    decl = default_decl(tmp_path)
    criteria = write_criteria(
        tmp_path, table, decl,
        search={"enabled": True, "budget": 1, "require_exhaustive": True},
    )

    code = run_gate(tmp_path, criteria)

    assert code == UNDECIDABLE
    document, markdown = read_gate(tmp_path)
    assert document["scan"]["verdict"] == "violation"
    assert document["search"]["completeness"] == "budget-truncated"
    assert document["outcome"] == "undecidable"
    assert document["undefined_reason"] == REASON_REQUIRE_EXHAUSTIVE
    assert "非穷尽结果" in markdown


def test_gate_budget_truncated_without_require_is_still_undecidable(tmp_path):
    table = write_table(tmp_path, BALANCED)
    decl = default_decl(tmp_path)
    criteria = write_criteria(
        tmp_path, table, decl,
        search={"enabled": True, "budget": 1, "require_exhaustive": False},
    )

    code = run_gate(tmp_path, criteria)

    assert code == UNDECIDABLE, "§4.6：退出码 0 要求完整性未被裁剪"
    document, _ = read_gate(tmp_path)
    assert document["undefined_reason"] == REASON_SEARCH_NOT_EXHAUSTED


def test_gate_monotonicity_not_applicable_blocks_pass(tmp_path):
    rows = BALANCED + [("NA", "102", "flu")]
    table = write_table(tmp_path, rows)
    decl = default_decl(tmp_path)
    criteria = write_criteria(
        tmp_path, table, decl,
        search={"enabled": True, "budget": 100, "require_exhaustive": False},
    )

    code = run_gate(tmp_path, criteria)

    assert code == UNDECIDABLE, "drop 下候选池含缺失 → 单调性不适用，不得判通过"
    document, markdown = read_gate(tmp_path)
    assert document["scan"]["verdict"] == "pass"
    assert document["search"]["completeness"] == "monotonicity-not-applicable"
    assert document["search"]["monotonicity_applicable"] is False
    assert document["undefined_reason"] == REASON_SEARCH_NOT_EXHAUSTED
    assert "monotonicity-not-applicable" in markdown
    assert "最小崩塌集（穷尽结果）" not in markdown


def test_gate_violation_wins_over_non_exhaustive_search(tmp_path):
    table = write_table(
        tmp_path,
        [("30", "100", "flu"), ("31", "100", "cold"), ("30", "101", "flu")],
    )
    decl = default_decl(tmp_path)
    criteria = write_criteria(
        tmp_path, table, decl,
        search={"enabled": True, "budget": 100, "require_exhaustive": False},
    )

    code = run_gate(tmp_path, criteria)

    assert code == VIOLATION
    document, _ = read_gate(tmp_path)
    assert document["undefined_reason"] is None, "已有违例时不再挂无法裁决原因"


def test_gate_empty_set_witness_is_explicit(tmp_path):
    rows = [("30", "100", "flu"), ("31", "101", "cold"), ("32", "102", "flu"), ("33", "103", "cold")]
    table = write_table(tmp_path, rows)
    decl = default_decl(tmp_path)
    criteria = write_criteria(
        tmp_path, table, decl,
        search={"enabled": True, "budget": 100, "require_exhaustive": False},
    )

    code = run_gate(tmp_path, criteria)

    assert code == VIOLATION
    document, markdown = read_gate(tmp_path)
    assert document["search"]["minimal_collapse_sets"] == [[]]
    assert document["search"]["empty_set_witness"] is True
    assert "一个 QI 列都不能加" in markdown


def test_gate_no_solution_is_explicit(tmp_path):
    table = write_table(tmp_path, [("30", "100", "flu"), ("31", "101", "cold")])
    decl = default_decl(tmp_path)
    criteria = write_criteria(
        tmp_path, table, decl,
        thresholds={"k": 5, "l": None, "t": None},
        search={"enabled": True, "budget": 100, "require_exhaustive": False},
    )

    code = run_gate(tmp_path, criteria)

    assert code == VIOLATION
    document, markdown = read_gate(tmp_path)
    assert document["search"]["verdict"] == "no_solution"
    assert "无解" in markdown


# ── 判据路径以判据文件所在目录为基准 ──────────────────────────────────────

def test_gate_resolves_relative_paths_against_criteria_directory(tmp_path):
    case = tmp_path / "case"
    table = write_table(case, BALANCED, name="table.csv")
    decl = write_decl(case, {"age": {"role": "qi"}, "zip": {"role": "qi"}, "disease": {"role": "sensitive"}})
    criteria = write_criteria(
        case,
        "table.csv",
        "decl.json",
        thresholds={"k": 2, "l": None, "t": None},
    )
    assert table.is_file() and decl.is_file()

    code = run_gate(tmp_path, criteria, root=case)

    assert code == PASS, "相对路径必须以判据文件所在目录为基准，而不是 cwd"
    document, _ = read_gate(tmp_path)
    assert document["criteria"] == "criteria.json"
    assert document["table"] == "table.csv"


# ── 可复算纪律（K3 / K7） ─────────────────────────────────────────────────

def test_gate_double_run_is_byte_identical(tmp_path):
    table = write_table(
        tmp_path,
        [("30", "100", "flu"), ("31", "100", "cold"), ("30", "101", "flu")],
    )
    decl = default_decl(tmp_path)
    criteria = write_criteria(
        tmp_path, table, decl,
        search={"enabled": True, "budget": 100, "require_exhaustive": False},
    )

    first = run_gate(tmp_path, criteria, out="a")
    second = run_gate(tmp_path, criteria, out="b")

    assert first == second == VIOLATION
    assert (tmp_path / "a" / "gate.json").read_bytes() == (tmp_path / "b" / "gate.json").read_bytes()
    assert (tmp_path / "a" / "gate.md").read_bytes() == (tmp_path / "b" / "gate.md").read_bytes()


def test_gate_outputs_have_no_abs_path_timestamp_or_hostname(tmp_path):
    table = write_table(tmp_path, BALANCED)
    decl = default_decl(tmp_path)
    criteria = write_criteria(
        tmp_path, table, decl,
        search={"enabled": True, "budget": 100, "require_exhaustive": False},
    )

    assert run_gate(tmp_path, criteria) == PASS
    raw_json = (tmp_path / "out" / "gate.json").read_bytes()
    raw_md = (tmp_path / "out" / "gate.md").read_bytes()
    for raw in (raw_json, raw_md):
        assert not raw.startswith(b"\xef\xbb\xbf"), "不得带 BOM"
        assert b"\r\n" not in raw, "必须是 LF"
    text_json = raw_json.decode("utf-8")
    text_md = raw_md.decode("utf-8")
    assert text_json == canonical.dumps(json.loads(text_json)), "gate.json 必须走 canonical 冻结参数"
    for text in (text_json, text_md):
        assert str(tmp_path) not in text
        assert str(tmp_path).replace("\\", "/") not in text
        assert socket.gethostname() not in text
        assert datetime.now().strftime("%Y-%m-%d") not in text
    assert text_md.endswith("\n") and not text_md.endswith("\n\n")


def test_render_markdown_is_a_pure_function(tmp_path):
    table = write_table(tmp_path, BALANCED)
    decl = default_decl(tmp_path)
    criteria = write_criteria(tmp_path, table, decl)

    assert run_gate(tmp_path, criteria) == PASS
    document, markdown = read_gate(tmp_path)
    assert render_markdown(document) == render_markdown(document) == markdown


# ── 结论优先级 ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "outcomes,expected",
    [
        ((), "pass"),
        (("pass",), "pass"),
        (("pass", "violation"), "violation"),
        (("violation", "pass"), "violation"),
        (("pass", "undecidable"), "undecidable"),
        (("violation", "undecidable"), "undecidable"),
        (("undecidable", "violation", "pass"), "undecidable"),
        (("pass", "nonsense"), "undecidable"),
    ],
)
def test_combine_outcomes_priority(outcomes, expected):
    assert combine_outcomes(*outcomes) == expected


# ── 分层纪律（K8）与"判据解析只此一处" ───────────────────────────────────

def _imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
            for alias in node.names:
                names.add(alias.name.split(".")[0])
    return names


def test_m5_module_respects_compute_layer_discipline():
    """K8：不 import CLI、不读时钟 / 随机 / 网络。"""
    modules = _imported_modules(SRC / "m5_gate.py")
    forbidden = {"time", "datetime", "random", "secrets", "socket", "os"}
    assert not (modules & forbidden), "m5_gate 出现了禁用模块：%s" % sorted(modules & forbidden)
    assert not any(name == "cli" or name.startswith("anonymity_scanner.cli") for name in modules)


def test_criteria_parsing_lives_only_in_m5_gate():
    """CLI 之外无第二份判据解析：cli 不再 import json / 不再调用 json.loads。"""
    cli_text = (SRC / "cli.py").read_text(encoding="utf-8")
    assert "json.loads" not in cli_text
    assert "json" not in _imported_modules(SRC / "cli.py")
    gate_text = (SRC / "m5_gate.py").read_text(encoding="utf-8")
    assert gate_text.count("json.loads") == 1


# ── Adult 演示：判据闭合、脚本离线（不需要数据也能跑） ────────────────────

def test_adult_example_is_closed_and_offline():
    example = ROOT / "examples" / "adult"
    for name in ("run.sh", "prepare.py", "criteria.json", "declaration.json", "README.md", "EXPECTED.md"):
        assert (example / name).is_file(), "examples/adult 缺 %s" % name

    criteria = load_criteria(example / "criteria.json")
    assert criteria["table"] == "adult.csv"
    assert criteria["declaration"] == "declaration.json"
    assert criteria["missing_policy"] == "drop"
    assert criteria["thresholds"] == {"k": 5, "l": None, "t": None}
    assert criteria["search"] == {"enabled": True, "budget": 256, "require_exhaustive": True}

    assert "curl" not in (example / "run.sh").read_text(encoding="utf-8"), "演示脚本不得代下载"
    prepare_modules = _imported_modules(example / "prepare.py")
    network = {"urllib", "http", "requests", "socket", "ftplib", "urllib3"}
    assert not (prepare_modules & network), "prepare.py 不得联网：%s" % sorted(prepare_modules & network)
