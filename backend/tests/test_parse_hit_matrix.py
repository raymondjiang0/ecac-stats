import os
import pytest
import pdfplumber
from app.ingest.parsers.hit_matrix import parse_hit_matrix, _parse_hit_cell, _extract_hit_pairs

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParseHitCell:
    """Unit tests for the _parse_hit_cell helper."""

    def test_delivered_greater_than_received_not_dropped(self):
        """Cells where delivered > received must NOT be dropped (no ordering invariant)."""
        delivered, received = _parse_hit_cell("3—1")
        assert delivered == 3, f"expected delivered=3, got {delivered}"
        assert received == 1, f"expected received=1, got {received}"

    def test_received_greater_than_delivered(self):
        delivered, received = _parse_hit_cell("1—3")
        assert delivered == 1
        assert received == 3

    def test_bare_dash_returns_none_none(self):
        assert _parse_hit_cell("—") == (None, None)
        assert _parse_hit_cell("-") == (None, None)

    def test_empty_string_returns_none_none(self):
        assert _parse_hit_cell("") == (None, None)

    def test_slash_separator(self):
        delivered, received = _parse_hit_cell("2/4")
        assert delivered == 2
        assert received == 4

    def test_hyphen_separator(self):
        delivered, received = _parse_hit_cell("5-2")
        assert delivered == 5
        assert received == 2


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
            assert isinstance(r["from_jersey"], str)
            assert isinstance(r["from_name"], str)
            assert isinstance(r["to_jersey"], str)
            assert isinstance(r["to_name"], str)

    def test_no_self_hit_pairs(self, pdf):
        """No row should have from_jersey == to_jersey (self-hit guard)."""
        rows = parse_hit_matrix(pdf, "HARVARD CRIMSON")
        for r in rows:
            assert r["from_jersey"] != r["to_jersey"], (
                f"self-hit pair found: {r}"
            )

    def test_returns_empty_for_unknown_team(self, pdf):
        assert parse_hit_matrix(pdf, "NOPE") == []
