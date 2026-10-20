"""M2 等价类引擎验收（`plan/05` M2 DoD / `plan/03 §模块 M2`）。

四条互不替代的判据：
  1. **真值对照**：`scan` 的 `scan.json` 与 `small/truth.json` 的 `by_policy` 逐项一致（三策略各一组）。
  2. **人工推导**：`single-column` / `separate-class` 的 l 值由本文件手算成常量写死，
     不与真值互证（针对 sdcMicro #363 型"缺失值下 l 算错"的坑）。
  3. **可手算**：tiny 的 12 行违例三件套能按文档逐条复核。
  4. **边界有定义**：空表 / 单行表 / 全 QI 相同表都有明确行为且被锁定。
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from anonymity_scanner import canonical
from anonymity_scanner.cli import main
from anonymity_scanner.m2_classes import group_rows, k_of, summarize
from anonymity_scanner.tableio import read_table

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "data" / "fixtures"
SUITES = ("tiny", "small", "prune", "budget")
POLICIES = ("drop", "single-column", "separate-class")
SRC = ROOT / "src" / "anonymity_scanner"


def load_truth(suite):
    return json.loads((FIXTURES / suite / "truth.json").read_text(encoding="utf-8"))


def policy_block(truth, policy):
    """`same_as` 回退：无缺失的夹具把后两种策略写成 {"same_as": "drop"}。"""
    block = truth["by_policy"][policy]
    if "same_as" in block:
        block = truth["by_policy"][block["same_as"]]
    return block


def write_declaration(truth, tmp_path):
    """按 `declaration_order`（**有序数组**）写声明：等价类键序 = 声明书写顺序。

    不能直接抄 truth["declaration"]：`canonical.dumps(sort_keys=True)` 已把 JSON 对象的键序
    排成字典序，拿它当声明会让键序从 age,zip,dob,sex 变成 age,dob,sex,zip。
    """
    columns = {}
    for item in truth["declaration_order"]:
        spec = {"role": item["role"]}
        if "precision" in item:
            spec["precision"] = item["precision"]
        columns[item["name"]] = spec
    path = tmp_path / "decl.json"
    path.write_text(json.dumps({"columns": columns}, ensure_ascii=False), encoding="utf-8")
    return path


def fixture_table(suite):
    path = FIXTURES / suite / "table.csv"
    if not path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）；用 tools/gen_fixtures.py 生成后复跑")
    return read_table(path)


def scan(tmp_path, table_path, decl_path, policy, k, *extra, out="out"):
    code = main([
        "scan", "--table", str(table_path), "--decl", str(decl_path),
        "--missing-policy", policy, "--k", str(k), "--out-dir", str(tmp_path / out), *extra,
    ])
    return code, tmp_path / out / "scan.json"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


# ── 判据 1：scan.json 与 small/truth.json 的 by_policy 逐项一致 ──────────

@pytest.mark.parametrize("policy", POLICIES)
def test_small_scan_matches_truth_by_policy(tmp_path, policy):
    truth = load_truth("small")
    table_path = FIXTURES / "small" / "table.csv"
    if not table_path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）")
    decl_path = write_declaration(truth, tmp_path)
    expected = policy_block(truth, policy)

    code, out = scan(tmp_path, table_path, decl_path, policy, truth["meta"]["threshold"])
    document = load_json(out)
    metrics = document["k_l_t"]

    assert code == 1, "small 在三种策略下都有 k<5 的类 → 退出码必须是有违例（1）"
    assert metrics["k"] == expected["k"]
    assert metrics["l"] == expected["l"]
    assert metrics["t"] == expected["t"]
    assert metrics["class_count"] == expected["class_count"]
    assert metrics["class_size_histogram"] == expected["class_size_histogram"]
    assert metrics["undecided_rows"] == expected["undecided_rows"]
    assert metrics["missing_class"] == expected["missing_class"]
    assert document["violations"] == expected["violations"]
    assert document["unique_records"] == expected["unique_records"]


@pytest.mark.parametrize("suite", SUITES)
@pytest.mark.parametrize("policy", POLICIES)
def test_all_fixtures_match_truth_by_policy(suite, policy):
    """四组夹具 × 三策略：真值是唯一对照（`drop` 之外的块可能与 `drop` 相同）。"""
    truth = load_truth(suite)
    table = fixture_table(suite)
    expected = policy_block(truth, policy)
    result = summarize(
        table, truth["qi_columns"], truth["sensitive_columns"],
        policy, truth["meta"]["threshold"],
    )
    assert result["k_l_t"]["k"] == expected["k"]
    assert result["k_l_t"]["l"] == expected["l"]
    assert result["k_l_t"]["t"] == expected["t"]
    assert result["k_l_t"]["class_count"] == expected["class_count"]
    assert result["k_l_t"]["class_size_histogram"] == expected["class_size_histogram"]
    assert result["k_l_t"]["undecided_rows"] == expected["undecided_rows"]
    assert result["k_l_t"]["missing_class"] == expected["missing_class"]
    assert result["violations"] == expected["violations"]
    assert result["unique_records"] == expected["unique_records"]


def test_empty_qi_set_uses_all_rows_under_drop():
    """空集语义（`plan/00` 勘误 E2 / `data/README.md` §4.5）：

    空集下没有任何列参与分组 → 没有"含缺失的行"概念，`drop` 也必须保留全部行。
    small 的期望值是 **60**（不是 56）。M3 的 k(∅) 直接依赖这条。
    """
    truth = load_truth("small")
    table = fixture_table("small")
    for policy in POLICIES:
        classes, undecided, _ = group_rows(table, [], policy)
        assert undecided == []
        assert k_of(classes) == truth["k_by_columns"]["[]"] == 60


# ── 判据 2：l 值人工推导后写死（sdcMicro #363 型坑） ─────────────────────

def _l_trap_table(tmp_path):
    """6 行小表，三策略给出**三种不同**的 l：

        age,sex,disease
        NA, M,flu      ← 缺失（age）
        NA, F,cold
        NA, M,flu
        NA, F,cold
        30, M,flu
        30, M,cold

    人工推导：
      * drop           —— 1–4 行被丢；唯一类 {5,6} 内 disease = {flu,cold} → l = 2
      * single-column  —— 键 age=NULL|sex=M {1,3}、age=NULL|sex=F {2,4}、age=30|sex=M {5,6}；
                          逐类 l = 1 / 1 / 2 → 全局 l = **1**
      * separate-class —— __MISSING__ {1,2,3,4} 内 disease = {flu,cold} → l = 2；
                          类 {5,6} 的 l = 2 → 全局 l = **2**

    `single-column` 的 1 与 `separate-class` 的 2 是手算出来的常量，不是从真值抄的
    （small 夹具三策略的 l 恰好都为 1，无法暴露这个坑）。
    """
    path = tmp_path / "trap.csv"
    path.write_bytes(
        (
            "age,sex,disease\n"
            "NA,M,flu\n"
            "NA,F,cold\n"
            "NA,M,flu\n"
            "NA,F,cold\n"
            "30,M,flu\n"
            "30,M,cold\n"
        ).encode("utf-8")
    )
    decl = tmp_path / "trap-decl.json"
    decl.write_text(
        json.dumps(
            {"columns": {"age": {"role": "qi"}, "sex": {"role": "qi"}, "disease": {"role": "sensitive"}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return read_table(path), decl


def test_l_hand_derived_single_column_constant(tmp_path):
    table, _ = _l_trap_table(tmp_path)
    result = summarize(table, ["age", "sex"], ["disease"], "single-column", 2)
    assert result["k_l_t"]["l"] == 1, "single-column 下逐类拆开后每类 l=1（手算常量）"
    assert result["k_l_t"]["k"] == 2
    assert result["k_l_t"]["class_count"] == 3
    assert result["k_l_t"]["undecided_rows"] == []
    assert result["k_l_t"]["t"] == 0.5, "单列分布 (flu,flu) 对全表 (3/6,3/6) 的总变差 = 0.5"


def test_l_hand_derived_separate_class_constant(tmp_path):
    table, _ = _l_trap_table(tmp_path)
    result = summarize(table, ["age", "sex"], ["disease"], "separate-class", 2)
    assert result["k_l_t"]["l"] == 2, "缺失行合并成一个类后类内 disease 有两种 → l=2（手算常量）"
    assert result["k_l_t"]["k"] == 2
    assert result["k_l_t"]["class_count"] == 2
    assert result["k_l_t"]["missing_class"] == {"k": 4, "row_numbers": [1, 2, 3, 4]}
    assert result["k_l_t"]["t"] == 0.0, "缺失类与正常类的分布都与全表一致 → t=0"


def test_l_hand_derived_drop_constant(tmp_path):
    table, _ = _l_trap_table(tmp_path)
    result = summarize(table, ["age", "sex"], ["disease"], "drop", 2)
    assert result["k_l_t"]["l"] == 2
    assert result["k_l_t"]["class_count"] == 1
    assert result["k_l_t"]["undecided_rows"] == [1, 2, 3, 4]
    assert result["k_l_t"]["t"] == 0.0


def test_l_trap_three_policies_are_not_the_same_result(tmp_path):
    """三策略必须真的算三遍：l 值集合是 {2, 1, 2}，且 single-column 与另两者不同。"""
    table, _ = _l_trap_table(tmp_path)
    values = {
        policy: summarize(table, ["age", "sex"], ["disease"], policy, 2)["k_l_t"]["l"]
        for policy in POLICIES
    }
    assert values == {"drop": 2, "single-column": 1, "separate-class": 2}


# ── 判据 3：tiny 的违例三件套可手算 ──────────────────────────────────────

def test_tiny_violations_are_hand_checkable():
    """tiny 12 行：完整 QI 组合下 12 个等价类各 1 行 → 12 条违例，行号 1..12。"""
    truth = load_truth("tiny")
    table = fixture_table("tiny")
    result = summarize(table, truth["qi_columns"], truth["sensitive_columns"], "drop", 3)
    assert result["k_l_t"]["k"] == 1
    assert result["k_l_t"]["class_count"] == 12
    assert len(result["violations"]) == 12
    assert all(item["count"] == 1 and len(item["row_numbers"]) == 1 for item in result["violations"])
    flattened = sorted(number for item in result["violations"] for number in item["row_numbers"])
    assert flattened == list(range(1, 13))
    assert result["unique_records"] == list(range(1, 13))
    assert result["verdict"] == "violation"


# ── 判据 4：边界表（空表 / 单行 / 全同） ─────────────────────────────────

def _boundary_inputs(tmp_path, body, columns=("age", "disease")):
    table_path = tmp_path / "data.csv"
    table_path.write_bytes(((",".join(columns) + "\n" + body).encode("utf-8")))
    decl_path = tmp_path / "decl.json"
    decl = {"columns": {"age": {"role": "qi"}, "disease": {"role": "sensitive"}}}
    decl_path.write_text(json.dumps(decl, ensure_ascii=False), encoding="utf-8")
    return table_path, decl_path


def test_empty_table_is_undecidable_with_reason(tmp_path, capsys):
    """只有表头：k=null + undefined_reason='empty_table'，退出码 2（不是 0）。"""
    table_path, decl_path = _boundary_inputs(tmp_path, "")
    code, out = scan(tmp_path, table_path, decl_path, "drop", 2)
    document = load_json(out)
    assert code == 2
    assert document["k_l_t"]["k"] is None
    assert document["k_l_t"]["l"] is None
    assert document["k_l_t"]["t"] is None
    assert document["k_l_t"]["class_count"] == 0
    assert document["undefined_reason"] == "empty_table"
    assert document["verdict"] == "undecidable"
    assert document["exit_code"] == 2
    assert document["violations"] == []


def test_single_row_table_has_defined_behaviour(tmp_path):
    table_path, decl_path = _boundary_inputs(tmp_path, "30,flu\n")
    code, out = scan(tmp_path, table_path, decl_path, "drop", 2)
    document = load_json(out)
    assert code == 1, "单行表的 k=1 < 2 → 有违例"
    assert document["k_l_t"]["k"] == 1
    assert document["k_l_t"]["class_count"] == 1
    assert document["k_l_t"]["class_size_histogram"] == {"1": 1}
    assert document["violations"] == [{"key": "age=30", "count": 1, "row_numbers": [1]}]


def test_all_qi_identical_table_collapses_to_one_class(tmp_path):
    table_path, decl_path = _boundary_inputs(tmp_path, "30,flu\n30,cold\n30,flu\n30,cold\n30,flu\n")
    code, out = scan(tmp_path, table_path, decl_path, "drop", 5)
    document = load_json(out)
    assert code == 0, "k=5 恰好达到门限 → 通过"
    assert document["k_l_t"]["k"] == 5
    assert document["k_l_t"]["class_count"] == 1
    assert document["k_l_t"]["class_size_histogram"] == {"5": 1}
    assert document["k_l_t"]["l"] == 2
    assert document["k_l_t"]["t"] == 0.0
    assert document["violations"] == []


def test_all_rows_dropped_is_undecidable_not_pass(tmp_path):
    """全部行都含缺失、策略为 drop：没有参与分组的行 → 算不出 k，按 2 处理。"""
    table_path, decl_path = _boundary_inputs(tmp_path, "NA,flu\n-,cold\n")
    code, out = scan(tmp_path, table_path, decl_path, "drop", 2)
    document = load_json(out)
    assert code == 2
    assert document["k_l_t"]["k"] is None
    assert document["undefined_reason"] == "no_participating_rows"
    assert document["k_l_t"]["undecided_rows"] == [1, 2]


def test_l_threshold_without_sensitive_column_is_undecidable(tmp_path, capsys):
    table_path = tmp_path / "data.csv"
    table_path.write_bytes(b"age\n30\n31\n")
    decl_path = tmp_path / "decl.json"
    decl_path.write_text(json.dumps({"columns": {"age": {"role": "qi"}}}), encoding="utf-8")
    code = main([
        "scan", "--table", str(table_path), "--decl", str(decl_path),
        "--missing-policy", "drop", "--k", "1", "--l", "2", "--out-dir", str(tmp_path / "out"),
    ])
    assert code == 2
    assert "sensitive" in capsys.readouterr().err


# ── 确定性 & 序列化纪律（K3 / K7 / K8） ──────────────────────────────────

def test_double_run_scan_json_is_byte_identical(tmp_path):
    truth = load_truth("small")
    table_path = FIXTURES / "small" / "table.csv"
    if not table_path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）")
    decl_path = write_declaration(truth, tmp_path)
    first_code, first = scan(tmp_path, table_path, decl_path, "separate-class", 5, out="a")
    second_code, second = scan(tmp_path, table_path, decl_path, "separate-class", 5, out="b")
    assert first_code == second_code == 1
    assert first.read_bytes() == second.read_bytes(), "同输入两次运行必须逐字节相同"


def test_scan_json_goes_through_canonical_and_has_no_abs_path(tmp_path):
    truth = load_truth("tiny")
    table_path = FIXTURES / "tiny" / "table.csv"
    if not table_path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）")
    decl_path = write_declaration(truth, tmp_path)
    _, out = scan(tmp_path, table_path, decl_path, "drop", 3)
    raw = out.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "不得带 BOM"
    assert b"\r\n" not in raw, "必须是 LF"
    text = raw.decode("utf-8")
    assert text == canonical.dumps(json.loads(text)), "scan.json 必须与 canonical.dumps 冻结参数一致"
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


def test_m2_module_respects_compute_layer_discipline():
    """K8：计算层不 import CLI、不读时钟/随机源、不写盘。"""
    modules = _imported_modules(SRC / "m2_classes.py")
    forbidden = {"time", "datetime", "random", "secrets", "socket", "os", "pathlib"}
    assert not (modules & forbidden), "m2_classes 出现了禁用模块：%s" % sorted(modules & forbidden)
    assert not any(name == "cli" or name.startswith("anonymity_scanner.cli") for name in modules)
