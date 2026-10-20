"""契约测试：退出码、参数形态、未实现模块的 fail-closed。

这些断言是 M0 的核心交付——计算面还没实现，但**契约面现在就被锁住**，
后续里程碑不会把"缺参数"或"未实现"悄悄变成退出码 0。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from anonymity_scanner import __version__
from anonymity_scanner.cli import main
from anonymity_scanner.exit_codes import (
    PASS,
    UNDECIDABLE,
    VIOLATION,
    CriteriaError,
    ScannerError,
    map_outcome,
)

ROOT = Path(__file__).resolve().parent.parent


def write_table(tmp_path, rows, header=("age", "zip", "disease")):
    path = tmp_path / "data.csv"
    lines = [",".join(header)] + [",".join(row) for row in rows]
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return path


def write_decl(tmp_path, columns):
    path = tmp_path / "decl.json"
    path.write_bytes(json.dumps({"columns": columns}, ensure_ascii=False).encode("utf-8"))
    return path


@pytest.fixture()
def table(tmp_path):
    return write_table(tmp_path, [("30", "100", "flu"), ("31", "100", "cold"), ("30", "101", "flu")])


@pytest.fixture()
def decl(tmp_path):
    return write_decl(tmp_path, {"age": {"role": "qi"}, "zip": {"role": "qi"}, "disease": {"role": "sensitive"}})


# ── 退出码映射（K2：单点） ────────────────────────────────────────────────

def test_map_outcome_closed_set():
    assert map_outcome("pass") == PASS
    assert map_outcome("violation") == VIOLATION
    assert map_outcome("undecidable") == UNDECIDABLE


@pytest.mark.parametrize("value", ["", None, "PASS", "ok", 0, [], {}])
def test_map_outcome_unknown_never_returns_pass(value):
    """fail-closed：不认识的取值一律 2，绝不退化为 0。"""
    assert map_outcome(value) == UNDECIDABLE


def test_map_outcome_error_object_uses_its_code():
    assert map_outcome(CriteriaError("bad criteria")) == UNDECIDABLE
    assert isinstance(CriteriaError("x"), ScannerError)


# ── 版本与帮助 ────────────────────────────────────────────────────────────

def test_version_flag(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_subcommand_is_undecidable(capsys):
    """没给子命令 = 无从裁决，不是"通过"。"""
    assert main([]) == UNDECIDABLE
    assert "usage" in capsys.readouterr().err.lower()


def test_unknown_subcommand_exits_2(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["nope"])
    assert excinfo.value.code == 2


# ── 未实现模块必须 fail-closed ────────────────────────────────────────────

def test_schema_reports_module_not_ready(capsys, table, decl, tmp_path):
    code = main(["schema", "--table", str(table), "--decl", str(decl), "--out-dir", str(tmp_path / "out")])
    captured = capsys.readouterr()
    assert code == UNDECIDABLE
    assert "MODULE_NOT_READY" in captured.err
    assert "M1" in captured.err
    assert not (tmp_path / "out").exists(), "未实现时不得写出任何产物"


def test_scan_requires_missing_policy(capsys, table, decl, tmp_path):
    code = main([
        "scan", "--table", str(table), "--decl", str(decl),
        "--k", "3", "--out-dir", str(tmp_path / "out"),
    ])
    captured = capsys.readouterr()
    assert code == UNDECIDABLE
    assert "缺失值策略未指定" in captured.err


def test_scan_requires_k(capsys, table, decl, tmp_path):
    code = main([
        "scan", "--table", str(table), "--decl", str(decl),
        "--missing-policy", "drop", "--out-dir", str(tmp_path / "out"),
    ])
    assert code == UNDECIDABLE
    assert "k 门限" in capsys.readouterr().err


@pytest.mark.parametrize("policy", ["Drop", "none", "single", ""])
def test_scan_rejects_unknown_missing_policy(capsys, table, decl, tmp_path, policy):
    code = main([
        "scan", "--table", str(table), "--decl", str(decl),
        "--missing-policy", policy, "--k", "3", "--out-dir", str(tmp_path / "out"),
    ])
    assert code == UNDECIDABLE


@pytest.mark.parametrize("budget", ["0", "-1"])
def test_search_rejects_non_positive_budget(capsys, table, decl, tmp_path, budget):
    code = main([
        "search", "--table", str(table), "--decl", str(decl),
        "--missing-policy", "drop", "--k", "3", "--budget", budget,
        "--out-dir", str(tmp_path / "out"),
    ])
    assert code == UNDECIDABLE
    assert "搜索预算" in capsys.readouterr().err


def test_search_requires_budget(capsys, table, decl, tmp_path):
    code = main([
        "search", "--table", str(table), "--decl", str(decl),
        "--missing-policy", "drop", "--k", "3", "--out-dir", str(tmp_path / "out"),
    ])
    assert code == UNDECIDABLE
    assert "搜索预算未指定" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_search_requires_missing_policy(capsys, table, decl, tmp_path):
    code = main([
        "search", "--table", str(table), "--decl", str(decl),
        "--k", "3", "--budget", "10", "--out-dir", str(tmp_path / "out"),
    ])
    assert code == UNDECIDABLE
    assert "缺失值策略未指定" in capsys.readouterr().err


def test_search_with_valid_arguments_computes(capsys, table, decl, tmp_path):
    """M3 落地后：有效参数必须真的算出结果（不再 MODULE_NOT_READY），且产物按契约落盘。"""
    code = main([
        "search", "--table", str(table), "--decl", str(decl),
        "--missing-policy", "drop", "--k", "3", "--budget", "10",
        "--out-dir", str(tmp_path / "out"),
    ])
    captured = capsys.readouterr()
    assert "MODULE_NOT_READY" not in captured.err
    assert code == VIOLATION, "完整 QI 只有 k=1 < 3 → 有违例（1）"
    document = json.loads((tmp_path / "out" / "search.json").read_text(encoding="utf-8"))
    result = document["search"]
    assert result["verdict"] == "ok"
    assert result["completeness"] == "exhausted"
    assert result["empty_set_k"] == 3
    assert result["minimal_collapse_sets"] == [[]], "两列单独都不安全 → 空集是边界集"
    assert result["empty_set_witness"] is True
    assert document["outcome"] == "violation"
    assert document["exit_code"] == VIOLATION


def test_risk_requires_attacker(capsys, table, decl, tmp_path):
    code = main([
        "risk", "--table", str(table), "--decl", str(decl),
        "--missing-policy", "drop", "--out-dir", str(tmp_path / "out"),
    ])
    assert code == UNDECIDABLE
    assert "攻击者模型未指定" in capsys.readouterr().err
    assert not (tmp_path / "out").exists(), "缺参数时不得写出任何产物"


def test_risk_requires_missing_policy(capsys, table, decl, tmp_path):
    code = main([
        "risk", "--table", str(table), "--decl", str(decl),
        "--attacker", "journalist", "--out-dir", str(tmp_path / "out"),
    ])
    assert code == UNDECIDABLE
    assert "缺失值策略未指定" in capsys.readouterr().err


def test_risk_rejects_unknown_attacker(capsys, table, decl, tmp_path):
    code = main([
        "risk", "--table", str(table), "--decl", str(decl),
        "--missing-policy", "drop", "--attacker", "nobody",
        "--out-dir", str(tmp_path / "out"),
    ])
    assert code == UNDECIDABLE
    assert "攻击者模型" in capsys.readouterr().err


def test_risk_with_valid_arguments_computes(capsys, table, decl, tmp_path):
    """M4 落地后：有效参数必须真的算出结果（不再 MODULE_NOT_READY），且产物按契约落盘。"""
    code = main([
        "risk", "--table", str(table), "--decl", str(decl),
        "--missing-policy", "separate-class", "--attacker", "journalist",
        "--out-dir", str(tmp_path / "out"),
    ])
    captured = capsys.readouterr()
    assert "MODULE_NOT_READY" not in captured.err
    assert code == VIOLATION, "三行的 (age, zip) 各不相同 → 3 个 size=1 的类，journalist 命中"
    document = json.loads((tmp_path / "out" / "risk.json").read_text(encoding="utf-8"))
    assert document["command"] == "risk"
    assert document["attacker"] == "journalist"
    assert document["threshold"] == 2
    assert document["rule"] == "class_size <= 2"
    assert document["flagged_rows"] == [1, 2, 3]
    assert [record["row_number"] for record in document["records"]] == [1, 2, 3]
    assert document["verdict"] == "violation"
    assert document["exit_code"] == VIOLATION


# ── 输入校验：坏表 / 坏声明 → 2 ───────────────────────────────────────────

def test_missing_table_file_is_undecidable(capsys, decl, tmp_path):
    code = main([
        "schema", "--table", str(tmp_path / "nope.csv"), "--decl", str(decl),
        "--out-dir", str(tmp_path / "out"),
    ])
    assert code == UNDECIDABLE
    assert "表文件不存在" in capsys.readouterr().err


def test_ragged_row_is_undecidable(capsys, decl, tmp_path):
    path = tmp_path / "ragged.csv"
    path.write_bytes("age,zip,disease\n30,100\n".encode("utf-8"))
    code = main(["schema", "--table", str(path), "--decl", str(decl), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "宽度" in capsys.readouterr().err


def test_declaration_unknown_column_is_undecidable(capsys, table, tmp_path):
    bad = write_decl(tmp_path, {"age": {"role": "qi"}, "salary": {"role": "qi"}})
    code = main(["schema", "--table", str(table), "--decl", str(bad), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "表中不存在的列" in capsys.readouterr().err


def test_declaration_unknown_role_is_undecidable(capsys, table, tmp_path):
    bad = write_decl(tmp_path, {"age": {"role": "quasi"}})
    code = main(["schema", "--table", str(table), "--decl", str(bad), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "角色不在枚举内" in capsys.readouterr().err


def test_declaration_date_precision_requires_precision(capsys, table, tmp_path):
    bad = write_decl(tmp_path, {"age": {"role": "date-precision"}})
    code = main(["schema", "--table", str(table), "--decl", str(bad), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "precision" in capsys.readouterr().err


def test_scan_requires_qi_columns(capsys, table, tmp_path):
    only_sensitive = write_decl(tmp_path, {"disease": {"role": "sensitive"}})
    code = main([
        "scan", "--table", str(table), "--decl", str(only_sensitive),
        "--missing-policy", "drop", "--k", "2", "--out-dir", str(tmp_path / "out"),
    ])
    assert code == UNDECIDABLE
    assert "未声明任何 qi 列" in capsys.readouterr().err


def test_scan_with_valid_arguments_computes(capsys, table, decl, tmp_path):
    """M2 落地后：有效参数必须真的算出结果（不再 MODULE_NOT_READY），且产物按契约落盘。"""
    code = main([
        "scan", "--table", str(table), "--decl", str(decl),
        "--missing-policy", "drop", "--k", "2", "--out-dir", str(tmp_path / "out"),
    ])
    captured = capsys.readouterr()
    assert "MODULE_NOT_READY" not in captured.err
    assert code == VIOLATION, "三行两列 QI 全是单例类 → k=1 < 2，退出码必须是有违例（1）"
    document = json.loads((tmp_path / "out" / "scan.json").read_text(encoding="utf-8"))
    assert document["k_l_t"]["k"] == 1
    assert document["k_l_t"]["class_count"] == 3
    assert document["verdict"] == "violation"
    assert document["exit_code"] == VIOLATION


# ── gate 判据文件 ─────────────────────────────────────────────────────────

def _criteria(tmp_path, table, decl, **overrides):
    document = {
        "table": str(table),
        "declaration": str(decl),
        "missing_policy": "drop",
        "thresholds": {"k": 2, "l": None, "t": None},
    }
    document.update(overrides)
    path = tmp_path / "criteria.json"
    path.write_bytes(json.dumps(document, ensure_ascii=False).encode("utf-8"))
    return path


def test_gate_missing_criteria_file(capsys, tmp_path):
    code = main(["gate", "--criteria", str(tmp_path / "nope.json"), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "判据文件不存在" in capsys.readouterr().err


def test_gate_missing_missing_policy(capsys, tmp_path, table, decl):
    document = {
        "table": str(table),
        "declaration": str(decl),
        "thresholds": {"k": 2},
    }
    path = tmp_path / "criteria.json"
    path.write_bytes(json.dumps(document).encode("utf-8"))
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "missing_policy" in capsys.readouterr().err


@pytest.mark.parametrize("k", [0, -3, "5", 2.5, True, None])
def test_gate_rejects_invalid_k_threshold(capsys, tmp_path, table, decl, k):
    path = _criteria(tmp_path, table, decl, thresholds={"k": k})
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "thresholds.k" in capsys.readouterr().err


def test_gate_with_valid_criteria_computes(capsys, tmp_path, table, decl):
    """M5 落地后：有效判据必须真的算出结果（不再 MODULE_NOT_READY），两份产物按契约落盘。"""
    path = _criteria(tmp_path, table, decl)
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    captured = capsys.readouterr()
    assert "MODULE_NOT_READY" not in captured.err
    assert code == VIOLATION, "三行两列 QI 全是单例类 → k=1 < 2，退出码必须是有违例（1）"
    document = json.loads((tmp_path / "out" / "gate.json").read_text(encoding="utf-8"))
    assert document["command"] == "gate"
    assert document["scan"]["k_l_t"]["k"] == 1
    assert len(document["violations"]) == 3
    assert document["outcome"] == "violation"
    assert document["exit_code"] == VIOLATION
    markdown = (tmp_path / "out" / "gate.md").read_text(encoding="utf-8")
    assert markdown.startswith("# anonymity-scanner gate")
    assert "缺失策略" in markdown and "阈值" in markdown and "预算" in markdown


# ── 判据文件闭合：未知键 / 非法 l·t / 坏 search 块 → 2 ────────────────────

def test_gate_rejects_unknown_top_level_key(capsys, tmp_path, table, decl):
    path = _criteria(tmp_path, table, decl, attacker="journalist")
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    captured = capsys.readouterr()
    assert "未知顶层键" in captured.err and "attacker" in captured.err
    assert not (tmp_path / "out").exists(), "判据无效时不得写出任何产物"


def test_gate_rejects_unknown_threshold_key(capsys, tmp_path, table, decl):
    path = _criteria(tmp_path, table, decl, thresholds={"k": 2, "delta": 0.1})
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "thresholds 有未知键" in capsys.readouterr().err


@pytest.mark.parametrize("l_value", [0, -1, "2", 2.5, True])
def test_gate_rejects_invalid_l_threshold(capsys, tmp_path, table, decl, l_value):
    path = _criteria(tmp_path, table, decl, thresholds={"k": 2, "l": l_value, "t": None})
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "thresholds.l" in capsys.readouterr().err


@pytest.mark.parametrize("t_value", [-0.1, 1.5, "0.5", True, [0.5]])
def test_gate_rejects_invalid_t_threshold(capsys, tmp_path, table, decl, t_value):
    path = _criteria(tmp_path, table, decl, thresholds={"k": 2, "l": None, "t": t_value})
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "thresholds.t" in capsys.readouterr().err


def test_gate_rejects_unknown_search_key(capsys, tmp_path, table, decl):
    path = _criteria(tmp_path, table, decl, search={"enabled": False, "budget": 10, "depth": 3})
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "search 有未知键" in capsys.readouterr().err


def test_gate_requires_budget_when_search_enabled(capsys, tmp_path, table, decl):
    path = _criteria(tmp_path, table, decl, search={"enabled": True})
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "search.budget" in capsys.readouterr().err


@pytest.mark.parametrize("budget", [0, -5, "10", True])
def test_gate_rejects_invalid_search_budget(capsys, tmp_path, table, decl, budget):
    path = _criteria(tmp_path, table, decl, search={"enabled": True, "budget": budget})
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "search.budget" in capsys.readouterr().err


def test_gate_rejects_non_bool_search_flags(capsys, tmp_path, table, decl):
    path = _criteria(
        tmp_path, table, decl,
        search={"enabled": "yes", "budget": 10, "require_exhaustive": False},
    )
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "search.enabled" in capsys.readouterr().err


def test_gate_rejects_require_exhaustive_without_search(capsys, tmp_path, table, decl):
    path = _criteria(
        tmp_path, table, decl,
        search={"enabled": False, "require_exhaustive": True},
    )
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "require_exhaustive" in capsys.readouterr().err


def test_gate_l_threshold_requires_sensitive_column(capsys, tmp_path, table):
    only_qi = write_decl(tmp_path, {"age": {"role": "qi"}, "zip": {"role": "qi"}})
    path = _criteria(tmp_path, table, only_qi, thresholds={"k": 2, "l": 2, "t": None})
    code = main(["gate", "--criteria", str(path), "--out-dir", str(tmp_path / "out")])
    assert code == UNDECIDABLE
    assert "sensitive" in capsys.readouterr().err


# ── 安装形态：入口函数在**未安装**的树里也要能跑 ──────────────────────────

def test_entry_point_runs_without_installation():
    """不依赖 `pip install`：显式把 src/ 放进 PYTHONPATH 跑入口。

    这是发布包（tarball 解包树）的真实通路——干净环境验证要求"不装也能跑测试"，
    所以这里不能依赖当前解释器恰好装过本包。
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", "from anonymity_scanner.cli import main; raise SystemExit(main(['--version']))"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(ROOT),
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert __version__ in result.stdout.decode("utf-8", "replace")


def test_console_script_is_installed():
    """若本解释器已 `pip install -e .`，控制台脚本必须可用（否则 skip，不伪造结论）。"""
    script = shutil.which("anonymity-scanner")
    if script is None:
        pytest.skip("当前解释器未安装控制台脚本（未执行 pip install -e .）")
    result = subprocess.run([script, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    assert result.returncode == 0
    assert __version__ in result.stdout.decode("utf-8", "replace")
