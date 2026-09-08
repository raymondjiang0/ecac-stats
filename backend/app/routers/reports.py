from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional
from ..database import get_db
from ..models import Player, Game, TeamGameStats, PlayerGameStats
from ..calculations import aggregate_team_stats, aggregate_player_stats
from ..report_generator import generate_player_report, generate_team_report
from ..enrichment import enrich_player_agg, load_player_instat_rows, load_team_instat_rows, build_position_cohorts, load_player_shots_rows

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _filter_games(db: Session, date_from: Optional[date], date_to: Optional[date]) -> list:
    q = db.query(Game).order_by(Game.date)
    if date_from:
        q = q.filter(Game.date >= date_from)
    if date_to:
        q = q.filter(Game.date <= date_to)
    return q.all()


@router.get("/player/{player_id}")
def player_report(
    player_id: int,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    player = db.query(Player).get(player_id)
    if not player:
        raise HTTPException(404, "Player not found")

    games = _filter_games(db, date_from, date_to)
    game_ids = {g.id for g in games}

    pgs_rows = (
        db.query(PlayerGameStats)
        .filter(PlayerGameStats.player_id == player_id,
                PlayerGameStats.game_id.in_(game_ids))
        .all()
    )
    agg = aggregate_player_stats(player, pgs_rows, games)

    # Build all_aggs so enrichment can compute cohort baselines
    all_players = db.query(Player).filter_by(active=True).all()
    all_aggs = []
    for other in all_players:
        other_pgs = (
            db.query(PlayerGameStats)
            .filter(PlayerGameStats.player_id == other.id,
                    PlayerGameStats.game_id.in_(game_ids))
            .all()
        )
        other_agg = aggregate_player_stats(other, other_pgs, games)
        all_aggs.append((other, other_agg))
    instat_rows = load_player_instat_rows(db, player_id, date_from, date_to)
    team_rows = load_team_instat_rows(db, date_from, date_to)
    position_cohorts = build_position_cohorts(all_players, db, date_from, date_to)
    shots_rows = load_player_shots_rows(db, player_id, date_from, date_to)

    agg = enrich_player_agg(
        player, agg, all_aggs,
        instat_rows=instat_rows,
        team_instat_rows=team_rows,
        pgs_rows=pgs_rows,
        position_cohorts=position_cohorts,
        shots_rows=shots_rows,
    )

    tgs_rows = db.query(TeamGameStats).filter(TeamGameStats.game_id.in_(game_ids)).all()
    team_agg = aggregate_team_stats(tgs_rows, games)

    pdf_bytes = generate_player_report(player, agg, team_agg)
    safe_name = player.name.replace(" ", "_")
    date_suffix = f"_{date_from}_to_{date_to}" if date_from or date_to else ""
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="player_{safe_name}{date_suffix}_report.pdf"'},
    )


@router.get("/team")
def team_report(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    games = _filter_games(db, date_from, date_to)
    game_ids = {g.id for g in games}
    tgs_rows = db.query(TeamGameStats).filter(TeamGameStats.game_id.in_(game_ids)).all()
    team_agg = aggregate_team_stats(tgs_rows, games)

    pdf_bytes = generate_team_report(team_agg)
    date_suffix = f"_{date_from}_to_{date_to}" if date_from or date_to else ""
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="team{date_suffix}_report.pdf"'},
    )
