from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, pricing, schemas, ticket_service
from ..auth import require_auth
from ..database import get_db

router = APIRouter(prefix="/tickets", tags=["6時間券"])


@router.get("/", response_model=list[schemas.TicketResponse])
@router.get("/me", response_model=list[schemas.TicketResponse])
def list_my_tickets(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    ticket_service.ensure_monthly_plan_charge(db, current_user)
    ticket_service.ensure_monthly_tickets(db, current_user)
    ticket_service.sweep_tickets(db)
    return (
        db.query(models.TimeTicket)
        .filter(models.TimeTicket.user_id == current_user.id)
        .order_by(
            models.TimeTicket.status,
            models.TimeTicket.expires_at,
            models.TimeTicket.id,
        )
        .all()
    )


@router.post(
    "/purchase",
    response_model=list[schemas.TicketResponse],
    status_code=status.HTTP_201_CREATED,
)
def purchase_tickets(
    payload: schemas.TicketGrant,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    if payload.source == "included":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="付与券は購入できません",
        )
    return ticket_service.grant_tickets(
        db, current_user, payload.source, payload.count
    )
