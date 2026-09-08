import pytest
from datetime import date
from app.models import (
    Player, Game, PlayerGameStats, PlayerGameStatsInStat, TeamGameStatsInStat,
    PlayerGameShotsInStat,
)
from app.enrichment import enrich_player_agg, load_player_shots_rows


@pytest.fixture
def enriched_setup(db_session):
    p = Player(name="Ten", number="10", position="F", is_center=True, active=True)
    g1 = Game(date=date(2025, 10, 1), opponent="A", is_home=True,
              season="2025-26", data_source="instat")
    g2 = Game(date=date(2025, 10, 8), opponent="B", is_home=False,
              season="2025-26", data_source="instat")
    db_session.add_all([p, g1, g2])
    db_session.commit()

    pgs_rows = []
    instat_rows = []
    team_rows = []
    shots_rows = []
    for g in [g1, g2]:
        pgs = PlayerGameStats(player_id=p.id, game_id=g.id,
                              toi_5v5=15.0, cf60=50, ca60=40,
                              xgf60=2.5, xga60=2.0,
                              ff60=40, fa60=35, sf60=30, sa60=25)
        db_session.add(pgs); pgs_rows.append(pgs)
        ir = PlayerGameStatsInStat(player_id=p.id, game_id=g.id,
                                    puck_recoveries=8, pb_won_dz=3,
                                    entries_pass=2, entries_stick=3, entries_dump=1)
        db_session.add(ir); instat_rows.append(ir)
        tr = TeamGameStatsInStat(game_id=g.id,
                                  scoring_chance_shots=25,
                                  pp_shots=12, pp_time_seconds_total=600,
                                  pp_time_seconds_in_oz=360, pk_opp_breakouts=2)
        db_session.add(tr); team_rows.append(tr)
        sr = PlayerGameShotsInStat(player_id=p.id, game_id=g.id,
                                    goals=1, shots_total=5, shots_on_goal=3,
                                    shots_blocked_defensively=4,
                                    slot_shots_total=2, slot_shots_on_goal=2,
                                    center_shots_total=1, center_shots_on_goal=1)
        db_session.add(sr); shots_rows.append(sr)
    db_session.commit()

    agg = {
        "player_id": p.id, "player_name": p.name,
        "games_played": 2, "small_sample": False,
        "toi_5v5": 15.0, "trend": [],
    }
    return p, agg, pgs_rows, instat_rows, team_rows, shots_rows


class TestLoadPlayerShotsRows:
    def test_loads_rows_for_player(self, db_session, enriched_setup):
        p, *_ = enriched_setup
        rows = load_player_shots_rows(db_session, p.id)
        assert len(rows) == 2


class TestEnrichTier3:
    def test_no_shots_rows_preserves_tier2_behavior(self, enriched_setup):
        p, agg, pgs_rows, instat_rows, team_rows, _ = enriched_setup
        result = enrich_player_agg(
            p, agg, [(p, agg)],
            instat_rows=instat_rows,
            team_instat_rows=team_rows,
            pgs_rows=pgs_rows,
            position_cohorts={},
        )
        # Tier 2 keys present, Tier 3 absent
        for k in ("contested_puck", "impact_score", "danger_share"):
            assert k in result
        assert "shot_threat" not in result
        assert "ddi" not in result

    def test_with_shots_rows_attaches_tier3(self, enriched_setup):
        p, agg, pgs_rows, instat_rows, team_rows, shots_rows = enriched_setup
        result = enrich_player_agg(
            p, agg, [(p, agg)],
            instat_rows=instat_rows,
            team_instat_rows=team_rows,
            pgs_rows=pgs_rows,
            position_cohorts={},
            shots_rows=shots_rows,
        )
        assert "shot_threat" in result
        assert "ddi" in result
        assert result["shot_threat"]["totals"]["goals"] == 2
        assert result["ddi"]["components"]["shots_blocked_defensively"] == 8

    def test_danger_share_uses_true_sca_when_shots_provided(self, enriched_setup):
        p, agg, pgs_rows, instat_rows, team_rows, shots_rows = enriched_setup
        result = enrich_player_agg(
            p, agg, [(p, agg)],
            instat_rows=instat_rows,
            team_instat_rows=team_rows,
            pgs_rows=pgs_rows,
            position_cohorts={},
            shots_rows=shots_rows,
        )
        # Numerator: 2 games × (slot=2 + center=1) = 6
        assert result["danger_share"]["player_sca_shots"] == 6
