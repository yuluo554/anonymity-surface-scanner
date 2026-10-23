"""M3 组合攻击面搜索验收（`plan/05` M3 DoD / `plan/03 §模块 M3`）。

五条互不替代的判据：

  1. **真值对照**：四组夹具的 `search` / `minimal_collapse_sets` 与真值逐项一致，
     三种场景（`default` / `empty_set_witness` / `no_solution`）逐组命中。
  2. **边界语义**：`[[]]` = 一个 QI 列都不能加；无解必须显式报 `no_solution`，不得用空数组冒充。
  3. **完整性三态**：预算截断不冒充穷尽；`drop` + 池含缺失 → `monotonicity-not-applicable`
     且**不剪枝**；剪枝成立时 `pruned_subsets > 0` 且结论与真值一致。
  4. **可复算**：分层曲线与逐子集暴露行数能只用 M2 的分组函数独立复算。
  5. **确定性 & 分层纪律**：双跑逐字节一致、走 `canonical`、无绝对路径，
     计算层不 import CLI / 真值工具。
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from anonymity_scanner import canonical
from anonymity_scanner.cli import main
from anonymity_scanner.exit_codes import CriteriaError
from anonymity_scanner.m2_classes import group_rows, k_of
from anonymity_scanner.m3_search import (
    COMPLETENESS_STATES,
    collapse_sets_status,
    completeness,
    outcome_for,
    search,
)
from anonymity_scanner.tableio import read_table

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
    """按 `declaration_order`（有序数组）写声明：`qi_columns` 必须是声明书写顺序。"""
    columns = {}
    for item in truth["declaration_order"]:
        spec = {"role": item["role"]}
        if "precision" in item:
            spec["precision"] = item["precision"]
        columns[item["name"]] = spec
    path = tmp_path / name
    path.write_text(json.dumps({"columns": columns}, ensure_ascii=False), encoding="utf-8")
    return path


def cli_search(tmp_path, table_path, decl_path, policy, k, budget, *extra, out="out"):
    code = main([
        "search", "--table", str(table_path), "--decl", str(decl_path),
        "--missing-policy", policy, "--k", str(k), "--budget", str(budget),
        "--out-dir", str(tmp_path / out), *extra,
    ])
    return code, tmp_path / out / "search.json"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


# ── 判据 1：四组夹具与真值逐项一致 ──────────────────────────────────────

@pytest.mark.parametrize("suite", SUITES)
def test_search_matches_truth_on_every_fixture(suite):
    truth = load_truth(suite)
    table = fixture_table(suite)
    spec = truth["meta"]
    result = search(
        table, truth["qi_columns"], truth["sensitive_columns"],
        spec["policy"], spec["threshold"], budget=spec["budget"],
    )
    expected = truth["search"]
    for key, value in expected.items():
        assert result[key] == value, "search.%s 与真值不一致" % key
    assert result["minimal_collapse_sets"] == truth["minimal_collapse_sets"]


@pytest.mark.parametrize("suite", SUITES)
def test_cli_search_writes_search_json_matching_truth(tmp_path, suite):
    truth = load_truth(suite)
    table_path = FIXTURES / suite / "table.csv"
    if not table_path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）")
    decl_path = write_declaration(truth, tmp_path)
    spec = truth["meta"]

    code, out_path = cli_search(
        tmp_path, table_path, decl_path, spec["policy"], spec["threshold"], spec["budget"]
    )
    document = load_json(out_path)
    assert code == 1, "四组夹具的完整 QI 声明都低于阈值 → 有违例（1）"
    assert document["command"] == "search"
    assert document["outcome"] == "violation"
    assert document["exit_code"] == 1
    for key, value in truth["search"].items():
        assert document["search"][key] == value, "search.json → search.%s 与真值不一致" % key


def test_search_scenarios_cover_all_three_boundaries():
    """每组的真值都必须恰好给出 default / 空集 / 无解三种场景。"""
    for suite in SUITES:
        names = {scenario["name"] for scenario in load_truth(suite)["search_scenarios"]}
        assert names == {"default", "empty_set_witness", "no_solution"}, suite


@pytest.mark.parametrize("suite", SUITES)
@pytest.mark.parametrize("scenario_name", ["default", "empty_set_witness", "no_solution"])
def test_search_scenarios_match_truth(suite, scenario_name):
    truth = load_truth(suite)
    table = fixture_table(suite)
    scenario = next(
        item for item in truth["search_scenarios"] if item["name"] == scenario_name
    )
    spec = truth["meta"]
    result = search(
        table, truth["qi_columns"], truth["sensitive_columns"],
        spec["policy"], scenario["threshold"], budget=None,
    )
    for key, value in scenario.items():
        if key == "name":
            continue
        assert result[key] == value, "%s/%s: search.%s 与真值不一致" % (suite, scenario_name, key)


# ── 判据 2：空集与无解两种边界显式表达 ──────────────────────────────────

@pytest.mark.parametrize("suite", SUITES)
def test_empty_set_witness_means_not_a_single_qi_column_may_be_added(suite):
    """`[[]]` 的语义 = 一个 QI 列都不能加（`plan/00` 勘误 E2），不是"什么都不用声明"。"""
    truth = load_truth(suite)
    table = fixture_table(suite)
    scenario = next(item for item in truth["search_scenarios"] if item["name"] == "empty_set_witness")
    result = search(
        table, truth["qi_columns"], truth["sensitive_columns"],
        truth["meta"]["policy"], scenario["threshold"], budget=None,
    )
    assert result["verdict"] == "ok"
    assert result["minimal_collapse_sets"] == [[]]
    assert result["empty_set_witness"] is True
    assert result["empty_set_k"] >= scenario["threshold"]


@pytest.mark.parametrize("suite", SUITES)
def test_no_solution_is_explicit_and_not_an_empty_success(suite):
    truth = load_truth(suite)
    table = fixture_table(suite)
    scenario = next(item for item in truth["search_scenarios"] if item["name"] == "no_solution")
    result = search(
        table, truth["qi_columns"], truth["sensitive_columns"],
        truth["meta"]["policy"], scenario["threshold"], budget=None,
    )
    assert result["verdict"] == "no_solution"
    assert result["minimal_collapse_sets"] == []
    assert result["empty_set_witness"] is False
    assert result["empty_set_k"] < scenario["threshold"]
    assert result["evaluated_subsets"] == 1, "无解时只需要算出空集"


# ── 判据 3：完整性三态、预算与剪枝 ─────────────────────────────────────

def test_completeness_states_are_closed_and_mutually_exclusive():
    assert completeness(True, True) == "exhausted"
    assert completeness(False, True) == "monotonicity-not-applicable"
    assert completeness(True, False) == "budget-truncated"
    assert completeness(False, False) == "budget-truncated", "预算截断优先于单调性不适用"
    assert completeness(False, True, required=False) == "exhausted", "无解时没有需要评估的子集"
    assert set(COMPLETENESS_STATES) == {"exhausted", "budget-truncated", "monotonicity-not-applicable"}
    assert collapse_sets_status("exhausted") == "exhaustive"
    for state in ("budget-truncated", "monotonicity-not-applicable"):
        assert collapse_sets_status(state) == "non-exhaustive"


def test_budget_truncation_never_pretends_exhaustive():
    truth = load_truth("budget")
    table = fixture_table("budget")
    full = search(
        table, truth["qi_columns"], truth["sensitive_columns"],
        truth["meta"]["policy"], truth["meta"]["threshold"], budget=truth["meta"]["budget"],
    )
    truncated = search(
        table, truth["qi_columns"], truth["sensitive_columns"],
        truth["meta"]["policy"], truth["meta"]["threshold"], budget=10,
    )
    assert truncated["evaluated_subsets"] == 10, "预算就是已评估子集数的硬上限（含空集）"
    assert truncated["completeness"] == "budget-truncated"
    assert truncated["non_exhaustive"] is True
    assert truncated["collapse_sets_status"] == "non-exhaustive"
    assert full["completeness"] == "budget-truncated"
    assert full["evaluated_subsets"] == truth["search"]["evaluated_subsets"]
    assert full["subset_space"] == truth["search"]["subset_space"]


# ── 判据 3b：`empty_set_witness` 必须有证据（D3 负控） ───────────────────

def test_budget_truncated_empty_set_witness_is_false(tmp_path):
    """预算只够算空集时，`empty_set_witness` 必须是 `false`（「没算过」≠「不存在」）。

    修复前：`budget=1` 会把 `[[]]` 留在 `minimal_collapse_sets` 里 → `empty_set_witness`
    恒 `true`，而 `gate.md` 会印出可证伪的「一个 QI 列都不能加」。
    """
    table_path = tmp_path / "t.csv"
    # 4 行、两列：单独任何一列都不安全（k=2 < 3），所以穷尽时空集确实是边界集。
    table_path.write_bytes(b"age,zip\n30,100\n30,101\n31,100\n31,101\n")
    table = read_table(table_path)
    pool = ["age", "zip"]

    truncated = search(table, pool, [], "drop", 3, budget=1)
    assert truncated["completeness"] == "budget-truncated"
    assert truncated["evaluated_subsets"] == 1, "预算只够算空集"
    assert truncated["empty_set_witness"] is False, "没算过任何单列扩展，不得断言边界"
    assert truncated["minimal_collapse_sets"] == [[]], "边界集列表本身不变（只是证据不足）"

    exhausted = search(table, pool, [], "drop", 3, budget=None)
    assert exhausted["completeness"] == "exhausted"
    assert exhausted["empty_set_witness"] is True, "穷尽且所有单列都不安全 → 证据成立"


def test_some_single_columns_evaluated_but_not_all_keeps_witness_false(tmp_path):
    """预算够算一部分单列扩展时，同样不得断言空集是边界集。"""
    table_path = tmp_path / "t.csv"
    table_path.write_bytes(b"age,zip,sex\n30,100,m\n30,101,m\n31,100,f\n31,101,f\n")
    result = search(read_table(table_path), ["age", "zip", "sex"], [], "drop", 3, budget=2)
    assert result["completeness"] == "budget-truncated"
    assert result["evaluated_subsets"] == 2, "空集 + 一个单列"
    assert result["empty_set_witness"] is False


def test_require_exhaustive_on_truncated_budget_is_undecidable(tmp_path, capsys):
    truth = load_truth("budget")
    table_path = FIXTURES / "budget" / "table.csv"
    if not table_path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）")
    decl_path = write_declaration(truth, tmp_path)
    code, out_path = cli_search(
        tmp_path, table_path, decl_path, "drop", 5, 10, "--require-exhaustive", out="out"
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "截断" in captured.err
    assert not out_path.exists(), "无法裁决时不得写出冒充结论的产物"


def test_drop_with_missing_in_pool_never_prunes():
    """K5：`drop` + 候选池含缺失 → 单调性不适用，剪枝必须停用（small 实测）。"""
    truth = load_truth("small")
    table = fixture_table("small")
    result = search(
        table, truth["qi_columns"], truth["sensitive_columns"],
        "drop", truth["meta"]["threshold"], budget=None,
    )
    assert result["monotonicity_applicable"] is False
    assert result["completeness"] == "monotonicity-not-applicable"
    assert result["pruned_subsets"] == 0
    assert result["evaluated_subsets"] == result["subset_space"] + 1, "不剪枝 → 全部子集都实算"
    assert result["minimal_collapse_sets"] == truth["minimal_collapse_sets"], "结论仍要与真值一致"


def test_policy_that_keeps_row_set_is_monotone_on_the_same_table():
    truth = load_truth("small")
    table = fixture_table("small")
    result = search(
        table, truth["qi_columns"], truth["sensitive_columns"],
        "single-column", truth["meta"]["threshold"], budget=None,
    )
    assert result["monotonicity_applicable"] is True
    assert result["completeness"] == "exhausted"
    assert result["pruned_subsets"] > 0


def test_pruning_is_active_and_fully_accounted_for():
    """剪枝只影响速度：被剪掉 + 已评估 = 全部非空子集，且边界集与真值一致。"""
    truth = load_truth("prune")
    table = fixture_table("prune")
    result = search(
        table, truth["qi_columns"], truth["sensitive_columns"],
        truth["meta"]["policy"], truth["meta"]["threshold"], budget=truth["meta"]["budget"],
    )
    assert result["pruned_subsets"] == truth["search"]["pruned_subsets"] == 25
    assert result["evaluated_subsets"] == truth["search"]["evaluated_subsets"] == 7
    assert result["evaluated_subsets"] - 1 + result["pruned_subsets"] == result["subset_space"]
    assert result["completeness"] == "exhausted"
    assert result["minimal_collapse_sets"] == [["age", "region"]]


def test_verdict_follows_declared_qis_and_never_claims_pass_when_incomplete(tmp_path):
    """§4.6：0 要求所有声明阈值满足**且**穷尽；非穷尽只允许 1（已证违例）或 2。"""
    # 6 行完全相同 → k=6 ≥ 5；预算够 → pass。
    rows = "\n".join(["30,flu"] * 6)
    table_path = tmp_path / "safe.csv"
    table_path.write_bytes(("age,disease\n" + rows + "\n").encode("utf-8"))
    decl_path = tmp_path / "safe-decl.json"
    decl_path.write_text(json.dumps({"columns": {"age": {"role": "qi"}}}), encoding="utf-8")
    table = read_table(table_path)

    complete = search(table, ["age"], [], "drop", 5, budget=8)
    assert complete["completeness"] == "exhausted"
    assert complete["declared_k"] == 6
    assert outcome_for(complete) == "pass"

    # 同一张表：预算只够算空集 → 截断，声明集合虽然安全也不得判 pass。
    truncated = search(table, ["age"], [], "drop", 5, budget=1)
    assert truncated["completeness"] == "budget-truncated"
    assert outcome_for(truncated) == "undecidable"

    # 池里带缺失（drop）：单调性不适用 → 同样不得冒充 pass。
    noisy = tmp_path / "noisy.csv"
    noisy.write_bytes(b"age,disease\n30,flu\n30,flu\n30,flu\n30,flu\n30,flu\nNA,flu\n")
    non_monotone = search(read_table(noisy), ["age"], [], "drop", 5, budget=8)
    assert non_monotone["monotonicity_applicable"] is False
    assert non_monotone["declared_k"] == 5
    assert outcome_for(non_monotone) == "undecidable"


def test_search_rejects_invalid_numeric_inputs():
    """纯函数层的 fail-closed：坏阈值 / 坏预算一律 CriteriaError（不返回空结果）。"""
    class _Empty:
        rows = []
        header = []

        def values(self, name):
            return []

        def column_index(self, name):
            return None

    fake = _Empty()
    for bad in (0, -1, True, "5", None):
        with pytest.raises(CriteriaError):
            search(fake, [], [], "drop", bad, budget=4)
    with pytest.raises(CriteriaError):
        search(fake, [], [], "drop", 5, budget=0)
    with pytest.raises(CriteriaError):
        search(fake, [], [], "drop", 5, budget=-2)
    with pytest.raises(CriteriaError):
        search(fake, ["a", "a"], [], "drop", 5, budget=4)


# ── 判据 4：分层曲线与暴露行数可复算 ────────────────────────────────────

@pytest.mark.parametrize("suite", SUITES)
def test_strata_and_exposed_rows_are_recomputable_with_m2(suite):
    truth = load_truth(suite)
    table = fixture_table(suite)
    policy = truth["meta"]["policy"]
    threshold = truth["meta"]["threshold"]
    result = search(
        table, truth["qi_columns"], truth["sensitive_columns"],
        policy, threshold, budget=truth["meta"]["budget"],
    )

    # 逐子集：k 与暴露行数都能只用 M2 的分组函数重算。
    for item in result["subsets"]:
        classes, _undecided, _values = group_rows(table, item["columns"], policy)
        assert item["k"] == k_of(classes)
        exposed = sum(len(numbers) for numbers in classes.values() if len(numbers) < threshold)
        assert item["exposed_rows"] == exposed
        assert item["safe"] is (item["k"] is not None and item["k"] >= threshold)

    # 分层：按 |S| 聚合 min_k / exposed_rows，同层并列时取字典序最小的子集。
    by_size = {}
    for item in result["subsets"]:
        by_size.setdefault(len(item["columns"]), []).append(item)
    assert [entry["size"] for entry in result["strata"]] == sorted(by_size)
    for entry in result["strata"]:
        items = by_size[entry["size"]]
        assert entry["evaluated"] == len(items)
        defined = [item["k"] for item in items if item["k"] is not None]
        expected_min = min(defined) if defined else None
        assert entry["min_k"] == expected_min
        if expected_min is None:
            assert entry["worst_subset"] is None
            assert entry["exposed_rows"] == 0
        else:
            worst = next(
                item for item in items
                if item["k"] == expected_min and item["columns"] == entry["worst_subset"]
            )
            assert entry["exposed_rows"] == worst["exposed_rows"]


# ── 判据 5：确定性、序列化与计算层纪律 ─────────────────────────────────

def test_double_run_search_json_is_byte_identical(tmp_path):
    truth = load_truth("small")
    table_path = FIXTURES / "small" / "table.csv"
    if not table_path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）")
    decl_path = write_declaration(truth, tmp_path)
    first_code, first = cli_search(
        tmp_path, table_path, decl_path, truth["meta"]["policy"],
        truth["meta"]["threshold"], truth["meta"]["budget"], out="a",
    )
    second_code, second = cli_search(
        tmp_path, table_path, decl_path, truth["meta"]["policy"],
        truth["meta"]["threshold"], truth["meta"]["budget"], out="b",
    )
    assert first_code == second_code == 1
    assert first.read_bytes() == second.read_bytes()


def test_search_json_goes_through_canonical_and_has_no_abs_path(tmp_path):
    truth = load_truth("tiny")
    table_path = FIXTURES / "tiny" / "table.csv"
    if not table_path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）")
    decl_path = write_declaration(truth, tmp_path)
    _, out = cli_search(
        tmp_path, table_path, decl_path, truth["meta"]["policy"],
        truth["meta"]["threshold"], truth["meta"]["budget"],
    )
    raw = out.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "不得带 BOM"
    assert b"\r\n" not in raw, "必须是 LF"
    text = raw.decode("utf-8")
    assert text == canonical.dumps(json.loads(text)), "search.json 必须与 canonical.dumps 冻结参数一致"
    assert str(tmp_path) not in text and str(tmp_path).replace("\\", "/") not in text


def test_pool_input_order_does_not_change_the_conclusion():
    """枚举顺序由排序决定，与声明书写顺序无关；`qi_columns` 仍回显声明顺序。"""
    truth = load_truth("tiny")
    table = fixture_table("tiny")
    forward = search(
        table, truth["qi_columns"], truth["sensitive_columns"],
        "drop", truth["meta"]["threshold"], budget=truth["meta"]["budget"],
    )
    backward = search(
        table, list(reversed(truth["qi_columns"])), truth["sensitive_columns"],
        "drop", truth["meta"]["threshold"], budget=truth["meta"]["budget"],
    )
    assert forward["pool"] == backward["pool"] == sorted(truth["qi_columns"])
    assert forward["qi_columns"] == list(truth["qi_columns"])
    assert backward["qi_columns"] == list(reversed(truth["qi_columns"]))
    assert forward["minimal_collapse_sets"] == backward["minimal_collapse_sets"]
    assert forward["evaluated_subsets"] == backward["evaluated_subsets"]


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


def test_m3_module_respects_compute_layer_discipline():
    """K8 / K10：不 import CLI、不读时钟/随机/环境、不 import 真值生成器。"""
    modules = _imported_modules(SRC / "m3_search.py")
    forbidden = {"time", "datetime", "random", "secrets", "socket", "os", "pathlib"}
    assert not (modules & forbidden), "m3_search 出现了禁用模块：%s" % sorted(modules & forbidden)
    assert not any(name == "cli" or name.startswith("anonymity_scanner.cli") for name in modules)
    assert not any("fixture_oracle" in name or "gen_fixtures" in name for name in modules)
    assert any("m2_classes" in name for name in modules), "M3 必须复用 M2 的分组函数（K1）"
