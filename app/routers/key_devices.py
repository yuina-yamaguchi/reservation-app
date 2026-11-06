from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from .. import key_provider, models, pricing, schemas
from ..auth import require_admin, require_auth
from ..database import get_db

router = APIRouter(prefix="/key-devices", tags=["デジタルキー機器"])


def _to_response(device: models.KeyDevice) -> dict:
    return {
        "id": device.id,
        "car_id": device.car_id,
        "car_name": device.car.name if device.car else None,
        "provider": device.provider,
        "provider_device_id": device.provider_device_id,
        "display_name": device.display_name,
        "status": device.status,
        "last_synced_at": device.last_synced_at,
    }


@router.get("/", response_model=list[schemas.KeyDeviceResponse])
def list_devices(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_auth),
):
    devices = (
        db.query(models.KeyDevice)
        .options(joinedload(models.KeyDevice.car))
        .order_by(models.KeyDevice.id)
        .all()
    )
    return [_to_response(device) for device in devices]


@router.get("/cars/{car_id}", response_model=schemas.KeyDeviceResponse)
def get_car_device(
    car_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_auth),
):
    device = (
        db.query(models.KeyDevice)
        .options(joinedload(models.KeyDevice.car))
        .filter(models.KeyDevice.car_id == car_id)
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="キーボックスが登録されていません")
    return _to_response(device)


@router.post(
    "/", response_model=schemas.KeyDeviceResponse, status_code=status.HTTP_201_CREATED
)
def create_device(
    payload: schemas.KeyDeviceCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    car = db.query(models.Car).filter(models.Car.id == payload.car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="車が見つかりません")

    existing = (
        db.query(models.KeyDevice)
        .filter(models.KeyDevice.car_id == payload.car_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="この車には既にキーボックスが登録されています",
        )

    device = models.KeyDevice(**payload.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return _to_response(device)


@router.put("/{device_id}", response_model=schemas.KeyDeviceResponse)
def update_device(
    device_id: int,
    payload: schemas.KeyDeviceUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    device = (
        db.query(models.KeyDevice)
        .options(joinedload(models.KeyDevice.car))
        .filter(models.KeyDevice.id == device_id)
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="キーボックスが見つかりません")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, key, value)
    db.commit()
    db.refresh(device)
    return _to_response(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    device = db.query(models.KeyDevice).filter(models.KeyDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="キーボックスが見つかりません")

    has_keys = (
        db.query(models.DigitalKey.id)
        .filter(models.DigitalKey.device_id == device_id)
        .first()
    )
    if has_keys:
        device.status = "inactive"
    else:
        db.delete(device)
    db.commit()


@router.post("/{device_id}/sync", response_model=schemas.KeyDeviceResponse)
def sync_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    device = (
        db.query(models.KeyDevice)
        .options(joinedload(models.KeyDevice.car))
        .filter(models.KeyDevice.id == device_id)
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="キーボックスが見つかりません")

    provider = key_provider.get_provider()
    try:
        result = provider.get_device_status(device)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"キーボックスの状態を取得できません: {exc}",
        ) from exc

    device.last_synced_at = pricing.now_jst()
    device.metadata_json = str(result)
    db.commit()
    db.refresh(device)
    return _to_response(device)
