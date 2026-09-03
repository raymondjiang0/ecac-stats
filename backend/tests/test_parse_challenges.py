import os
import pytest
import pdfplumber
from app.ingest.parsers.challenges import parse_challenges

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParseChallenges:
    def test_returns_list(self, pdf):
        rows = parse_challenges(pdf, "HARVARD CRIMSON")
        assert isinstance(rows, list)

    def test_reasonable_row_count(self, pdf):
        rows = parse_challenges(pdf, "HARVARD CRIMSON")
        assert 10 <= len(rows) <= 25

    def test_each_row_has_expected_keys(self, pdf):
        rows = parse_challenges(pdf, "HARVARD CRIMSON")
        for r in rows:
            for k in ("jersey_number", "player_name",
                      "pb_won_dz", "pb_total_dz",
                      "pb_won_oz", "pb_total_oz",
                      "pb_won_nz", "pb_total_nz"):
                assert k in r

    def test_won_never_exceeds_total(self, pdf):
        rows = parse_challenges(pdf, "HARVARD CRIMSON")
        for r in rows:
            for won, tot in [("pb_won_dz", "pb_total_dz"),
                             ("pb_won_oz", "pb_total_oz"),
                             ("pb_won_nz", "pb_total_nz")]:
                w, t = r[won], r[tot]
                if w is not None and t is not None:
                    assert w <= t, f"{r['player_name']}: {won}={w} > {tot}={t}"

    def test_returns_empty_for_unknown_team(self, pdf):
        assert parse_challenges(pdf, "NOPE") == []
