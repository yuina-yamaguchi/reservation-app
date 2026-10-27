from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/members", tags=["住人"])


@router.get("/", response_model=list[schemas.MemberResponse])
def list_members(db: Session = Depends(get_db)):
    return db.query(models.Member).order_by(models.Member.id).all()


@router.get("/{member_id}", response_model=schemas.MemberResponse)
def get_member(member_id: int, db: Session = Depends(get_db)):
    member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="住人が見つかりません")
    return member


@router.post(
    "/", response_model=schemas.MemberResponse, status_code=status.HTTP_201_CREATED
)
def create_member(member: schemas.MemberCreate, db: Session = Depends(get_db)):
    db_member = models.Member(**member.model_dump())
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return db_member


@router.put("/{member_id}", response_model=schemas.MemberResponse)
def update_member(
    member_id: int, member: schemas.MemberCreate, db: Session = Depends(get_db)
):
    db_member = (
        db.query(models.Member).filter(models.Member.id == member_id).first()
    )
    if not db_member:
        raise HTTPException(status_code=404, detail="住人が見つかりません")

    for key, value in member.model_dump().items():
        setattr(db_member, key, value)

    db.commit()
    db.refresh(db_member)
    return db_member


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(member_id: int, db: Session = Depends(get_db)):
    member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="住人が見つかりません")

    has_reservation = (
        db.query(models.Reservation.id)
        .filter(models.Reservation.member_id == member_id)
        .first()
    )
    if has_reservation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="この住人には予約があるため削除できません。先に予約をキャンセルしてください。",
        )

    db.delete(member)
    db.commit()
