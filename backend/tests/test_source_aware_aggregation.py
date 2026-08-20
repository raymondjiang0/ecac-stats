import pytest
from datetime import date, timedelta
from app.models import Player, Game, PlayerGameStats, TeamGameStats
from app.calculations import aggregate_player_stats, aggregate_team_stats


@pytest.fixture
def player(db_session):
    p = Player(name="Test", number="10", position="F", is_center=True, active=True)
    db_session.add(p)
    db_session.commit()
    return p


@pytest.fixture
def games_mixed_sources(db_session):
    games = []
    for i, source in enumerate(["49ing", "49ing", "instat"]):
        g = Game(date=date(2025, 10, 1) + timedelta(days=i * 4),
                 opponent=f"O{i}", is_home=True, season="2025-26",
                 data_source=source)
        db_session.add(g)
        games.append(g)
    db_session.commit()
    return games


class TestAggregatePlayerStatsAvailability:
    def test_returns_availability_dict(self, db_session, player, games_mixed_sources):
        # Add per-60 rows for the two 49ing games only
        for g in games_mixed_sources[:2]:
            db_session.add(PlayerGameStats(
                player_id=player.id, game_id=g.id,
                toi_5v5=15.0, cf60=50.0, ca60=40.0,
                xgf60=2.5, xga60=2.0,
                ff60=40.0, fa60=30.0, sf60=25.0, sa60=20.0,
            ))
        db_session.commit()
        pgs_rows = db_session.query(PlayerGameStats).filter_by(player_id=player.id).all()

        result = aggregate_player_stats(player, pgs_rows, games_mixed_sources)

        assert "availability" in result
        # cf60 is available from both sources → all 3 games "count" for the window,
        # but only 2 have data → availability reports the 2
        assert result["availability"]["cf60"]["games"] == 2
        # xfsh_pct is 49ing-only → available games = 2, both marked 49ing
        assert result["availability"]["xfsh_pct"]["games"] == 2
        assert set(result["availability"]["xfsh_pct"]["sources"]) == {"49ing"}


class TestAggregateTeamStatsAvailability:
    def test_returns_availability_dict(self, db_session, games_mixed_sources):
        for g in games_mixed_sources[:2]:
            db_session.add(TeamGameStats(
                game_id=g.id,
                cf_for_5v5=60, cf_against_5v5=40,
                xgf_5v5=2.5, xga_5v5=2.0,
                total_game_time=60, toi_pp=5, toi_pk=5, other_toi=0,
            ))
        db_session.commit()
        tgs_rows = db_session.query(TeamGameStats).all()

        result = aggregate_team_stats(tgs_rows, games_mixed_sources)

        assert "availability" in result
        # xgf_pct 49ing-only, 2 games have data
        assert result["availability"]["xgf_pct"]["games"] == 2
        # cf_pct is both-source; 2 games have data (49ing rows only for now)
        assert result["availability"]["cf_pct"]["games"] == 2
