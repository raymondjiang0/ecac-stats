import os
import pytest
import pdfplumber
from app.ingest.parsers.hit_matrix import parse_hit_matrix

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParseHitMatrix:
    def test_returns_list(self, pdf):
        rows = parse_hit_matrix(pdf, "HARVARD CRIMSON")
        assert isinstance(rows, list)

    def test_all_rows_are_non_empty_pairs(self, pdf):
        # Parser omits pairs where both delivered and received are 0 (from '—')
        rows = parse_hit_matrix(pdf, "HARVARD CRIMSON")
        for r in rows:
            assert r["delivered"] > 0 or r["received"] > 0, (
                f"row {r} has no interaction; should be omitted"
            )

    def test_each_row_has_pair_and_counts(self, pdf):
        rows = parse_hit_matrix(pdf, "HARVARD CRIMSON")
        for r in rows:
            for k in ("from_jersey", "from_name", "to_jersey", "to_name",
                      "delivered", "received"):
                assert k in r
            assert isinstance(r["delivered"], int)
            assert isinstance(r["received"], int)

    def test_returns_empty_for_unknown_team(self, pdf):
        assert parse_hit_matrix(pdf, "NOPE") == []
