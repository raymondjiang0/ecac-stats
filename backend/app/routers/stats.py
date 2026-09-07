from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional
from ..database import get_db
from ..models import Player, Game, TeamGameStats, PlayerGameStats
from ..calculations import aggregate_team_stats, aggregate_player_stats
from ..enrichment import enrich_player_agg, load_player_instat_rows, load_team_instat_rows, build_position_cohorts, load_player_shots_rows
from ..tier2_stats import special_teams_v2

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _filter_games(db: Session, date_from: Optional[date], date_to: Optional[date]) -> list:
    q = db.query(Game).order_by(Game.date)
    if date_from:
        q = q.filter(Game.date >= date_from)
    if date_to:
        q = q.filter(Game.date <= date_to)
    return q.all()


def _tgs_for_games(db: Session, game_ids: set) -> list:
    return db.query(TeamGameStats).filter(TeamGameStats.game_id.in_(game_ids)).all()


def _pgs_for_player_games(db: Session, player_id: int, game_ids: set) -> list:
    return (
        db.query(PlayerGameStats)
        .filter(PlayerGameStats.player_id == player_id,
                PlayerGameStats.game_id.in_(game_ids))
        .all()
    )


@router.get("/team")
def team_stats(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    games = _filter_games(db, date_from, date_to)
    game_ids = {g.id for g in games}
    tgs_rows = _tgs_for_games(db, game_ids)
    result = aggregate_team_stats(tgs_rows, games)

    team_instat = load_team_instat_rows(db, date_from, date_to)
    result["special_teams_v2"] = special_teams_v2(team_instat)

    return result



@router.get("/player/{player_id}")
def player_stats(
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
    pgs_rows = _pgs_for_player_games(db, player_id, game_ids)
    agg = aggregate_player_stats(player, pgs_rows, games)

    # Build cohort baselines from all active players over the same window
    all_players = db.query(Player).filter_by(active=True).all()
    all_aggs = []
    for other in all_players:
        other_pgs = _pgs_for_player_games(db, other.id, game_ids)
        other_agg = aggregate_player_stats(other, other_pgs, games)
        all_aggs.append((other, other_agg))

    instat_rows = load_player_instat_rows(db, player_id, date_from, date_to)
    team_rows = load_team_instat_rows(db, date_from, date_to)
    position_cohorts = build_position_cohorts(all_players, db, date_from, date_to)
    shots_rows = load_player_shots_rows(db, player_id, date_from, date_to)

    return enrich_player_agg(
        player, agg, all_aggs,
        instat_rows=instat_rows,
        team_instat_rows=team_rows,
        pgs_rows=pgs_rows,
        position_cohorts=position_cohorts,
        shots_rows=shots_rows,
    )


@router.get("/players/all")
def all_player_stats(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    players = db.query(Player).filter_by(active=True).order_by(Player.name).all()
    games = _filter_games(db, date_from, date_to)
    game_ids = {g.id for g in games}
    result = []
    for p in players:
        pgs_rows = _pgs_for_player_games(db, p.id, game_ids)
        agg = aggregate_player_stats(p, pgs_rows, games)
        agg.pop("trend", None)
        result.append(agg)
    return result


def _row_to_dict(row) -> dict:
    d = {}
    for col in row.__table__.columns:
        v = getattr(row, col.name)
        d[col.name] = v.isoformat() if isinstance(v, date) else v
    return d


@router.get("/export")
def export_all(db: Session = Depends(get_db)):
    payload = {
        "exported_at": date.today().isoformat(),
        "players": [_row_to_dict(r) for r in db.query(Player).all()],
        "games": [_row_to_dict(r) for r in db.query(Game).order_by(Game.date).all()],
        "team_game_stats": [_row_to_dict(r) for r in db.query(TeamGameStats).all()],
        "player_game_stats": [_row_to_dict(r) for r in db.query(PlayerGameStats).all()],
    }
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="ecac_export_{date.today()}.json"'},
    )
