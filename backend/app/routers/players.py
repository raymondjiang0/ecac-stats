from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Player
from ..schemas import PlayerCreate, PlayerUpdate, PlayerOut

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("", response_model=list[PlayerOut])
def list_players(db: Session = Depends(get_db)):
    return db.query(Player).order_by(Player.name).all()


@router.post("", response_model=PlayerOut, status_code=201)
def create_player(body: PlayerCreate, db: Session = Depends(get_db)):
    player = Player(**body.model_dump())
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@router.put("/{player_id}", response_model=PlayerOut)
def update_player(player_id: int, body: PlayerUpdate, db: Session = Depends(get_db)):
    player = db.query(Player).get(player_id)
    if not player:
        raise HTTPException(404, "Player not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(player, field, val)
    db.commit()
    db.refresh(player)
    return player


@router.delete("/{player_id}", status_code=204)
def delete_player(player_id: int, db: Session = Depends(get_db)):
    player = db.query(Player).get(player_id)
    if not player:
        raise HTTPException(404, "Player not found")
    db.delete(player)
    db.commit()
