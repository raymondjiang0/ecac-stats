import pytest
from datetime import date
from app.models import (
    Player, Game, TeamGameStatsInStat, PlayerGameStatsInStat,
    PlayerHitMatrix, PlayerPassMatrix,
)
from app.ingest.commit import commit_parsed


@pytest.fixture
def game_and_players(db_session):
    g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True,
             season="2025-26", data_source="instat")
    p10 = Player(name="Ten", number="10", position="F", is_center=True, active=True)
    p7  = Player(name="Seven", number="7", position="F", is_center=False, active=True)
    db_session.add_all([g, p10, p7])
    db_session.commit()
    return g, p10, p7


class TestCommitParsed:
    def test_writes_team_stats(self, db_session, game_and_players):
        g, _, _ = game_and_players
        parsed = {
            "templates": {
                "instat_team_stats": {
                    "pp_shots": 12, "pp_time_seconds_total": 429,
                    "oz_possession_pct": 0.50,
                    # rest None
                    "pp_time_seconds_in_oz": None, "pk_opp_breakouts": None,
                    "pp_opp_breakouts_allowed": None,
                    "puck_possession_seconds_total": None,
                    "oz_possession_seconds": None,
                    "scoring_chance_shots": None, "scoring_chance_shots_on_goal": None,
                },
                "instat_players_main": [], "instat_time_distribution": [],
                "instat_challenges": [], "instat_hit_matrix": [], "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        report = commit_parsed(parsed, g.id, db_session)
        assert report["wrote"]["instat_team_stats"] == 1
        row = db_session.query(TeamGameStatsInStat).filter_by(game_id=g.id).one()
        assert row.pp_shots == 12
        assert row.oz_possession_pct == 0.50

    def test_writes_players_main(self, db_session, game_and_players):
        g, p10, p7 = game_and_players
        parsed = {
            "templates": {
                "instat_team_stats": _empty_team(),
                "instat_players_main": [
                    {"jersey_number": "10", "player_name": "Ten",
                     "shots": 5, "corsi_plus": 12, "hits_delivered": 2},
                    {"jersey_number": "7", "player_name": "Seven",
                     "shots": 3, "corsi_plus": 8},
                ],
                "instat_time_distribution": [], "instat_challenges": [],
                "instat_hit_matrix": [], "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        report = commit_parsed(parsed, g.id, db_session)
        assert report["wrote"]["instat_players_main"] == 2
        rows = db_session.query(PlayerGameStatsInStat).filter_by(game_id=g.id).all()
        assert len(rows) == 2

    def test_writes_hit_matrix(self, db_session, game_and_players):
        g, p10, p7 = game_and_players
        parsed = {
            "templates": {
                "instat_team_stats": _empty_team(),
                "instat_players_main": [], "instat_time_distribution": [],
                "instat_challenges": [],
                "instat_hit_matrix": [
                    {"from_jersey": "10", "from_name": "Ten",
                     "to_jersey": "7", "to_name": "Seven",
                     "delivered": 3, "received": 1},
                ],
                "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        report = commit_parsed(parsed, g.id, db_session)
        assert report["wrote"]["instat_hit_matrix"] == 1
        row = db_session.query(PlayerHitMatrix).filter_by(game_id=g.id).one()
        assert row.from_player_id == p10.id
        assert row.to_player_id == p7.id
        assert row.delivered == 3

    def test_skips_unknown_jersey(self, db_session, game_and_players):
        g, _, _ = game_and_players
        parsed = {
            "templates": {
                "instat_team_stats": _empty_team(),
                "instat_players_main": [
                    {"jersey_number": "99", "player_name": "Ghost", "shots": 1},
                ],
                "instat_time_distribution": [], "instat_challenges": [],
                "instat_hit_matrix": [], "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        report = commit_parsed(parsed, g.id, db_session)
        assert report["wrote"]["instat_players_main"] == 0
        assert any("99" in s for s in report["skipped"])

    def test_upserts_on_reingest(self, db_session, game_and_players):
        g, p10, _ = game_and_players
        parsed_v1 = {
            "templates": {
                "instat_team_stats": _empty_team(),
                "instat_players_main": [
                    {"jersey_number": "10", "player_name": "Ten", "shots": 5},
                ],
                "instat_time_distribution": [], "instat_challenges": [],
                "instat_hit_matrix": [], "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        commit_parsed(parsed_v1, g.id, db_session)
        # Re-ingest with different value
        parsed_v2 = {
            "templates": {
                "instat_team_stats": _empty_team(),
                "instat_players_main": [
                    {"jersey_number": "10", "player_name": "Ten", "shots": 9},
                ],
                "instat_time_distribution": [], "instat_challenges": [],
                "instat_hit_matrix": [], "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        commit_parsed(parsed_v2, g.id, db_session)
        rows = db_session.query(PlayerGameStatsInStat).filter_by(game_id=g.id).all()
        assert len(rows) == 1
        assert rows[0].shots == 9


    def test_hit_matrix_none_values_committed_as_zero(self, db_session, game_and_players):
        """Regression: user-cleared cells send None; `or 0` must coerce to 0
        instead of letting IntegrityError abort the whole commit."""
        g, p10, p7 = game_and_players
        parsed = {
            "templates": {
                "instat_team_stats": _empty_team(),
                "instat_players_main": [], "instat_time_distribution": [],
                "instat_challenges": [],
                "instat_hit_matrix": [
                    {"from_jersey": "10", "from_name": "Ten",
                     "to_jersey": "7", "to_name": "Seven",
                     "delivered": None, "received": None},
                ],
                "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        report = commit_parsed(parsed, g.id, db_session)
        assert report["wrote"]["instat_hit_matrix"] == 1
        row = db_session.query(PlayerHitMatrix).filter_by(game_id=g.id).one()
        assert row.delivered == 0
        assert row.received == 0


def _empty_team():
    return {
        "pp_shots": None, "pp_time_seconds_in_oz": None,
        "pp_time_seconds_total": None, "pk_opp_breakouts": None,
        "pp_opp_breakouts_allowed": None,
        "puck_possession_seconds_total": None,
        "oz_possession_seconds": None, "oz_possession_pct": None,
        "scoring_chance_shots": None, "scoring_chance_shots_on_goal": None,
    }
