"""M1 夹具的验收测试：独立 oracle、真值纪律、逐字节可复算、局部生成不改清单。

这些断言保护的是 `plan/05` M1 的 DoD 与 `plan/03` K10（真值不得自证）：
  * 生成器与 oracle **互不 import**，且都不 import 生产包（AST 守门，不是靠自觉）；
  * `truth.json` 只存输入与期望，**不含** `observed_*`；
  * `--check` 重生成逐字节一致，且在**没有表格**的干净树里也成立；
  * `--only` **不写** `manifest.json`（全集清单只能由全集运行改写）；
  * `manifest.json` 的 sha256 与盘上文件真正对得上（不是"写了个字段"）；
  * 真值与**朴素手算**对得上（tiny 组逐条手推）。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "data" / "fixtures"
TOOLS = ROOT / "tools"
SUITES = ("tiny", "small", "prune", "budget")

sys.path.insert(0, str(TOOLS))

import fixture_oracle as oracle  # noqa: E402


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_env(pythonpath=None):
    """子进程环境：保留系统必需变量（Windows 启动需要 SYSTEMROOT），只钉住编码与路径。

    不整份替换 `env`：那会让 Windows 上的解释器在 preinit 阶段就崩，
    测出来的是"子进程起不来"，而不是夹具行为。
    """
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env.pop("PYTHONPATH", None)
    if pythonpath is not None:
        env["PYTHONPATH"] = str(pythonpath)
    return env


def _run_generator(*extra, cwd=None):
    return subprocess.run(
        [sys.executable, str(TOOLS / "gen_fixtures.py"), *extra],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(cwd or ROOT),
        env=_clean_env(),
        timeout=600,
    )


# ── AST 守门：独立实现（K10） ─────────────────────────────────────────────

def _imported_modules(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


@pytest.mark.parametrize("name", ["fixture_oracle.py", "gen_fixtures.py"])
def test_tools_do_not_import_production_package(name):
    """真值工具**不 import 生产模块**：否则真值变成"被测实现自证"，基准永久全绿。"""
    modules = _imported_modules(TOOLS / name)
    offenders = sorted(m for m in modules if m == "anonymity_scanner" or m.startswith("anonymity_scanner."))
    assert not offenders, "%s 不得 import 生产模块（K10）：%s" % (name, offenders)


def test_oracle_and_generator_do_not_import_each_other():
    """方向单向：生成器 import oracle；oracle **不得** import 生成器。"""
    assert "fixture_oracle" in _imported_modules(TOOLS / "gen_fixtures.py")
    generator_imports = _imported_modules(TOOLS / "fixture_oracle.py")
    assert "gen_fixtures" not in generator_imports


def test_generator_does_not_use_random_module():
    """固定种子的"确定性"不能建立在 `random` 的实现细节上（`plan/04 §三`）。"""
    modules = _imported_modules(TOOLS / "gen_fixtures.py")
    assert "random" not in modules, "生成器自带 splitmix64，不得 import random"


def test_tool_round6_matches_canonical():
    """oracle 复写的 round6 必须与生产 `canonical.round6` 逐值一致（复写不等于可以漂移）。"""
    from anonymity_scanner.canonical import round6 as production_round6

    for value in (0.0, -0.0, 1 / 3, 2 / 7, 0.1234565, 0.1234575, 2.675, 1e-7, -1e-7, 123456.7890125):
        assert oracle.round6(value) == production_round6(value), "round6 在 %r 上不一致" % (value,)


# ── 真值纪律 ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("suite", SUITES)
def test_truth_exists_and_has_required_keys(suite):
    truth = _load(FIXTURES / suite / "truth.json")
    required = [
        "fixture", "seed", "rows", "columns", "planted", "minimal_collapse_sets",
        "empty_set_witness", "k_by_columns", "violations", "missing_rows", "unique_records",
    ]
    missing = [key for key in required if key not in truth]
    assert not missing, "%s/truth.json 缺键: %s" % (suite, missing)
    assert truth["fixture"] == suite
    assert truth["seed"] == 20261020, "种子必须是固定值（同种子同参数 → 逐字节相同）"


@pytest.mark.parametrize("suite", SUITES)
def test_truth_has_no_observed_fields(suite):
    """真值只存**输入与期望**。出现 `observed_*` 说明它把被测实现的输出抄进来了。"""
    raw = (FIXTURES / suite / "truth.json").read_text(encoding="utf-8")
    assert "observed" not in raw, "%s/truth.json 出现 observed* 字段（真值不得由被测实现填写）" % suite


@pytest.mark.parametrize("suite", SUITES)
def test_truth_is_canonically_serialized(suite):
    """真值必须走确定性序列化（sorted keys / 2 空格 / LF 结尾 / 无 BOM）。"""
    from anonymity_scanner.canonical import dumps as production_dumps

    raw = (FIXTURES / suite / "truth.json").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "不得带 BOM"
    assert b"\r\n" not in raw, "必须是 LF"
    text = raw.decode("utf-8")
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert text == production_dumps(json.loads(text)), "与 canonical.dumps 的冻结参数不一致"


@pytest.mark.parametrize("suite", SUITES)
def test_truth_generator_dumps_matches_canonical(suite):
    """生成器自带的 dumps 必须与生产 `canonical.dumps` 同字节（两份实现，一个口径）。"""
    import gen_fixtures

    truth = _load(FIXTURES / suite / "truth.json")
    from anonymity_scanner.canonical import dumps as production_dumps

    assert gen_fixtures.dumps(truth) == production_dumps(truth)


# ── 独立 oracle 复算 == 生成器写入 ────────────────────────────────────────

@pytest.mark.parametrize("suite", SUITES)
def test_oracle_recomputes_recorded_truth(suite):
    """从**已生成的行**复算一遍，与 truth.json 里写的期望值逐项比对。

    注意这里读的是 `table.csv`（生成物的输入侧），不是重新跑 builder：
    这样测的是"真值与表一致"，而不是"builder 与自己一致"。
    """
    import csv
    import io

    table_path = FIXTURES / suite / "table.csv"
    if not table_path.is_file():
        pytest.skip("表格不在（.gitignore 排除 *.csv）；用 --check 通路覆盖")
    text = table_path.read_text(encoding="utf-8")
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader)
    rows = [{name: value for name, value in zip(header, record)} for record in reader if record]

    truth = _load(FIXTURES / suite / "truth.json")
    qi = truth["qi_columns"]
    sensitive = truth["sensitive_columns"]
    policy = truth["meta"]["policy"]
    threshold = truth["meta"]["threshold"]

    summary = oracle.summarize(rows, qi, policy, threshold, sensitive)
    assert summary["k"] == truth["k_l_t"]["k"], "%s: k 不一致" % suite
    assert summary["l"] == truth["k_l_t"]["l"], "%s: l 不一致" % suite
    assert summary["t"] == truth["k_l_t"]["t"], "%s: t 不一致" % suite
    assert summary["violations"] == truth["violations"], "%s: 违例三件套不一致" % suite
    assert summary["unique_records"] == truth["unique_records"], "%s: 唯一记录不一致" % suite

    for subset, expected in truth["k_by_columns"].items():
        columns = json.loads(subset)
        classes, _ = oracle.group(rows, columns, policy)
        assert oracle.k_of(classes) == expected, "%s: k(%s) 不一致" % (suite, subset)

    search = oracle.search_collapse_sets(
        rows, truth["meta"]["pool"], threshold, policy,
        truth["meta"]["budget"], monotone=truth["search"]["monotonicity_applicable"],
    )
    assert search["minimal_collapse_sets"] == truth["minimal_collapse_sets"], "%s: 崩塌集不一致" % suite
    assert search["evaluated_subsets"] == truth["search"]["evaluated_subsets"]


@pytest.mark.parametrize("suite", SUITES)
def test_declaration_order_is_explicit_and_matches_key_order(suite):
    """§4.3：等价类键按**声明书写顺序**拼接——顺序是语义，不能被 JSON 排序抹掉。

    `canonical.dumps(sort_keys=True)` 会把 `declaration.columns` 的**对象键序**变成字典序；
    真值因此另存 `declaration_order`（有序数组）。这条测试钉住两件事：
      ① `declaration_order` 里的 qi 列顺序 == `qi_columns`；
      ② 真值里的违例键前缀顺序 == `qi_columns`（键确实按声明顺序拼的）。
    """
    truth = _load(FIXTURES / suite / "truth.json")
    ordered = [item["name"] for item in truth["declaration_order"] if item["role"] == "qi"]
    assert ordered == truth["qi_columns"], "%s: declaration_order 的 qi 顺序与 qi_columns 不一致" % suite

    if truth["violations"]:
        first_key = truth["violations"][0]["key"]
        # 从键里**按出现顺序**抽出列名（值是任意内容，不能按 "col=" 直接前缀匹配）
        found = [part.split("=", 1)[0] for part in first_key.split("|")]
        assert found == truth["qi_columns"],             "%s: 违例键的列顺序 %r 与声明顺序 %r 不一致（键 = %r）" % (
                suite, found, truth["qi_columns"], first_key)


def test_tiny_truth_is_hand_checkable():
    """tiny 的全部期望值按 `plan/04 §三` 的植入说明**手工推导**，逐条钉死。

    这是"可手算复核"这条产品承诺的测试形态：不是断言"和生成器一样"，
    而是断言"和一个人按文档算出来的一样"。
    """
    truth = _load(FIXTURES / "tiny" / "truth.json")
    # 12 行；age 四值各 3 行 → k({age}) = 3（阈值 3，恰好达标）
    assert truth["rows"] == 12
    assert truth["k_by_columns"]["[\"age\"]"] == 3
    # 年龄组内 zip 三值各一次 → age+zip 共 12 个单例 → k = 1
    assert truth["k_by_columns"]["[\"age\",\"zip\"]"] == 1
    # dob 12 个不同值 → k = 1
    assert truth["k_by_columns"]["[\"dob\"]"] == 1
    # 空集 = 一张表一个类 → k = 行数
    assert truth["k_by_columns"]["[]"] == 12
    # age 安全、sex 一半一半安全；zip/dob 不安全 → age+zip、age+dob 都不安全
    assert truth["minimal_collapse_sets"] == [["age"], ["sex"], ["zip"]]
    assert truth["empty_set_witness"] is False


def test_small_missing_rows_and_policies():
    """small：4 行缺失；三策略结果必须**不同**（这是 D4 / sdcMicro #363 型坑的用例）。"""
    truth = _load(FIXTURES / "small" / "truth.json")
    assert truth["missing_rows"] == [5, 12, 31, 44]
    drop = truth["by_policy"]["drop"]
    single = truth["by_policy"]["single-column"]
    separate = truth["by_policy"]["separate-class"]
    assert drop["undecided_rows"] == [5, 12, 31, 44], "drop 必须把这 4 行登记为未裁决"
    assert single["undecided_rows"] == []
    assert separate["missing_class"]["row_numbers"] == [5, 12, 31, 44]
    assert separate["missing_class"]["k"] == 4
    # 三种策略的类数各不相同 → 它们确实算了三遍，不是同一份结果换个名字
    assert len({drop["class_count"], single["class_count"], separate["class_count"]}) == 3


def test_small_planted_singletons_match_expected_count():
    truth = _load(FIXTURES / "small" / "truth.json")
    planted = {item["kind"]: item for item in truth["planted"]}
    assert len(planted["singleton_classes"]["class_keys"]) == 3
    assert planted["singleton_classes"]["row_numbers"] == [58, 59, 60]
    assert planted["l_equals_one"]["expected_l"] == 1
    assert planted["l_equals_one"]["row_numbers"] == list(range(1, 13))


def test_prune_fixture_prunes_and_is_exhaustive():
    truth = _load(FIXTURES / "prune" / "truth.json")
    search = truth["search"]
    assert search["completeness"] == "exhausted"
    assert search["monotonicity_applicable"] is True
    # 三个"单列即崩塌"的列（zip / dob / sex）全部被剪 → 剪掉的子集数 > 0
    assert search["pruned_subsets"] > 0
    # 安全列只有 age 与 region，且两者组合仍安全 → 边界集 = {age, region}
    assert truth["minimal_collapse_sets"] == [["age", "region"]]
    # 单列 k 的期望值按 `plan/04 §三` 的植入说明手推。念 `k_by_columns` 而不是重算表：
    # 干净 clone 里没有 table.csv（.gitignore），这条断言必须在那种树上也成立。
    single = {name: truth["k_by_columns"][json.dumps([name])] for name in ("zip", "dob", "sex", "age", "region")}
    assert single == {"zip": 1, "dob": 2, "sex": 2, "age": 30, "region": 100}


def test_budget_fixture_is_truncated_not_exhausted():
    truth = _load(FIXTURES / "budget" / "truth.json")
    search = truth["search"]
    assert search["subset_space"] == 2 ** 10 - 1
    assert search["budget"] < search["subset_space"]
    assert search["completeness"] == "budget-truncated"
    assert search["non_exhaustive"] is True
    assert truth["collapse_sets_status"] == "non-exhaustive", \
        "预算截断下的结论不得被渲染成'最小崩塌集'（plan/06 A2）"


@pytest.mark.parametrize("suite", SUITES)
def test_search_scenarios_cover_boundaries(suite):
    """`plan/01` §M3 验收 ④：空集边界与无解边界都必须有显式真值。"""
    truth = _load(FIXTURES / suite / "truth.json")
    scenarios = {item["name"]: item for item in truth["search_scenarios"]}
    assert set(scenarios) == {"default", "empty_set_witness", "no_solution"}
    assert scenarios["empty_set_witness"]["minimal_collapse_sets"] == [[]]
    assert scenarios["empty_set_witness"]["empty_set_witness"] is True
    assert scenarios["no_solution"]["verdict"] == "no_solution"
    assert scenarios["no_solution"]["minimal_collapse_sets"] == []


# ── manifest 与逐字节可复算 ───────────────────────────────────────────────

def test_manifest_registers_real_hashes():
    """manifest 的 sha256 必须与盘上文件真正对得上（不是"写了个字段"）。"""
    manifest = _load(FIXTURES / "manifest.json")
    assert manifest["seed"] == 20261020
    assert set(manifest["suites"]) == set(SUITES)
    for name, entry in manifest["suites"].items():
        truth_path = FIXTURES / name / "truth.json"
        digest = hashlib.sha256(truth_path.read_bytes()).hexdigest()
        assert entry["truth_sha256"] == digest, "%s 的真值 sha256 与 manifest 不符" % name
    generator_digest = hashlib.sha256((TOOLS / "gen_fixtures.py").read_bytes()).hexdigest()
    assert manifest["generator_sha256"] == generator_digest, "生成器改动后必须重生成 manifest"
    oracle_digest = hashlib.sha256((TOOLS / "fixture_oracle.py").read_bytes()).hexdigest()
    assert manifest["oracle_sha256"] == oracle_digest, "oracle 改动后必须重生成 manifest"


def test_generator_check_is_byte_identical():
    """`--check` 重生成后逐字节一致（生成器改动未重生成 → 这条会红）。"""
    result = _run_generator("--check")
    assert result.returncode == 0, result.stdout.decode("utf-8", "replace")
    assert "逐字节一致" in result.stdout.decode("utf-8", "replace")


def test_generator_check_works_without_tables(tmp_path):
    """干净 clone（表格被 `.gitignore` 排除）里也必须能 `--check`。

    这是 `plan/04 §一` 的"表不入库"与"真值可复算"两条承诺的交点：
    只拷真值与 manifest（没有 *.csv）到临时目录，`--check` 仍须绿。
    """
    clean = tmp_path / "clean"
    (clean / "tools").mkdir(parents=True)
    shutil.copy2(str(TOOLS / "gen_fixtures.py"), str(clean / "tools" / "gen_fixtures.py"))
    shutil.copy2(str(TOOLS / "fixture_oracle.py"), str(clean / "tools" / "fixture_oracle.py"))
    for suite in SUITES:
        (clean / "data" / "fixtures" / suite).mkdir(parents=True)
        shutil.copy2(
            str(FIXTURES / suite / "truth.json"),
            str(clean / "data" / "fixtures" / suite / "truth.json"),
        )
    shutil.copy2(str(FIXTURES / "manifest.json"), str(clean / "data" / "fixtures" / "manifest.json"))
    # 断言前置条件：这棵树里真的没有表格
    assert not list(clean.rglob("*.csv")), "测试前提：干净树里不应有表"

    result = subprocess.run(
        [sys.executable, str(clean / "tools" / "gen_fixtures.py"), "--check"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(clean),
        env=_clean_env(),
        timeout=600,
    )
    output = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 0, output
    assert "逐字节一致" in output


def test_only_does_not_rewrite_manifest(tmp_path):
    """局部生成（`--only`）**绝不改写全集清单**（`plan/04 §六`）。

    做法：目标目录里先放一份"哨兵" manifest（内容刻意不该被保留），
    跑 `--only tiny` 后它的字节必须原封不动。
    """
    target = tmp_path / "fixtures"
    target.mkdir()
    sentinel = b'{"sentinel": "must-not-be-touched"}\n'
    (target / "manifest.json").write_bytes(sentinel)

    result = subprocess.run(
        [sys.executable, str(TOOLS / "gen_fixtures.py"), "--only", "tiny", "--out", str(target)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(ROOT),
        env=_clean_env(),
        timeout=300,
    )
    output = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 0, output
    assert "manifest.json 未改写" in output
    assert (target / "manifest.json").read_bytes() == sentinel, "--only 改写了 manifest.json"
    # 该组的表与真值确实产出了（否则"没改写"只是因为它什么也没干）
    assert (target / "tiny" / "table.csv").is_file()
    assert (target / "tiny" / "truth.json").is_file()
    # 其它三组没有被写出来
    for other in ("small", "prune", "budget"):
        assert not (target / other).exists(), "--only 只应生成被点名的那一组"


def test_full_run_writes_manifest(tmp_path):
    """对照组：全集运行**必须**写 manifest（否则上一条测试可能因"从不写"而假绿）。"""
    result = subprocess.run(
        [sys.executable, str(TOOLS / "gen_fixtures.py"), "--out", str(tmp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(ROOT),
        env=_clean_env(),
        timeout=600,
    )
    assert result.returncode == 0, result.stdout.decode("utf-8", "replace")
    assert (tmp_path / "manifest.json").is_file()
    manifest = _load(tmp_path / "manifest.json")
    assert set(manifest["suites"]) == set(SUITES)


def test_generator_is_deterministic_across_runs(tmp_path):
    """同种子同参数 → 两次全集运行的表与真值逐字节相同。"""
    first, second = tmp_path / "a", tmp_path / "b"
    for target in (first, second):
        result = subprocess.run(
            [sys.executable, str(TOOLS / "gen_fixtures.py"), "--out", str(target)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(ROOT),
            env=_clean_env(),
            timeout=600,
        )
        assert result.returncode == 0, result.stdout.decode("utf-8", "replace")
    for suite in SUITES:
        for name in ("table.csv", "truth.json"):
            assert (first / suite / name).read_bytes() == (second / suite / name).read_bytes(), \
                "%s/%s 两次运行不一致" % (suite, name)


# ── Adult 基线（只读本地，不联网） ────────────────────────────────────────


def _run_adult(*extra):
    return subprocess.run(
        [sys.executable, str(TOOLS / "adult_baseline.py"), *extra],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(ROOT),
        env=_clean_env(),
        timeout=300,
    )


def test_adult_reports_not_obtained_without_file():
    """不给文件是**如实标注**（退出码 3），不是失败也不是编造行数。"""
    result = _run_adult()
    output = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 3
    assert "未取得" in output
    assert "不代下载" in output


def test_adult_reads_local_file_and_reports_shape(tmp_path):
    """造一份 3 行的 Adult 形态文件：必须报出行数与列数，且指出 `?` 缺失列。"""
    path = tmp_path / "adult.data"
    path.write_bytes(
        (
            "39, State-gov, 77516, Bachelors, 13, Never-married, Adm-clerical, Not-in-family, "
            "White, Male, 2174, 0, 40, United-States, <=50K, \n"
            "50, Private, 83311, Bachelors, 13, Married-civ-spouse, Exec-managerial, Husband, "
            "White, Male, 0, 0, 13, ?, <=50K, \n"
            "38, Private, 215646, HS-grad, 9, Divorced, Handlers-cleaners, Not-in-family, "
            "White, Male, 0, 0, 40, United-States, <=50K, \n"
        ).encode("utf-8")
    )
    result = _run_adult("--table", str(path), "--json")
    assert result.returncode == 0, result.stdout.decode("utf-8", "replace")
    report = json.loads(result.stdout.decode("utf-8"))
    assert report["rows"] == 3
    assert report["columns"] == 15
    assert report["missing_like_cells_by_column"] == {"native-country": 1}
    assert report["matches_expected_train_rows"] is False


def test_adult_missing_file_is_undecidable(tmp_path):
    """给了路径但文件不存在 → 退出码 2（"无法裁决"，与本项目退出码口径一致）。"""
    result = _run_adult("--table", str(tmp_path / "nope.data"))
    assert result.returncode == 2
    assert "文件不存在" in result.stdout.decode("utf-8", "replace")


def test_adult_baseline_matches_recorded_real_file_facts():
    """`data/README.md` §二 回填的 Adult 实测事实必须与脚本的假设一致。

    这些是**实测数字**（2026-10-20 下载 adult.data 后跑出来的），写进测试是为了防止
    "文档写 32561、脚本按别的数判"这种静默漂移。没有本地文件时本测试不读数据，
    只验常量与格式假设。
    """
    import adult_baseline

    assert adult_baseline.ADULT_TRAIN_ROWS == 32561
    assert len(adult_baseline.ADULT_COLUMNS) == 15
    assert adult_baseline.ADULT_COLUMNS[0] == "age"
    assert adult_baseline.ADULT_COLUMNS[-1] == "income"
    # 归一化口径：`?` 与空串都算"缺失样"单元格（Adult 原文写 " ?"）
    blank = {"workclass": 1836, "occupation": 1843, "native-country": 583}
    assert set(blank) <= set(adult_baseline.ADULT_COLUMNS)


def test_adult_script_has_no_network_calls():
    """`data/README.md` §二：安装后零网络、脚本只读本地文件。

    这条判据落在源码上：一旦有人往脚本里塞 `urllib` / `requests` / `socket`，这里变红。
    """
    modules = _imported_modules(TOOLS / "adult_baseline.py")
    forbidden = {"socket", "urllib", "urllib.request", "requests", "http", "httpx"}
    assert not (modules & forbidden), "adult_baseline.py 出现了网络模块：%s" % sorted(modules & forbidden)
