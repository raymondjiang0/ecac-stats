import os
import pytest
import pdfplumber
from app.ingest.parsers.pass_matrix import parse_pass_matrix

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParsePassMatrix:
    def test_returns_list(self, pdf):
        rows = parse_pass_matrix(pdf, "HARVARD CRIMSON")
        assert isinstance(rows, list)

    def test_all_rows_have_positive_count(self, pdf):
        rows = parse_pass_matrix(pdf, "HARVARD CRIMSON")
        for r in rows:
            assert r["count"] > 0

    def test_each_row_has_pair_and_count(self, pdf):
        rows = parse_pass_matrix(pdf, "HARVARD CRIMSON")
        for r in rows:
            for k in ("from_jersey", "from_name", "to_jersey", "to_name", "count"):
                assert k in r
            assert isinstance(r["count"], int)
            for k in ("from_jersey", "from_name", "to_jersey", "to_name"):
                assert isinstance(r[k], str)

    def test_reasonable_pair_count(self, pdf):
        # Fixture's Harvard passes matrix has 139 total passes across many pairs
        rows = parse_pass_matrix(pdf, "HARVARD CRIMSON")
        assert 20 <= len(rows) <= 200

    def test_returns_empty_for_unknown_team(self, pdf):
        assert parse_pass_matrix(pdf, "NOPE") == []

    def test_no_self_pass_pairs(self, pdf):
        rows = parse_pass_matrix(pdf, "HARVARD CRIMSON")
        for r in rows:
            assert r["from_jersey"] != r["to_jersey"]
