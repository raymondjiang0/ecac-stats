import pytest
from datetime import date
from app.models import Player, Game, PlayerGameStatsInStat, TeamGameStatsInStat
from app.enrichment import load_player_instat_rows, load_team_instat_rows


@pytest.fixture
def seeded_instat(db_session):
    p = Player(name="Ten", number="10", position="F", is_center=True, active=True)
    games = [
        Game(date=date(2025, 10, 1), opponent="A", is_home=True,  season="2025-26", data_source="instat"),
        Game(date=date(2025, 10, 8), opponent="B", is_home=False, season="2025-26", data_source="instat"),
        Game(date=date(2025, 10, 15), opponent="C", is_home=True, season="2025-26", data_source="49ing"),
    ]
    db_session.add(p)
    for g in games:
        db_session.add(g)
    db_session.commit()

    for g in games[:2]:  # only InStat games get InStat rows
        db_session.add(PlayerGameStatsInStat(
            player_id=p.id, game_id=g.id,
            shots=5, hits_delivered=2, pb_won_dz=3, pb_total_dz=5,
        ))
        db_session.add(TeamGameStatsInStat(
            game_id=g.id, pp_shots=8, pp_time_seconds_total=300,
        ))
    db_session.commit()
    return p, games


class TestLoadPlayerInstatRows:
    def test_loads_all_when_no_date_filter(self, db_session, seeded_instat):
        p, _ = seeded_instat
        rows = load_player_instat_rows(db_session, p.id)
        assert len(rows) == 2

    def test_filters_by_date_range(self, db_session, seeded_instat):
        p, _ = seeded_instat
        rows = load_player_instat_rows(db_session, p.id,
                                       date_from=date(2025, 10, 5),
                                       date_to=date(2025, 10, 20))
        assert len(rows) == 1

    def test_returns_empty_for_unknown_player(self, db_session, seeded_instat):
        rows = load_player_instat_rows(db_session, 99999)
        assert rows == []


class TestLoadTeamInstatRows:
    def test_loads_all_when_no_date_filter(self, db_session, seeded_instat):
        rows = load_team_instat_rows(db_session)
        assert len(rows) == 2

    def test_filters_by_date_range(self, db_session, seeded_instat):
        rows = load_team_instat_rows(db_session,
                                     date_from=date(2025, 10, 5),
                                     date_to=date(2025, 10, 20))
        assert len(rows) == 1


class TestModuleScaffold:
    def test_module_importable(self):
        import app.tier2_stats  # noqa: F401
