from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Game, TeamGameStats, PlayerGameStats
from ..schemas import (
    GameCreate, GameUpdate, GameOut,
    TeamGameStatsCreate, TeamGameStatsOut,
    PlayerGameStatsCreate, PlayerGameStatsOut,
)

router = APIRouter(prefix="/api/games", tags=["games"])


@router.get("", response_model=list[GameOut])
def list_games(db: Session = Depends(get_db)):
    return db.query(Game).order_by(Game.date.desc()).all()


@router.post("", response_model=GameOut, status_code=201)
def create_game(body: GameCreate, db: Session = Depends(get_db)):
    game = Game(**body.model_dump())
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


@router.get("/{game_id}", response_model=GameOut)
def get_game(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    return game


@router.put("/{game_id}", response_model=GameOut)
def update_game(game_id: int, body: GameUpdate, db: Session = Depends(get_db)):
    game = db.query(Game).get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(game, field, val)
    db.commit()
    db.refresh(game)
    return game


@router.delete("/{game_id}", status_code=204)
def delete_game(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    db.delete(game)
    db.commit()


# ── Team Stats ────────────────────────────────────────────────────────────────

@router.get("/{game_id}/team-stats", response_model=TeamGameStatsOut)
def get_team_stats(game_id: int, db: Session = Depends(get_db)):
    tgs = db.query(TeamGameStats).filter_by(game_id=game_id).first()
    if not tgs:
        raise HTTPException(404, "Team stats not yet entered for this game")
    return tgs


@router.post("/{game_id}/team-stats", response_model=TeamGameStatsOut)
def upsert_team_stats(game_id: int, body: TeamGameStatsCreate, db: Session = Depends(get_db)):
    if not db.query(Game).get(game_id):
        raise HTTPException(404, "Game not found")
    tgs = db.query(TeamGameStats).filter_by(game_id=game_id).first()
    if tgs:
        for field, val in body.model_dump().items():
            setattr(tgs, field, val)
    else:
        tgs = TeamGameStats(game_id=game_id, **body.model_dump())
        db.add(tgs)
    db.commit()
    db.refresh(tgs)
    return tgs


# ── Player Stats ──────────────────────────────────────────────────────────────

@router.get("/{game_id}/players", response_model=list[PlayerGameStatsOut])
def get_all_player_stats(game_id: int, db: Session = Depends(get_db)):
    return db.query(PlayerGameStats).filter_by(game_id=game_id).all()


@router.get("/{game_id}/players/{player_id}", response_model=PlayerGameStatsOut)
def get_player_stats(game_id: int, player_id: int, db: Session = Depends(get_db)):
    row = db.query(PlayerGameStats).filter_by(game_id=game_id, player_id=player_id).first()
    if not row:
        raise HTTPException(404, "Player stats not found for this game")
    return row


@router.post("/{game_id}/players/{player_id}", response_model=PlayerGameStatsOut)
def upsert_player_stats(game_id: int, player_id: int, body: PlayerGameStatsCreate, db: Session = Depends(get_db)):
    if not db.query(Game).get(game_id):
        raise HTTPException(404, "Game not found")
    row = db.query(PlayerGameStats).filter_by(game_id=game_id, player_id=player_id).first()
    if row:
        for field, val in body.model_dump().items():
            setattr(row, field, val)
    else:
        row = PlayerGameStats(game_id=game_id, player_id=player_id, **body.model_dump())
        db.add(row)
    db.commit()
    db.refresh(row)
    return row
