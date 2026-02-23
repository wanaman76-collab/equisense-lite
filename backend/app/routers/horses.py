from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..db import get_db, Base, engine
from ..models import Horse
from ..schemas import HorseCreate, HorseOut

router = APIRouter(prefix="/horses", tags=["horses"])
Base.metadata.create_all(bind=engine)

@router.post("", response_model=HorseOut, status_code=201)
def create_horse(payload: HorseCreate, db: Session = Depends(get_db)):
    h = Horse(name=payload.name, notes=payload.notes)
    db.add(h)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Horse with name '{payload.name}' already exists")
    db.refresh(h)
    return h

@router.get("", response_model=list[HorseOut])
def list_horses(db: Session = Depends(get_db)):
    q = db.execute(select(Horse).order_by(Horse.name.asc()))
    return [r[0] for r in q.all()]
