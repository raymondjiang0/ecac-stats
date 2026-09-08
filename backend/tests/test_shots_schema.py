import pytest
from datetime import date
from app.models import Player, Game, PlayerGameShotsInStat


@pytest.fixture
def player_and_game(db_session):
    p = Player(name="Ten", number="10", position="F", is_center=True, active=True)
    g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True,
             season="2025-26", data_source="instat")
    db_session.add(p)
    db_session.add(g)
    db_session.commit()
    return p, g


class TestPlayerGameShotsInStat:
    def test_can_create_row_with_all_fields(self, db_session, player_and_game):
        p, g = player_and_game
        row = PlayerGameShotsInStat(
            player_id=p.id, game_id=g.id,
            goals=1,
            shots_total=5, shots_on_goal=3,
            shots_blocked_defensively=2,
            pp_shots_total=1, pp_shots_on_goal=1,
            sh_shots_total=0, sh_shots_on_goal=0,
            positional_shots_total=4, positional_shots_on_goal=2,
            counter_shots_total=1, counter_shots_on_goal=1,
            slot_shots_total=2, slot_shots_on_goal=2,
            center_shots_total=1, center_shots_on_goal=1,
            right_flank_shots_total=1, right_flank_shots_on_goal=0,
            left_flank_shots_total=0, left_flank_shots_on_goal=0,
            blue_line_right_shots_total=1, blue_line_right_shots_on_goal=0,
            blue_line_center_shots_total=0, blue_line_center_shots_on_goal=0,
            blue_line_left_shots_total=0, blue_line_left_shots_on_goal=0,
            slapshot_total=1, slapshot_on_goal=1,
            wristshot_total=4, wristshot_on_goal=2,
        )
        db_session.add(row)
        db_session.commit()
        assert row.id is not None

    def test_all_fields_default_none(self, db_session, player_and_game):
        p, g = player_and_game
        row = PlayerGameShotsInStat(player_id=p.id, game_id=g.id)
        db_session.add(row)
        db_session.commit()
        assert row.goals is None
        assert row.shots_total is None
        assert row.slot_shots_total is None
        assert row.slapshot_total is None

    def test_unique_player_game(self, db_session, player_and_game):
        from sqlalchemy.exc import IntegrityError
        p, g = player_and_game
        db_session.add(PlayerGameShotsInStat(player_id=p.id, game_id=g.id, goals=1))
        db_session.commit()
        db_session.add(PlayerGameShotsInStat(player_id=p.id, game_id=g.id, goals=2))
        with pytest.raises(IntegrityError):
            db_session.commit()
