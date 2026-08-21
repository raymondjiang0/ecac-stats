import pytest
from datetime import date
from app.models import Game
from app.stat_sources import (
    STAT_SOURCES, stat_available_from, games_with_stat
)


class TestStatSources:
    def test_cf60_available_from_49ing(self):
        assert stat_available_from("49ing", "cf60") is True

    def test_cf60_available_from_both(self):
        # 49ing side of "both" supplies cf60
        assert stat_available_from("both", "cf60") is True

    def test_puck_battle_pct_only_from_instat(self):
        assert stat_available_from("instat", "puck_battle_pct") is True
        assert stat_available_from("49ing", "puck_battle_pct") is False
        assert stat_available_from("both", "puck_battle_pct") is True

    def test_attack_scenario_only_from_49ing(self):
        # Per spec §9: attack scenario xG is team-level 49ing-only
        assert stat_available_from("49ing", "rush_share") is True
        assert stat_available_from("instat", "rush_share") is False


class TestGamesWithStat:
    def _game(self, data_source, id_=None):
        g = Game(date=date(2025, 10, 1), opponent="X",
                 is_home=True, season="2025-26", data_source=data_source)
        if id_ is not None:
            g.id = id_
        return g

    def test_filters_49ing_games_out_for_instat_only_stat(self):
        games = [self._game("49ing", 1), self._game("instat", 2), self._game("both", 3)]
        result = games_with_stat(games, "puck_battle_pct")
        ids = {g.id for g in result}
        assert ids == {2, 3}

    def test_keeps_all_when_stat_is_universal(self):
        games = [self._game("49ing", 1), self._game("instat", 2), self._game("both", 3)]
        result = games_with_stat(games, "toi_5v5")  # TOI both sources supply
        assert len(result) == 3

    def test_empty_for_stat_no_source_supplies(self):
        games = [self._game("49ing", 1)]
        result = games_with_stat(games, "totally_unknown_stat")
        assert result == []


class TestStatSourcesCoverage:
    def test_all_existing_stat_keys_declared(self):
        """Every stat currently returned by aggregate_player_stats or
        aggregate_team_stats must have an entry in STAT_SOURCES so the
        aggregation layer doesn't accidentally filter to zero games."""
        existing_player_stats = {
            "toi_5v5", "on_ice_cf_pct", "on_ice_xgf_pct", "on_ice_sf_pct",
            "cf60", "ca60", "ff60", "fa60", "sf60", "sa60",
            "xfsh_pct", "xfsv_pct",
            "icf", "isf",
            "median_shift_seconds",
            "personal_fo_pct", "on_ice_fo_pct",
        }
        existing_team_stats = {
            "cf_pct", "xgf_pct", "xgf60", "xga60",
            "pp_cf_pct", "pp_xgf_pct", "pk_cf_pct", "pk_xgf_pct",
            "rush_share", "oz_fc_share", "oz_fo_share", "sust_pos_share",
        }
        missing = (existing_player_stats | existing_team_stats) - set(STAT_SOURCES.keys())
        assert not missing, f"Missing STAT_SOURCES entries for: {missing}"
