import os
import pytest
import pdfplumber
from app.ingest.parsers.time_distribution import parse_time_distribution

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParseTimeDistribution:
    def test_returns_list(self, pdf):
        rows = parse_time_distribution(pdf, "HARVARD CRIMSON")
        assert isinstance(rows, list)

    def test_reasonable_row_count(self, pdf):
        rows = parse_time_distribution(pdf, "HARVARD CRIMSON")
        assert 10 <= len(rows) <= 25

    def test_each_row_has_expected_keys(self, pdf):
        rows = parse_time_distribution(pdf, "HARVARD CRIMSON")
        for r in rows:
            for k in ("jersey_number", "player_name",
                      "toi_5v5_seconds", "toi_pp_seconds", "toi_sh_seconds"):
                assert k in r

    def test_seconds_are_int_or_none(self, pdf):
        rows = parse_time_distribution(pdf, "HARVARD CRIMSON")
        for r in rows:
            for k in ("toi_5v5_seconds", "toi_pp_seconds", "toi_sh_seconds"):
                assert r[k] is None or isinstance(r[k], int)

    def test_returns_empty_for_unknown_team(self, pdf):
        assert parse_time_distribution(pdf, "NOPE") == []
