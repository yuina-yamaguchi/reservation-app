from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, joinedload

from .. import key_service, models, schemas
from ..auth import require_admin, require_auth
from ..database import get_db

router = APIRouter(prefix="/digital-keys", tags=["デジタルキー"])


def _handle_key_error(exc: key_service.KeyServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/me", response_model=list[schemas.DigitalKeyResponse])
def my_keys(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    return (
        db.query(models.DigitalKey)
        .filter(
            models.DigitalKey.recipient_user_id == current_user.id,
            models.DigitalKey.purpose == "reservation",
        )
        .order_by(models.DigitalKey.valid_from.desc())
        .all()
    )


@router.post("/issue-due")
def issue_due_keys(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    return key_service.issue_due(db)


@router.post("/backfill-reservation-keys")
def backfill_reservation_keys(
    include_past: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    return key_service.backfill_reservation_keys(db, include_past=include_past)


@router.get("/admin", response_model=list[schemas.DigitalKeyResponse])
def admin_keys(
    car_id: int | None = Query(default=None),
    purpose: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    query = db.query(models.DigitalKey)
    if car_id is not None:
        query = query.filter(models.DigitalKey.car_id == car_id)
    if purpose is not None:
        query = query.filter(models.DigitalKey.purpose == purpose)
    return query.order_by(models.DigitalKey.valid_from.desc()).limit(200).all()


@router.get("/audit", response_model=list[schemas.KeyAuditResponse])
def key_audit(
    car_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    query = (
        db.query(models.KeyAuditEvent)
        .options(joinedload(models.KeyAuditEvent.actor))
        .order_by(models.KeyAuditEvent.id.desc())
    )
    if car_id is not None:
        query = query.filter(models.KeyAuditEvent.car_id == car_id)
    events = query.limit(limit).all()
    return [
        {
            "id": event.id,
            "car_id": event.car_id,
            "actor_user_id": event.actor_user_id,
            "actor_name": event.actor.username if event.actor else None,
            "digital_key_id": event.digital_key_id,
            "action": event.action,
            "result": event.result,
            "reason": event.reason,
            "ip": event.ip,
            "user_agent": event.user_agent,
            "detail": event.detail,
            "created_at": event.created_at,
        }
        for event in events
    ]


@router.post(
    "/cars/{car_id}/master",
    response_model=schemas.DigitalKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
def issue_master_key(
    car_id: int,
    payload: schemas.MasterKeyRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    car = db.query(models.Car).filter(models.Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="車が見つかりません")
    try:
        return key_service.issue_master_key(
            db,
            current_user,
            car,
            payload.password,
            payload.reason,
            payload.confirm_in_use,
            request,
        )
    except key_service.KeyServiceError as exc:
        raise _handle_key_error(exc) from exc


@router.post("/cars/{car_id}/remote-unlock")
def remote_unlock(
    car_id: int,
    payload: schemas.RemoteUnlockRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    car = db.query(models.Car).filter(models.Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="車が見つかりません")
    try:
        return key_service.remote_unlock(
            db,
            current_user,
            car,
            payload.password,
            payload.reason,
            payload.confirm_in_use,
            request,
        )
    except key_service.KeyServiceError as exc:
        raise _handle_key_error(exc) from exc


@router.post("/{key_id}/revoke", response_model=schemas.DigitalKeyResponse)
def revoke_key(
    key_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    key = db.query(models.DigitalKey).filter(models.DigitalKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="デジタルキーが見つかりません")
    return key_service.revoke_key(db, key, current_user, request)
