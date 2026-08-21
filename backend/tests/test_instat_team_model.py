import pytest
from datetime import date
from app.models import Game, TeamGameStatsInStat


@pytest.fixture
def sample_game(db_session):
    g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True, season="2025-26",
             data_source="instat")
    db_session.add(g)
    db_session.commit()
    return g


class TestTeamGameStatsInStat:
    def test_can_create_row(self, db_session, sample_game):
        row = TeamGameStatsInStat(
            game_id=sample_game.id,
            pp_shots=12, pp_time_seconds_in_oz=317, pp_time_seconds_total=429,
            pk_opp_breakouts=6, pp_opp_breakouts_allowed=2,
            puck_possession_seconds_total=1197,
            oz_possession_seconds=597, oz_possession_pct=0.50,
            scoring_chance_shots=33, scoring_chance_shots_on_goal=24,
        )
        db_session.add(row)
        db_session.commit()
        assert row.id is not None

    def test_all_fields_default_none(self, db_session, sample_game):
        row = TeamGameStatsInStat(game_id=sample_game.id)
        db_session.add(row)
        db_session.commit()
        assert row.pp_shots is None
        assert row.oz_possession_pct is None

    def test_unique_game(self, db_session, sample_game):
        from sqlalchemy.exc import IntegrityError
        db_session.add(TeamGameStatsInStat(game_id=sample_game.id))
        db_session.commit()
        db_session.add(TeamGameStatsInStat(game_id=sample_game.id))
        with pytest.raises(IntegrityError):
            db_session.commit()
