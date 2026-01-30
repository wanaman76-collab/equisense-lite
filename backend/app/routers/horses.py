from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db, Base, engine
from ..models import Horse
from ..schemas import HorseCreate, HorseOut

router = APIRouter(prefix="/horses", tags=["horses"])
Base.metadata.create_all(bind=engine)

@router.post("", response_model=HorseOut)
def create_horse(payload: HorseCreate, db: Session = Depends(get_db)):
    h = Horse(name=payload.name, notes=payload.notes)
    db.add(h); db.commit(); db.refresh(h)
    return h

@router.get("", response_model=list[HorseOut])
def list_horses(db: Session = Depends(get_db)):
    q = db.execute(select(Horse).order_by(Horse.name.asc()))
    return [r[0] for r in q.all()]
