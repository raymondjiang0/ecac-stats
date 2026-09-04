"""Endpoints for InStat PDF ingest.

Flow: upload → parse → store IngestRun → review (frontend) → commit or discard.
"""
import os
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models import IngestRun, Game
from ..config import OUR_TEAM_NAME
from ..ingest.orchestrator import parse_all
from ..ingest.commit import commit_parsed


router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _upload_dir() -> str:
    d = os.environ.get(
        "INGEST_UPLOAD_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "ingest"),
    )
    os.makedirs(d, exist_ok=True)
    return d


@router.post("/upload")
def upload(
    file: UploadFile = File(...),
    game_id: int = Form(...),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter_by(id=game_id).one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    # Persist the file first (need the run_id to name it — two-phase)
    run = IngestRun(
        game_id=game_id,
        filename=file.filename or "unknown.pdf",
        parsed_json="{}",
        status="pending_review",
    )
    db.add(run)
    db.commit()

    try:
        dest = os.path.join(_upload_dir(), f"{run.id}.pdf")
        with open(dest, "wb") as f:
            f.write(file.file.read())
        parsed = parse_all(dest, OUR_TEAM_NAME)
    except Exception as e:
        run.status = "failed"
        run.error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Ingest failed: {e}")

    run.parsed_json = json.dumps(parsed)
    db.commit()

    return {
        "ingest_run_id": run.id,
        "warnings": parsed["warnings"],
        "preview": parsed["templates"],
    }


@router.get("/{ingest_run_id}")
def get_run(ingest_run_id: int, db: Session = Depends(get_db)):
    run = db.query(IngestRun).filter_by(id=ingest_run_id).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": run.id,
        "game_id": run.game_id,
        "filename": run.filename,
        "uploaded_at": run.uploaded_at.isoformat() if run.uploaded_at else None,
        "status": run.status,
        "parsed_json": json.loads(run.parsed_json) if run.parsed_json else {},
        "committed_at": run.committed_at.isoformat() if run.committed_at else None,
        "error": run.error,
    }


class CommitPayload(BaseModel):
    parsed_json: Optional[dict] = None  # edited-by-user override


@router.post("/{ingest_run_id}/commit")
def commit_run(
    ingest_run_id: int,
    payload: Optional[CommitPayload] = None,
    db: Session = Depends(get_db),
):
    run = db.query(IngestRun).filter_by(id=ingest_run_id).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Not found")
    if run.status != "pending_review":
        raise HTTPException(
            status_code=400,
            detail=f"Run is {run.status!r}, cannot commit",
        )

    parsed = (
        payload.parsed_json if (payload and payload.parsed_json is not None)
        else json.loads(run.parsed_json)
    )

    report = commit_parsed(parsed, run.game_id, db)

    run.status = "committed"
    run.committed_at = datetime.utcnow()
    run.parsed_json = json.dumps(parsed)  # persist the edited version
    db.commit()

    return report


@router.delete("/{ingest_run_id}")
def discard_run(ingest_run_id: int, db: Session = Depends(get_db)):
    run = db.query(IngestRun).filter_by(id=ingest_run_id).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Not found")
    if run.status == "committed":
        raise HTTPException(
            status_code=400,
            detail=f"Run {ingest_run_id} is already committed; cannot discard",
        )
    run.status = "discarded"
    db.commit()
    return {"status": "discarded"}
