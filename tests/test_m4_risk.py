"""M4 逐记录风险验收（`plan/05` M4 DoD / `plan/03 §模块 M4`）。

四条互不替代的判据：

  1. **真值对照**：四组夹具 `prosecutor` 的 `flagged_rows` 与 `truth["unique_records"]` 逐项一致；
     类 id 用 `declaration_order`（有序数组）**独立拼键复核**，不拿 `group_rows` 的输出当真值。
  2. **三口径边界**：手工构造 1 / 2 / 3 人等价类，测试名带口径名，锁死 `== 1` / `<= 2` / `< 3`。
  3. **失败路径**：空表 / 无参与行 → 显式 `undefined_reason` + 退出码 `2`，绝不返回 `pass`。
  4. **表达完整**：`drop` 未裁决行、`separate-class` 缺失类都逐条出现（不静默消失）；
     双跑逐字节一致；计算层不 import CLI / 时钟 / 随机 / 真值工具。
"""
from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path

import pytest

from anonymity_scanner import canonical
from anonymity_scanner.cli import main
from anonymity_scanner.m4_risk import (
    ATTACKERS,
    ATTACKER_RULES,
    UNDECIDED_ROW_REASON,
    classify,
    risk,
)
from anonymity_scanner.tableio import is_missing, read_table

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "data" / "fixtures"
SUITES = ("tiny", "small", "prune", "budget")
SRC = ROOT / "src" / "anonymity_scanner"


def load_truth(suite):
    return json.loads((FIXTURES / suite / "truth.json").read_text(encoding="utf-8"))


def fixture_table(suite):
    path = FIXTURES / suite / "table.csv"
    if not path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）；用 tools/gen_fixtures.py 生成后复跑")
    return read_table(path)


def write_declaration(truth, tmp_path, name="decl.json"):
    """按 `declaration_order`（有序数组）写声明：等价类键序 = 声明书写顺序。"""
    columns = {}
    for item in truth["declaration_order"]:
        spec = {"role": item["role"]}
        if "precision" in item:
            spec["precision"] = item["precision"]
        columns[item["name"]] = spec
    path = tmp_path / name
    path.write_text(json.dumps({"columns": columns}, ensure_ascii=False), encoding="utf-8")
    return path


def write_decl(tmp_path, columns, name="decl.json"):
    path = tmp_path / name
    path.write_text(json.dumps({"columns": columns}, ensure_ascii=False), encoding="utf-8")
    return path


def write_table(tmp_path, body, name="data.csv", header="age,disease"):
    path = tmp_path / name
    path.write_bytes((header + "\n" + body).encode("utf-8"))
    return path


def cli_risk(tmp_path, table_path, decl_path, policy, attacker, out="out"):
    code = main([
        "risk", "--table", str(table_path), "--decl", str(decl_path),
        "--missing-policy", policy, "--attacker", attacker,
        "--out-dir", str(tmp_path / out),
    ])
    return code, tmp_path / out / "risk.json"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected_class_ids(truth, table, policy):
    """独立复算：只用 `declaration_order` + 原始取值 + 缺失判定，不调用 `group_rows`。"""
    qi = [item["name"] for item in truth["declaration_order"] if item["role"] == "qi"]
    indices = [table.column_index(name) for name in qi]
    keys = {}
    for row_number, values in table.rows:
        selected = [values[index] for index in indices]
        if any(is_missing(value) for value in selected):
            if policy == "drop":
                continue
            if policy == "separate-class":
                keys[row_number] = "__MISSING__"
                continue
        keys[row_number] = "|".join(
            "%s=%s" % (name, value) for name, value in zip(qi, selected)
        )
    return keys


# ── 判据 1：四组夹具 × prosecutor 与真值逐项一致 ────────────────────────

@pytest.mark.parametrize("suite", SUITES)
def test_prosecutor_flagged_rows_match_unique_records_truth(suite):
    truth = load_truth(suite)
    table = fixture_table(suite)
    policy = truth["meta"]["policy"]
    result = risk(table, truth["qi_columns"], policy, "prosecutor")

    assert result["flagged_rows"] == truth["unique_records"]
    assert result["threshold"] == 1
    assert result["rule"] == "class_size == 1"
    expected_verdict = "violation" if truth["unique_records"] else "pass"
    assert result["verdict"] == expected_verdict


@pytest.mark.parametrize("policy", ("drop", "separate-class"))
def test_class_ids_are_recomputable_from_declaration_order(policy):
    """类 id = 声明书写顺序的 `name=value|...`；键序不得被表头或字典序改变。"""
    truth = load_truth("small")
    table = fixture_table("small")
    result = risk(table, truth["qi_columns"], policy, "journalist")
    expected = expected_class_ids(truth, table, policy)

    for record in result["records"]:
        if not record["participates"]:
            assert record["class_id"] is None
            continue
        assert record["class_id"] == expected[record["row_number"]]

    sizes = Counter(expected.values())
    for record in result["records"]:
        if record["participates"]:
            assert record["class_size"] == sizes[record["class_id"]]

    assert any(key.startswith("age=") for key in expected.values()), "键必须按声明顺序起头"
    assert policy != "separate-class" or "__MISSING__" in set(expected.values())


def test_cli_risk_writes_risk_json_matching_truth(tmp_path):
    truth = load_truth("small")
    table_path = FIXTURES / "small" / "table.csv"
    if not table_path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）")
    decl_path = write_declaration(truth, tmp_path)

    code, out = cli_risk(tmp_path, table_path, decl_path, "drop", "prosecutor")
    document = load_json(out)
    assert code == 1
    assert document["command"] == "risk"
    assert document["attacker"] == "prosecutor"
    assert document["flagged_rows"] == truth["unique_records"]
    assert document["verdict"] == "violation"
    assert document["exit_code"] == 1
    assert [record["row_number"] for record in document["records"]] == list(
        range(1, truth["rows"] + 1)
    ), "records 必须覆盖每一行且按行号升序"


# ── 判据 2：三口径边界（1 / 2 / 3 人等价类，测试名带口径名） ─────────────

def _sized_class_table(tmp_path):
    """3 个等价类：size 1 (row 1) / size 2 (rows 2-3) / size 3 (rows 4-6)。"""
    path = write_table(
        tmp_path,
        "10,flu\n20,flu\n20,cold\n30,flu\n30,cold\n30,flu\n",
        name="sized.csv",
    )
    return read_table(path)


def test_prosecutor_flags_only_class_size_one(tmp_path):
    result = risk(_sized_class_table(tmp_path), ["age"], "drop", "prosecutor")
    assert result["threshold"] == 1
    assert result["rule"] == "class_size == 1"
    assert result["flagged_rows"] == [1]
    assert [record["flagged"] for record in result["records"]] == [
        True, False, False, False, False, False,
    ]
    assert result["by_class_size"]["2"]["flagged_records"] == 0
    assert result["by_class_size"]["3"]["flagged_records"] == 0


def test_journalist_flags_size_two_but_not_three(tmp_path):
    result = risk(_sized_class_table(tmp_path), ["age"], "drop", "journalist")
    assert result["threshold"] == 2
    assert result["rule"] == "class_size <= 2"
    assert result["flagged_rows"] == [1, 2, 3]
    by_size = {record["class_size"]: record["flagged"] for record in result["records"]}
    assert by_size == {1: True, 2: True, 3: False}


def test_marketer_flags_below_three_not_three(tmp_path):
    result = risk(_sized_class_table(tmp_path), ["age"], "drop", "marketer")
    assert result["threshold"] == 3
    assert result["rule"] == "class_size < 3"
    assert result["flagged_rows"] == [1, 2, 3]
    assert [record["flagged"] for record in result["records"] if record["class_size"] == 3] == [
        False, False, False,
    ]
    assert result["by_class_size"] == {
        "1": {"classes": 1, "records": 1, "flagged_records": 1},
        "2": {"classes": 1, "records": 2, "flagged_records": 2},
        "3": {"classes": 1, "records": 3, "flagged_records": 0},
    }


def test_classify_rules_do_not_bleed_across_attackers():
    """`classify()` 是唯一判定实现：三口径在同一批类上给出各自边界。"""
    classes = {"one": [1], "two": [2, 3], "three": [4, 5, 6]}
    assert [item["flagged"] for item in classify(classes, "prosecutor")] == [True, False, False]
    assert [item["flagged"] for item in classify(classes, "journalist")] == [True, True, False]
    assert [item["flagged"] for item in classify(classes, "marketer")] == [True, True, False]
    assert ATTACKER_RULES == {
        "prosecutor": ("==", 1),
        "journalist": ("<=", 2),
        "marketer": ("<", 3),
    }
    assert ATTACKERS == ("prosecutor", "journalist", "marketer")


def test_risk_pass_when_no_record_is_flagged(tmp_path):
    """三行同一 QI → 一个 size=3 的类；prosecutor/journalist/marketer 都不命中 → pass。"""
    path = write_table(tmp_path, "30,flu\n30,cold\n30,flu\n", name="wide.csv")
    table = read_table(path)
    for attacker in ATTACKERS:
        result = risk(table, ["age"], "drop", attacker)
        assert result["flagged_rows"] == []
        assert result["verdict"] == "pass"


# ── 判据 3：失败路径（空表 / 无参与行） ──────────────────────────────────

def test_empty_table_risk_is_undecidable_with_reason(tmp_path):
    table_path = write_table(tmp_path, "", name="empty.csv")
    decl_path = write_decl(tmp_path, {"age": {"role": "qi"}, "disease": {"role": "sensitive"}})

    code, out = cli_risk(tmp_path, table_path, decl_path, "drop", "journalist")
    document = load_json(out)
    assert code == 2
    assert document["rows"] == 0
    assert document["records"] == []
    assert document["flagged_rows"] == []
    assert document["undefined_reason"] == "empty_table"
    assert document["verdict"] == "undecidable"
    assert document["exit_code"] == 2


def test_drop_all_rows_missing_is_undecidable_not_pass(tmp_path):
    table_path = write_table(tmp_path, "NA,flu\n-,cold\n", name="all-missing.csv")
    decl_path = write_decl(tmp_path, {"age": {"role": "qi"}, "disease": {"role": "sensitive"}})

    code, out = cli_risk(tmp_path, table_path, decl_path, "drop", "prosecutor")
    document = load_json(out)
    assert code == 2
    assert document["class_count"] == 0
    assert document["undefined_reason"] == "no_participating_rows"
    assert document["verdict"] == "undecidable"
    assert document["exit_code"] == 2
    assert [record["row_number"] for record in document["records"]] == [1, 2]
    assert all(record["participates"] is False for record in document["records"])
    assert all(record["class_id"] is None for record in document["records"])


# ── 判据 4：未裁决行与缺失类的表达 ───────────────────────────────────────

def test_drop_undecided_rows_are_expressed_not_silently_dropped(tmp_path):
    table_path = write_table(tmp_path, "NA,flu\n30,flu\n30,cold\n", name="partial-missing.csv")
    decl_path = write_decl(tmp_path, {"age": {"role": "qi"}, "disease": {"role": "sensitive"}})

    code, out = cli_risk(tmp_path, table_path, decl_path, "drop", "journalist")
    document = load_json(out)
    assert code == 1, "行 2-3 构成 size=2 的类 → journalist 命中"
    first = document["records"][0]
    assert first == {
        "row_number": 1,
        "class_id": None,
        "class_size": None,
        "flagged": False,
        "attacker": "journalist",
        "participates": False,
        "undefined_reason": UNDECIDED_ROW_REASON,
    }
    assert document["flagged_rows"] == [2, 3]
    assert document["class_count"] == 1


def test_separate_class_missing_rows_get_missing_class_id(tmp_path):
    path = write_table(
        tmp_path,
        "NA,flu\nNA,cold\n30,flu\n30,cold\n30,flu\n",
        name="separate.csv",
    )
    result = risk(read_table(path), ["age"], "separate-class", "journalist")

    missing = [record for record in result["records"] if record["class_id"] == "__MISSING__"]
    assert [record["row_number"] for record in missing] == [1, 2]
    assert {record["class_size"] for record in missing} == {2}
    assert all(record["flagged"] and record["participates"] for record in missing)

    size_three = [record for record in result["records"] if record["class_size"] == 3]
    assert [record["row_number"] for record in size_three] == [3, 4, 5]
    assert all(record["flagged"] is False for record in size_three)
    assert result["by_class_size"]["2"] == {
        "classes": 1, "records": 2, "flagged_records": 2,
    }


# ── 确定性 & 分层纪律（K3 / K7 / K8） ───────────────────────────────────

def test_double_run_risk_json_is_byte_identical(tmp_path):
    truth = load_truth("small")
    table_path = FIXTURES / "small" / "table.csv"
    if not table_path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）")
    decl_path = write_declaration(truth, tmp_path)
    first_code, first = cli_risk(tmp_path, table_path, decl_path, "separate-class", "marketer", out="a")
    second_code, second = cli_risk(tmp_path, table_path, decl_path, "separate-class", "marketer", out="b")
    assert first_code == second_code == 1
    assert first.read_bytes() == second.read_bytes(), "同输入两次运行必须逐字节相同"


def test_risk_json_goes_through_canonical_and_has_no_abs_path(tmp_path):
    truth = load_truth("tiny")
    table_path = FIXTURES / "tiny" / "table.csv"
    if not table_path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）")
    decl_path = write_declaration(truth, tmp_path)
    _, out = cli_risk(tmp_path, table_path, decl_path, "drop", "prosecutor")
    raw = out.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "不得带 BOM"
    assert b"\r\n" not in raw, "必须是 LF"
    text = raw.decode("utf-8")
    assert text == canonical.dumps(json.loads(text)), "risk.json 必须与 canonical.dumps 冻结参数一致"
    assert str(tmp_path) not in text and str(tmp_path).replace("\\", "/") not in text


def _imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def test_m4_module_respects_compute_layer_discipline():
    """K8：计算层不 import CLI、不读时钟/随机源、不写盘、不 import 真值工具。"""
    modules = _imported_modules(SRC / "m4_risk.py")
    forbidden = {"time", "datetime", "random", "secrets", "socket", "os", "pathlib"}
    assert not (modules & forbidden), "m4_risk 出现了禁用模块：%s" % sorted(modules & forbidden)
    assert not any(
        name == "cli" or name.startswith("anonymity_scanner.cli") or name.endswith(".cli")
        for name in modules
    ), "计算层不得 import CLI"
    assert not any(
        "fixture" in name or name.startswith("tools") or name.endswith(".tools")
        for name in modules
    ), "计算层不得 import 真值工具"
