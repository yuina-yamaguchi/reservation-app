from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from .. import models, pricing, schemas
from ..auth import require_admin, require_auth
from ..database import get_db

router = APIRouter(prefix="/emergency-alerts", tags=["緊急通報"])


def _to_response(alert: models.EmergencyAlert) -> dict:
    return {
        "id": alert.id,
        "reservation_id": alert.reservation_id,
        "reporter_user_id": alert.reporter_user_id,
        "reporter_name": alert.reporter.username if alert.reporter else None,
        "car_id": alert.car_id,
        "car_name": alert.car.name if alert.car else None,
        "message": alert.message,
        "status": alert.status,
        "resolved_at": alert.resolved_at,
        "created_at": alert.created_at,
    }


@router.post(
    "/",
    response_model=schemas.EmergencyAlertResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_alert(
    payload: schemas.EmergencyAlertCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    car = db.query(models.Car).filter(models.Car.id == payload.car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="車が見つかりません")

    alert = models.EmergencyAlert(
        reservation_id=payload.reservation_id,
        reporter_user_id=current_user.id,
        car_id=payload.car_id,
        message=payload.message,
        status="open",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # リレーションを読み込む
    alert = (
        db.query(models.EmergencyAlert)
        .options(
            joinedload(models.EmergencyAlert.reporter),
            joinedload(models.EmergencyAlert.car),
        )
        .filter(models.EmergencyAlert.id == alert.id)
        .first()
    )
    return _to_response(alert)


@router.get("/", response_model=list[schemas.EmergencyAlertResponse])
def list_alerts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    alerts = (
        db.query(models.EmergencyAlert)
        .options(
            joinedload(models.EmergencyAlert.reporter),
            joinedload(models.EmergencyAlert.car),
        )
        .order_by(models.EmergencyAlert.id.desc())
        .all()
    )
    return [_to_response(a) for a in alerts]


@router.post("/{alert_id}/resolve", response_model=schemas.EmergencyAlertResponse)
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    alert = (
        db.query(models.EmergencyAlert)
        .options(
            joinedload(models.EmergencyAlert.reporter),
            joinedload(models.EmergencyAlert.car),
        )
        .filter(models.EmergencyAlert.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="緊急通報が見つかりません")
    alert.status = "resolved"
    alert.resolved_at = pricing.now_jst()
    db.commit()
    db.refresh(alert)
    return _to_response(alert)
