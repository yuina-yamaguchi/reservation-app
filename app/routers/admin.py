from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..seed_data import seed_defaults

router = APIRouter(prefix="/admin", tags=["管理"])


@router.post("/seed")
def seed(db: Session = Depends(get_db)):
    result = seed_defaults(db)
    created = result["cars_created"] + result["members_created"]
    message = (
        "初期データを投入しました"
        if created
        else "データが既に存在するためスキップしました"
    )
    return {**result, "message": message}
