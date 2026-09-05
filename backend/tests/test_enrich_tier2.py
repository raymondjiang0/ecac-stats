import pytest
from datetime import date
from app.models import (
    Player, Game, PlayerGameStats, PlayerGameStatsInStat, TeamGameStatsInStat,
)
from app.enrichment import enrich_player_agg


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
    for g in [g1, g2]:
        pgs = PlayerGameStats(
            player_id=p.id, game_id=g.id,
            toi_5v5=15.0, xgf60=2.5, xga60=2.0, cf60=50, ca60=40,
            ff60=40, fa60=35, sf60=30, sa60=25,
        )
        db_session.add(pgs)
        pgs_rows.append(pgs)

    instat_rows = []
    team_rows = []
    for g in [g1, g2]:
        ir = PlayerGameStatsInStat(
            player_id=p.id, game_id=g.id,
            shots=5, pb_won_dz=3, pb_total_dz=5,
            entries_pass=2, entries_stick=3, entries_dump=1,
            puck_losses=6, puck_losses_dz=2, puck_recoveries=8, puck_recoveries_oz=3,
        )
        tr = TeamGameStatsInStat(
            game_id=g.id, pp_shots=12, pp_time_seconds_total=600,
            pp_time_seconds_in_oz=360, pk_opp_breakouts=2,
            scoring_chance_shots=25,
        )
        db_session.add_all([ir, tr])
        instat_rows.append(ir)
        team_rows.append(tr)
    db_session.commit()

    agg = {
        "player_id": p.id, "player_name": p.name,
        "games_played": 2, "small_sample": False,
        "toi_5v5": 15.0, "trend": [],
        # ... other fields will be filled with test values as needed
    }
    return p, agg, pgs_rows, instat_rows, team_rows


class TestEnrichTier2:
    def test_no_instat_rows_preserves_existing_behavior(self, enriched_setup):
        p, agg, _, _, _ = enriched_setup
        result = enrich_player_agg(p, agg, [(p, agg)])
        assert "flags" in result
        assert "comparisons" in result
        assert "contested_puck" not in result

    def test_with_instat_attaches_tier2_stats(self, enriched_setup):
        p, agg, pgs_rows, instat_rows, team_rows = enriched_setup
        cohorts = {"F": {
            "xg_diff": [0.0, 0.3, -0.2, 0.4, 0.1],
            "cf_pct": [0.5, 0.52, 0.48, 0.55, 0.51],
            "battle_w_pct": [0.5, 0.55, 0.48, 0.52, 0.53],
            "controlled_entry_pct": [0.6, 0.65, 0.7, 0.55, 0.58],
        }}
        result = enrich_player_agg(
            p, agg, [(p, agg)],
            instat_rows=instat_rows,
            team_instat_rows=team_rows,
            pgs_rows=pgs_rows,
            position_cohorts=cohorts,
        )
        for k in ("contested_puck", "zone_entry", "turnover_ratio",
                  "danger_share", "impact_score"):
            assert k in result, f"missing {k}"

    def test_contested_puck_shape(self, enriched_setup):
        p, agg, pgs_rows, instat_rows, team_rows = enriched_setup
        result = enrich_player_agg(
            p, agg, [(p, agg)],
            instat_rows=instat_rows,
            team_instat_rows=team_rows,
            pgs_rows=pgs_rows,
            position_cohorts={},
        )
        cp = result["contested_puck"]
        assert cp["overall_pct"] == pytest.approx(6 / 10)
        assert cp["games"] == 2

    def test_impact_score_null_with_empty_cohorts(self, enriched_setup):
        p, agg, pgs_rows, instat_rows, team_rows = enriched_setup
        result = enrich_player_agg(
            p, agg, [(p, agg)],
            instat_rows=instat_rows,
            team_instat_rows=team_rows,
            pgs_rows=pgs_rows,
            position_cohorts={},
        )
        assert result["impact_score"]["score"] is None
