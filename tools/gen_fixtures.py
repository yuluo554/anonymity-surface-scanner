"""合成夹具生成器（M1 交付）：固定种子 + 自研确定性随机 + 独立 oracle 复算真值。

用法：
    py -3.12 tools/gen_fixtures.py                 # 全集生成：表 + 真值 + manifest
    py -3.12 tools/gen_fixtures.py --only tiny     # 局部生成：只写该组表与真值，**不动 manifest**
    py -3.12 tools/gen_fixtures.py --check         # 重生成到临时目录，与入仓真值/manifest 逐字节比对

纪律（`plan/04 §二`、`data/README.md` §三）：
  * **禁 `random` 模块**：跨版本序列不保证一致。本文件自带 splitmix64。
  * **不 import 生产模块**（`anonymity_scanner`）：真值必须由独立判定式写出（K10）。
    表写盘与 JSON 序列化因此在本文件里各有一份最小实现；与 `canonical.dumps` 的等价性
    由 `tests/test_fixtures.py` 钉住（不是靠"看起来一样"）。
  * 表落 `data/fixtures/<suite>/table.csv`（`.gitignore` 已排除 `*.csv`，不入库）；
    真值落 `data/fixtures/<suite>/truth.json`；清单落 `data/fixtures/manifest.json`（只有全集运行才写）。
  * 生成期断言"植入项可检出"：植入的类大小必须等于期望值，不是"我以为是单例"。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fixture_oracle as oracle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = Path(__file__).resolve()
ORACLE = Path(__file__).resolve().parent / "fixture_oracle.py"
SUITES = ("tiny", "small", "prune", "budget")
SEED = 20261020
MANIFEST_FORMAT = 1
MASK64 = (1 << 64) - 1


# ── 自研确定性随机（splitmix64） ─────────────────────────────────────────

class DeterministicRandom(object):
    """splitmix64：纯整数运算，任何 Python 3.8+ 上序列完全相同。

    为什么不用 `random`：`random.Random` 的算法在 CPython 里虽稳定，但"稳定"是实现细节
    而非语言承诺；本项目的真值要能被三年后的解释器逐字节复现。
    """

    def __init__(self, seed: int) -> None:
        self.state = seed & MASK64

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return z ^ (z >> 31)

    def below(self, bound: int) -> int:
        """无偏拒绝采样：`bound <= 0` 视为用法错误。"""
        if bound <= 0:
            raise ValueError("bound 必须为正整数")
        limit = (1 << 64) - ((1 << 64) % bound)
        while True:
            value = self.next_u64()
            if value < limit:
                return value % bound

    def pick(self, items):
        return items[self.below(len(items))]


# ── 最小写盘实现（不 import 生产模块；等价性有测试） ────────────────────

def dumps(obj) -> str:
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2, separators=(",", ": "), allow_nan=False)
    return text + "\n"


def write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def write_table(path: Path, columns, rows) -> None:
    """CSV：UTF-8 无 BOM、LF 结尾、不做任何转义之外的加工。"""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row[name] for name in columns])
    write_bytes_atomic(path, buffer.getvalue().encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


# ── 夹具设计 ─────────────────────────────────────────────────────────────
#
# 每个 builder 返回 dict：
#   columns / decl / rows / threshold / budget / pool / planted / notes
# rows 为 [{列名: 值}]，顺序即数据行号（1 起，不含表头）。

def _row(columns, values):
    return {name: value for name, value in zip(columns, values)}


def build_tiny():
    """12 行 × 7 列。手算可核：`age` 单列每个取值 3 次（k=3 恰好达标）；
    `age`+`zip` 交叉后全为单例（k=1）——最小崩塌集必须把这对关系说出来。
    """
    columns = ["age", "zip", "dob", "sex", "disease", "name", "phone"]
    ages = ["20", "30", "40", "50"]
    zips = ["zip-00001", "zip-00002", "zip-00003"]
    diseases = ["flu", "cold", "covid"]
    rows = []
    for index in range(12):
        rows.append(_row(columns, [
            ages[index // 3],                     # 每个年龄恰好 3 行
            zips[index % 3],                      # 年龄组内 zip 三值各一次 → 交叉全是单例
            "1960-%02d" % (index + 1),            # 12 个不同值 → k({dob}) = 1
            "F" if index % 2 == 0 else "M",
            diseases[index % 3],
            "alice-%03d" % (index + 1),           # 明显虚构
            "000-0000-%04d" % (index + 1),
        ]))
    decl = {
        "columns": {
            "age": {"role": "qi"},
            "zip": {"role": "qi"},
            "dob": {"role": "qi"},
            "sex": {"role": "qi"},
            "disease": {"role": "sensitive"},
            "name": {"role": "direct-identifier"},
            "phone": {"role": "direct-identifier"},
        }
    }
    return {
        "columns": columns,
        "decl": decl,
        "rows": rows,
        "threshold": 3,
        "budget": 64,
        "pool": ["age", "sex", "zip", "dob"],
        "policy": "drop",
        "planted": [
            {"kind": "single_column_min_class", "columns": ["age"], "expected_k": 3},
            {"kind": "pair_collapses_to_singletons", "columns": ["age", "zip"], "expected_k": 1},
        ],
    }


def build_small():
    """60 行 × 8 列。植入：`zip+dob` 恰好 3 个单例类；最大类内 `sex` 全同（l=1 用例）；
    4 行缺失（覆盖三种 token 形态）；`note` 未声明（进 `unparticipating`）。
    """
    columns = ["age", "zip", "dob", "sex", "disease", "name", "phone", "note"]
    ages = ["20", "30", "40", "50", "60"]
    diseases = ["flu", "cold", "covid"]

    # (zip, dob) → 行数。前 8 组共 57 行，后 3 组各 1 行（植入的单例类）。
    groups = [
        ("zip-00001", "1990-01", 12),
        ("zip-00001", "1990-02", 10),
        ("zip-00002", "1990-01", 9),
        ("zip-00002", "1990-02", 8),
        ("zip-00003", "1990-03", 7),
        ("zip-00003", "1990-04", 5),
        ("zip-00004", "1990-05", 3),
        ("zip-00004", "1990-06", 3),
    ]
    planted_groups = [
        ("zip-00009", "1999-09", 1),
        ("zip-00009", "1999-08", 1),
        ("zip-00010", "1999-07", 1),
    ]

    rows = []
    # 最大的类（zip-00001 / 1990-01，12 行）里 sex 全为 F → 该类 l = 1。
    for zip_code, dob, count in groups + planted_groups:
        for offset in range(count):
            index = len(rows)
            sex = "F" if (zip_code, dob) == ("zip-00001", "1990-01") else ("F" if index % 2 == 0 else "M")
            rows.append(_row(columns, [
                ages[index % len(ages)],
                zip_code,
                dob,
                sex,
                diseases[index % 3],
                "bob-%03d" % (index + 1),
                "000-0000-%04d" % (index + 1),
                "note-%02d" % (index % 4),
            ]))

    # 缺失植入：4 行，token 覆盖 ""、"NA"、"-"、"null"。
    # 刻意只落在 `age` / `sex` 上：`zip+dob` 的 3 个单例类是**植入项**，不能被缺失值污染成 5 个
    # （生成期断言要求单例数恰好 3 —— 这条纪律把"我以为"换成"我断言过"）。
    missing_plan = [(5, "age", ""), (12, "age", "NA"), (31, "sex", "-"), (44, "sex", "null")]
    for row_number, column, token in missing_plan:
        rows[row_number - 1][column] = token

    decl = {
        "columns": {
            "age": {"role": "qi"},
            "zip": {"role": "qi"},
            "dob": {"role": "qi"},
            "sex": {"role": "qi"},
            "disease": {"role": "sensitive"},
            "name": {"role": "direct-identifier"},
            "phone": {"role": "direct-identifier"},
            # note 故意不声明 → 必须出现在 unparticipating 里（不静默丢弃）
        }
    }
    return {
        "columns": columns,
        "decl": decl,
        "rows": rows,
        "threshold": 5,
        "budget": 256,
        "pool": ["age", "sex", "zip", "dob"],
        "policy": "drop",
        "planted": [
            {"kind": "singleton_classes", "columns": ["zip", "dob"], "expected_count": 3},
            {"kind": "l_equals_one", "columns": ["zip", "dob"], "class_key": "zip=zip-00001|dob=1990-01"},
            {"kind": "missing_tokens", "columns": ["age", "sex"],
             "row_numbers": [row_number for row_number, _, _ in missing_plan],
             "tokens": [token for _, _, token in missing_plan]},
        ],
    }


def build_prune():
    """300 行 × 9 列。植入三个"单列即崩塌"的列 → 它们的全部超集必须被反单调剪枝跳过：
      * `zip` 全不重复（k=1）
      * `dob` 每个取值恰 2 行（k=2）
      * `sex` 含 2 行稀有取值 `X`（k=2）—— 低基数 + 长尾 = 低 k，`plan/04 §三` 的 `k({sex}) < 阈值`
    安全对照列：`age`（10 值 × 30 行 → k=30）、`region`（3 值 × 100 行 → k=100）。

    行内取值按行号确定性构造（不用随机）：真值里 `k({sex}) == 2` 这类断言才有意义，
    随机分布只能断言"大约"。`rng` 只用于不该被断言的 `disease` / `note`。
    **无缺失**：保证 `drop` 下加列不改变行集（单调性前提成立，`exhausted` 才是真话）。
    """
    columns = ["age", "zip", "dob", "sex", "region", "disease", "name", "phone", "note"]
    rng = DeterministicRandom(SEED + 3)
    regions = ["region-north", "region-south", "region-east"]
    rows = []
    for index in range(300):
        # 末两行把 sex 换成稀有值 X：`sex` 的类大小分布 = {F:149, M:149, X:2} → k=2
        sex = "X" if index >= 298 else ("F" if index % 2 == 0 else "M")
        rows.append(_row(columns, [
            "age-%02d" % (index % 10),                  # 10 值 × 30 行 → k=30
            "zip-%05d" % index,                         # 300 个不同值 → k=1
            "dob-%03d" % (index % 150),                 # 150 值 × 2 行 → k=2
            sex,                                        # {F:149, M:149, X:2} → k=2
            regions[index % 3],                         # 100 / 100 / 100 → k=100
            ["flu", "cold", "covid"][rng.below(3)],
            "carol-%03d" % (index + 1),
            "000-0000-%04d" % (index + 1),
            "note-%02d" % rng.below(5),
        ]))
    decl = {
        "columns": {
            "age": {"role": "qi"},
            "zip": {"role": "qi"},
            "dob": {"role": "qi"},
            "sex": {"role": "qi"},
            "region": {"role": "qi"},
            "disease": {"role": "sensitive"},
            "name": {"role": "direct-identifier"},
            "phone": {"role": "direct-identifier"},
        }
    }
    return {
        "columns": columns,
        "decl": decl,
        "rows": rows,
        "threshold": 5,
        "budget": 4096,
        "pool": ["age", "dob", "region", "sex", "zip"],
        "policy": "drop",
        "planted": [
            {"kind": "high_cardinality_prune_trigger", "columns": ["zip"], "expected_k": 1},
            {"kind": "high_cardinality_prune_trigger", "columns": ["dob"], "expected_k": 2},
            {"kind": "low_k_trigger", "columns": ["sex"], "expected_k": 2},
            {"kind": "safe_control", "columns": ["age"], "expected_k": 30},
            {"kind": "safe_control", "columns": ["region"], "expected_k": 100},
        ],
    }


def build_budget():
    """1200 行 × 10 列，10 个候选列 → 子集空间 1023 ≫ 预算 40。
    每个单列 k ≥ 5（单列阶段不会触发剪枝）→ 预算一定在广度上被耗尽，
    `completeness` 必须是 `budget-truncated`（不得声称穷尽）。
    """
    columns = ["c01_age", "c02_zip", "c03_dob", "c04_sex", "c05_region",
               "c06_income", "c07_edu", "c08_job", "c09_house", "c10_car"]
    cardinalities = [20, 40, 60, 2, 5, 80, 12, 30, 24, 8]
    rng = DeterministicRandom(SEED + 4)
    rows = []
    for _ in range(1200):
        values = []
        for position, cardinality in enumerate(cardinalities):
            values.append("c%02d-%03d" % (position + 1, rng.below(cardinality)))
        rows.append(_row(columns, values))
    decl = {"columns": {name: {"role": "qi"} for name in columns}}
    return {
        "columns": columns,
        "decl": decl,
        "rows": rows,
        "threshold": 5,
        "budget": 40,
        "pool": list(columns),
        "policy": "drop",
        "planted": [
            {"kind": "budget_truncation", "expected_subset_space": 2 ** len(columns) - 1,
             "budget": 40, "expected_completeness": "budget-truncated"},
        ],
    }


BUILDERS = {
    "tiny": build_tiny,
    "small": build_small,
    "prune": build_prune,
    "budget": build_budget,
}


# ── 生成期断言（植入项必须可检出） ──────────────────────────────────────

def run_planted_assertions(suite, spec, rows) -> None:
    """把"我以为是"换成"我断言过"。任一断言失败 = 夹具设计坏了，直接让生成器红。"""
    by_policy = {}
    for policy in oracle.POLICIES:
        classes, undecided = oracle.group(rows, spec["pool"], policy)
        by_policy[policy] = (classes, undecided)

    if suite == "tiny":
        classes, _ = by_policy["drop"]
        assert oracle.k_of(oracle.group(rows, ["age"], "drop")[0]) == 3, "tiny: k({age}) 应为 3"
        assert oracle.k_of(oracle.group(rows, ["age", "zip"], "drop")[0]) == 1, "tiny: k({age,zip}) 应为 1"
        assert len(classes) >= 1
    elif suite == "small":
        classes, _ = oracle.group(rows, ["zip", "dob"], "single-column")
        singles = sorted(key for key, numbers in classes.items() if len(numbers) == 1)
        assert len(singles) == 3, "small: zip+dob 单例类应为 3，实测 %d" % len(singles)
        biggest = "zip=zip-00001|dob=1990-01"
        assert biggest in classes, "small: 最大类的键不在类集合里"
        sexes = {rows[number - 1]["sex"] for number in classes[biggest]}
        assert sexes == {"F"}, "small: 最大类内 sex 应全同（l=1 用例），实测 %r" % (sexes,)
        planted_missing = [5, 12, 31, 44]
        actual = sorted(
            index + 1 for index, row in enumerate(rows)
            if any(oracle.is_missing(row[name]) for name in spec["columns"])
        )
        assert actual == planted_missing, "small: 含缺失的行应为 %r，实测 %r" % (planted_missing, actual)
    elif suite == "prune":
        assert oracle.k_of(oracle.group(rows, ["zip"], "drop")[0]) == 1, "prune: k({zip}) 应为 1"
        assert oracle.k_of(oracle.group(rows, ["dob"], "drop")[0]) < 5, "prune: k({dob}) 应 < 5"
        assert oracle.k_of(oracle.group(rows, ["sex"], "drop")[0]) == 2, "prune: k({sex}) 应为 2"
        assert oracle.k_of(oracle.group(rows, ["region"], "drop")[0]) == 100, "prune: k({region}) 应为 100"
        assert oracle.k_of(oracle.group(rows, ["age"], "drop")[0]) == 30, "prune: k({age}) 应为 30"
        for policy in oracle.POLICIES:
            numbers = sorted(number for numbers in by_policy[policy][0].values() for number in numbers)
            assert numbers == list(range(1, 301)), "prune: 无缺失夹具在 %s 下必须保留全部 300 行" % policy
    elif suite == "budget":
        space = 2 ** len(spec["pool"]) - 1
        assert space > spec["budget"], "budget: 子集空间 %d 必须大于预算 %d" % (space, spec["budget"])
        for column in spec["pool"]:
            value = oracle.k_of(oracle.group(rows, [column], "drop")[0])
            assert value is not None and value >= spec["threshold"], \
                "budget: k({%s}) = %r 应 ≥ 阈值 %d（单列阶段不得剪枝）" % (column, value, spec["threshold"])


# ── 真值组装 ─────────────────────────────────────────────────────────────

def _missing_facts(rows, columns):
    cells = []
    for index, row in enumerate(rows):
        for name in columns:
            if oracle.is_missing(row[name]):
                cells.append({"row": index + 1, "column": name})
    return cells


def _policy_block(rows, spec):
    """三种缺失策略下的摘要（含违例三件套、唯一记录、未裁决行、缺失独立类）。

    去重纪律：无缺失值的夹具在三种策略下结果**必然相同**（没有缺失可处理，策略无从表现）。
    与其把同一份 1200 条违例清单抄三遍（`budget` 真值会因此从 300 KB 涨到 1.4 MB），
    不如把后两种写成 `{"same_as": "drop"}` —— 读者一眼看出"为什么一样"，
    `tests/test_fixtures.py` 也据此解析。有缺失的夹具（`small`）三种结果不同，照常各写一份。
    """
    declared = spec["decl"]["columns"]
    qi = [name for name in spec["columns"] if declared.get(name, {}).get("role") == "qi"]
    sensitive = [name for name in spec["columns"] if declared.get(name, {}).get("role") == "sensitive"]
    out = {}
    baseline = None
    for policy in oracle.POLICIES:
        summary = oracle.summarize(rows, qi, policy, spec["threshold"], sensitive)
        block = {
            "k": summary["k"],
            "l": summary["l"],
            "t": summary["t"],
            "class_count": summary["class_count"],
            "class_size_histogram": summary["class_size_histogram"],
            "violations": summary["violations"],
            "unique_records": summary["unique_records"],
            "undecided_rows": summary["undecided_rows"],
            "missing_class": summary["missing_class"],
        }
        if baseline is None:
            baseline = block
            out[policy] = block
        elif block == baseline:
            out[policy] = {"same_as": oracle.POLICIES[0]}
        else:
            out[policy] = block
    return qi, sensitive, out


def monotonicity_holds(rows, pool, policy) -> bool:
    """单调性前提 = **固定行集**（`data/README.md` §4.5）。

    `drop` 下只要候选池里有任何一列含缺失，加这一列就会多丢行 → 行集变了，
    `k(S ∪ {c}) ≤ k(S)` 不再由定义保证。其余策略不改行集，前提成立。
    """
    if policy != "drop":
        return True
    return not any(oracle.is_missing(row[name]) for row in rows for name in pool)


def _search_block(rows, spec, qi):
    """§4.5 的搜索结论（含完整性三态与单调性前提）。"""
    policy = spec["policy"]
    monotone = monotonicity_holds(rows, spec["pool"], policy)
    result = oracle.search_collapse_sets(
        rows, spec["pool"], spec["threshold"], policy, spec["budget"], monotone=monotone
    )
    result["policy"] = policy
    result["threshold"] = spec["threshold"]
    result["pool"] = sorted(spec["pool"])
    result["qi_columns"] = qi
    return result


def _search_scenarios(rows, spec):
    """同一份夹具在三种阈值下的搜索结论：默认 / 空集边界 / 无解。

    为什么必须显式覆盖：`plan/01` §M3 验收 ④ 要求"单列已达阈值"与"全部列都不达标"
    两个边界都有定义行为。只写默认场景，M3 落地时这两个分支没有真值可对。
    """
    policy = spec["policy"]
    pool = sorted(spec["pool"])
    monotone = monotonicity_holds(rows, pool, policy)
    single = {name: oracle.k_of(oracle.group(rows, [name], policy)[0]) for name in pool}
    biggest_single = max(value for value in single.values() if value is not None)

    scenarios = [("default", spec["threshold"])]
    # 空集边界：阈值高于所有单列 k，但不超过行数（空集本身安全）
    if biggest_single + 1 <= len(rows):
        scenarios.append(("empty_set_witness", biggest_single + 1))
    # 无解：阈值高于行数（连空集都不安全）
    scenarios.append(("no_solution", len(rows) + 1))

    out = []
    for name, threshold in scenarios:
        result = oracle.search_collapse_sets(rows, pool, threshold, policy, None, monotone=monotone)
        result["name"] = name
        result["threshold"] = threshold
        out.append(result)
    return out


def build_truth(name, spec) -> dict:
    rows = spec["rows"]
    columns = spec["columns"]
    run_planted_assertions(name, spec, rows)
    qi, sensitive, by_policy = _policy_block(rows, spec)
    missing_cells = _missing_facts(rows, columns)
    search = _search_block(rows, spec, qi)
    scenarios = _search_scenarios(rows, spec)
    k_by_columns = oracle.k_table(rows, oracle.candidate_subsets(spec["pool"], 2), spec["policy"])

    planted = []
    for item in spec["planted"]:
        record = dict(item)
        if item.get("kind") == "singleton_classes":
            classes, _ = oracle.group(rows, item["columns"], "single-column")
            singles = sorted(key for key, numbers in classes.items() if len(numbers) == 1)
            record["class_keys"] = singles
            record["row_numbers"] = sorted(classes[key][0] for key in singles)
            assert len(singles) == item["expected_count"], \
                "%s: 植入的单例类数应为 %d，实测 %d" % (name, item["expected_count"], len(singles))
        if item.get("kind") == "l_equals_one":
            key = item["class_key"]
            classes, _ = oracle.group(rows, item["columns"], "single-column")
            record["row_numbers"] = sorted(classes[key])
            record["expected_l"] = 1
        if "expected_k" in item:
            value = oracle.k_of(oracle.group(rows, item["columns"], "single-column")[0])
            assert value == item["expected_k"], \
                "%s: 植入列 %r 的单列 k 应为 %r，实测 %r" % (name, item["columns"], item["expected_k"], value)
        planted.append(record)

    # `spec["policy"]` 是默认策略；若它被记成 same_as，解析回基线块。
    default_policy = by_policy[spec["policy"]]
    if "same_as" in default_policy:
        default_policy = by_policy[default_policy["same_as"]]
    return {
        # ── `plan/04 §二` 规定的顶层键（顺序按契约，生成器写、键序固定） ──
        "fixture": name,
        "seed": SEED,
        "rows": len(rows),
        "columns": columns,
        "planted": planted,
        "minimal_collapse_sets": search["minimal_collapse_sets"],
        # 非穷尽时这个字段**不得**被渲染成"最小"（`plan/06` A2 / `data/README` §4.5 歧义纪律）。
        # 真值把它写死，M3/M5 的文案断言才有东西可对。
        "collapse_sets_status": "exhaustive" if search["completeness"] == "exhausted" else "non-exhaustive",
        "empty_set_witness": search["empty_set_witness"],
        "k_by_columns": k_by_columns,
        "violations": default_policy["violations"],
        "missing_rows": sorted(
            index + 1 for index, row in enumerate(rows)
            if any(oracle.is_missing(row[name]) for name in columns)
        ),
        "unique_records": default_policy["unique_records"],
        # `sort_keys=True` 会把 `declaration.columns` 的**对象键序**打乱（JSON 对象在真值里是字典序）。
        # 而 §4.3 规定等价类键按**声明书写顺序**拼接，顺序是语义的一部分，不能丢。
        # 因此这里另存一份**有序数组**：M2 读它，不要读 `declaration.columns` 的键序。
        "declaration_order": [
            {"name": column, "role": spec["decl"]["columns"][column]["role"],
             **({"precision": spec["decl"]["columns"][column]["precision"]}
                if "precision" in spec["decl"]["columns"][column] else {})}
            for column in spec["decl"]["columns"]
        ],
        # ── 下钻细节（M2/M3/M4 落地时用；同样只含输入与期望，无 observed_*） ──
        "meta": {
            "generator": "tools/gen_fixtures.py",
            "oracle": "tools/fixture_oracle.py",
            "policy": spec["policy"],
            "threshold": spec["threshold"],
            "budget": spec["budget"],
            "pool": sorted(spec["pool"]),
        },
        "declaration": spec["decl"],
        "qi_columns": qi,
        "sensitive_columns": sensitive,
        "missing_cells": missing_cells,
        "k_l_t": {
            "k": default_policy["k"],
            "l": default_policy["l"],
            "t": default_policy["t"],
            "class_count": default_policy["class_count"],
            "class_size_histogram": default_policy["class_size_histogram"],
            "undecided_rows": default_policy["undecided_rows"],
            "missing_class": default_policy["missing_class"],
        },
        "by_policy": by_policy,
        "search": search,
        "search_scenarios": scenarios,
    }


# ── 写出与比对 ───────────────────────────────────────────────────────────

def generate_suite(name, target: Path):
    spec = BUILDERS[name]()
    truth = build_truth(name, spec)
    suite_dir = target / name
    write_table(suite_dir / "table.csv", spec["columns"], spec["rows"])
    truth_path = suite_dir / "truth.json"
    write_bytes_atomic(truth_path, dumps(truth).encode("utf-8"))
    return spec, truth, truth_path


def generate_all(target: Path):
    entries = {}
    for name in SUITES:
        spec, truth, truth_path = generate_suite(name, target)
        entries[name] = {
            "rows": truth["rows"],
            "columns": truth["columns"],
            "params": truth["meta"],
            "table": "%s/table.csv" % name,
            "truth": "%s/truth.json" % name,
            "truth_sha256": sha256_file(truth_path),
        }
    manifest = {
        "format": MANIFEST_FORMAT,
        "seed": SEED,
        "generator": "tools/gen_fixtures.py",
        "generator_sha256": sha256_file(GENERATOR),
        "oracle": "tools/fixture_oracle.py",
        "oracle_sha256": sha256_file(ORACLE),
        "suites": entries,
    }
    manifest_path = target / "manifest.json"
    write_bytes_atomic(manifest_path, dumps(manifest).encode("utf-8"))
    return manifest, manifest_path


def _compare(expected: Path, actual: Path, label: str, problems) -> None:
    if not actual.is_file():
        problems.append("%s: 重生成未产出该文件" % label)
        return
    if not expected.is_file():
        problems.append("%s: 入仓文件缺失" % label)
        return
    if expected.read_bytes() != actual.read_bytes():
        problems.append("%s: 逐字节不一致（生成器改动未重生成？）" % label)


def check(target: Path) -> int:
    """重生成到临时目录 → 与入仓真值 / manifest（以及已存在的表）逐字节比对。"""
    temp = Path(tempfile.mkdtemp(prefix="fixtures-check-"))
    problems = []
    try:
        generate_all(temp)
        for name in SUITES:
            _compare(target / name / "truth.json", temp / name / "truth.json", "%s/truth.json" % name, problems)
            # 表可能不在（`.gitignore` 排除 `*.csv`）：只在入仓侧存在时比对。
            if (target / name / "table.csv").is_file():
                _compare(target / name / "table.csv", temp / name / "table.csv", "%s/table.csv" % name, problems)
        _compare(target / "manifest.json", temp / "manifest.json", "manifest.json", problems)
    finally:
        shutil.rmtree(str(temp), ignore_errors=True)

    for line in problems:
        sys.stdout.write("FAIL  %s\n" % line)
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(
        "结论: %s\n" % ("逐字节一致（%d 组夹具）" % len(SUITES) if not problems else "%d 处不一致" % len(problems))
    )
    return 0 if not problems else 1


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

    parser = argparse.ArgumentParser(description="合成夹具生成器（固定种子 + 独立 oracle 真值）")
    parser.add_argument("--out", default=str(ROOT / "data" / "fixtures"), help="输出根目录")
    parser.add_argument("--only", choices=SUITES, default=None,
                        help="只生成一组；**不写 manifest.json**（全集清单只能由全集运行改写）")
    parser.add_argument("--check", action="store_true", help="重生成到临时目录并逐字节比对")
    args = parser.parse_args(argv)
    target = Path(args.out)

    if args.check:
        return check(target)

    if args.only:
        spec, truth, truth_path = generate_suite(args.only, target)
        sys.stdout.write(
            "局部生成 %s：%d 行 × %d 列 → %s（manifest.json 未改写）\n"
            % (args.only, truth["rows"], len(truth["columns"]), truth_path)
        )
        return 0

    manifest, manifest_path = generate_all(target)
    for name in SUITES:
        entry = manifest["suites"][name]
        sys.stdout.write(
            "%-7s %4d 行 × %2d 列  truth sha256=%s…\n"
            % (name, entry["rows"], len(entry["columns"]), entry["truth_sha256"][:16])
        )
    sys.stdout.write("manifest → %s\n" % manifest_path)
    sys.stdout.write("结论: 全集生成完成（%d 组）\n" % len(SUITES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
