"""Frozen SQL fingerprints tolerate checkout newlines, never content changes."""

import hashlib
import json
from importlib.resources import files

import pytest
from legal_checker.migrations.manager import sql_resource_checksum

ROOT = files("legal_checker.migrations")
BASELINES = json.loads(ROOT.joinpath("legacy_baselines.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("version", ["1", "2", "3"])
def test_frozen_sql_checksum_is_independent_of_checkout_line_endings(version):
    baseline = BASELINES[version]
    source = ROOT.joinpath("sql", baseline["sql_file"]).read_bytes()
    lf = source.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    assert hashlib.sha256(lf).hexdigest() == baseline["sql_sha256"]
    assert hashlib.sha256(crlf).hexdigest() != baseline["sql_sha256"]
    assert sql_resource_checksum(lf) == baseline["sql_sha256"]
    assert sql_resource_checksum(crlf) == baseline["sql_sha256"]


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.replace(b"SELECT", b"select"),
        lambda value: value.replace(b"1;", b"2;"),
        lambda value: value.replace(b" ", b"  "),
        lambda value: value.replace(b"\n", b"\r"),
        lambda value: b"\xef\xbb\xbf" + value,
        lambda value: value + b"-- changed\n",
    ],
    ids=["case", "SQL-value", "whitespace", "lone-CR", "BOM", "comment"],
)
def test_only_crlf_conversion_is_normalized(change):
    lf = "-- cột tiếng Việt\nSELECT 1;\n".encode()
    expected = hashlib.sha256(lf).hexdigest()
    assert sql_resource_checksum(lf.replace(b"\n", b"\r\n")) == expected
    assert sql_resource_checksum(change(lf)) != expected
