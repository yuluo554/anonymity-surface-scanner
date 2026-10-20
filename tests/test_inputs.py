"""表格读取与声明校验的单元测试（M1 的输入面）。"""
from __future__ import annotations

import json

import pytest

from anonymity_scanner.declaration import load_declaration
from anonymity_scanner.exit_codes import DeclarationError, InputError
from anonymity_scanner.tableio import is_missing, missing_set, read_table


def test_missing_set_is_frozen():
    tokens = missing_set()
    with pytest.raises(AttributeError):
        tokens.add("X")  # type: ignore[attr-defined]


@pytest.mark.parametrize("token", ["", "NA", "N/A", "null", "NULL", "-"])
def test_missing_tokens(token):
    assert is_missing(token)


@pytest.mark.parametrize("token", ["na", "Null", "0", "N/A ", " "])
def test_non_missing_tokens(token):
    assert not is_missing(token)


def test_row_numbers_are_one_based_and_skip_blank_lines(tmp_path):
    path = tmp_path / "t.csv"
    path.write_bytes("a,b\n1,2\n\n3,4\n".encode("utf-8"))
    table = read_table(path)
    assert [row[0] for row in table.rows] == [1, 2]
    assert table.header == ["a", "b"]


def test_bom_is_stripped(tmp_path):
    path = tmp_path / "t.csv"
    path.write_bytes("age,zip\n30,100\n".encode("utf-8-sig"))
    assert read_table(path).header == ["age", "zip"]


def test_tsv_delimiter(tmp_path):
    path = tmp_path / "t.tsv"
    path.write_bytes("age\tzip\n30\t100\n".encode("utf-8"))
    table = read_table(path)
    assert table.header == ["age", "zip"]
    assert table.rows == [(1, ["30", "100"])]


def test_duplicate_header_rejected(tmp_path):
    path = tmp_path / "t.csv"
    path.write_bytes("a,a\n1,2\n".encode("utf-8"))
    with pytest.raises(InputError) as excinfo:
        read_table(path)
    assert "重复列名" in excinfo.value.message


def test_non_utf8_rejected(tmp_path):
    path = tmp_path / "t.csv"
    path.write_bytes("age\n张三\n".encode("gbk"))
    with pytest.raises(InputError) as excinfo:
        read_table(path)
    assert "UTF-8" in excinfo.value.message


def test_empty_file_rejected(tmp_path):
    path = tmp_path / "t.csv"
    path.write_bytes(b"")
    with pytest.raises(InputError):
        read_table(path)


def test_header_only_table_is_allowed(tmp_path):
    """只有表头的表是合法输入（0 行）；空表语义由计算层定义，不在读取层报错。"""
    path = tmp_path / "t.csv"
    path.write_bytes("a,b\n".encode("utf-8"))
    table = read_table(path)
    assert table.row_count == 0
    assert table.header == ["a", "b"]


def _decl(tmp_path, columns):
    path = tmp_path / "d.json"
    path.write_bytes(json.dumps({"columns": columns}).encode("utf-8"))
    return path


def test_qi_order_follows_declaration_not_table(tmp_path):
    path = _decl(tmp_path, {"zip": {"role": "qi"}, "age": {"role": "qi"}})
    decl = load_declaration(path, ["age", "zip", "disease"])
    assert [c.name for c in decl.qi_columns()] == ["zip", "age"]


def test_undeclared_and_direct_identifier_are_listed(tmp_path):
    path = _decl(tmp_path, {"name": {"role": "direct-identifier"}, "zip": {"role": "qi"}})
    decl = load_declaration(path, ["age", "zip", "name"])
    unused = {item["column"]: item["reason"] for item in decl.unparticipating()}
    assert unused == {"age": "undeclared", "name": "direct-identifier"}
    assert decl.direct_identifier_warning() == ["name"]


def test_unknown_top_level_key_rejected(tmp_path):
    path = tmp_path / "d.json"
    path.write_bytes(json.dumps({"columns": {"age": {"role": "qi"}}, "extra": 1}).encode("utf-8"))
    with pytest.raises(DeclarationError) as excinfo:
        load_declaration(path, ["age"])
    assert "未知顶层键" in excinfo.value.message


def test_role_specific_keys_are_enforced(tmp_path):
    path = _decl(tmp_path, {"age": {"role": "qi", "precision": "year"}})
    with pytest.raises(DeclarationError) as excinfo:
        load_declaration(path, ["age"])
    assert "不允许的键" in excinfo.value.message


def test_date_precision_accepted(tmp_path):
    path = _decl(tmp_path, {"dob": {"role": "date-precision", "precision": "month"}})
    decl = load_declaration(path, ["dob"])
    assert decl.by_role("date-precision")[0].precision == "month"


def test_empty_columns_rejected(tmp_path):
    path = _decl(tmp_path, {})
    with pytest.raises(DeclarationError):
        load_declaration(path, ["age"])


def test_non_json_rejected(tmp_path):
    path = tmp_path / "d.json"
    path.write_bytes(b"{not json")
    with pytest.raises(DeclarationError):
        load_declaration(path, ["age"])
