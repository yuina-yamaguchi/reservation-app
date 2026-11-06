from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from . import models, pricing
from .auth import verify_password_hash
from .key_provider import get_provider

MASTER_KEY_MINUTES = 10
_MASTER_ADMIN_LIMIT = 10
_MASTER_CAR_LIMIT = 5
_MASTER_WINDOW_SECONDS = 600


class KeyServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


_master_attempts: dict[str, deque[float]] = defaultdict(deque)
_master_lock = threading.Lock()


def digital_key_enabled() -> bool:
    value = os.getenv("DIGITAL_KEY_ENABLED", "true")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def request_meta(request) -> tuple[str, str]:
    forwarded_for = request.headers.get("x-forwarded-for")
    ip = (
        forwarded_for.split(",")[0].strip()
        if forwarded_for
        else (request.client.host if request.client else "unknown")
    )
    return ip, request.headers.get("user-agent", "")[:500]


def _audit(
    db: Session,
    *,
    car_id: int,
    actor_user_id: int | None,
    digital_key_id: int | None,
    action: str,
    result: str,
    reason: str = "",
    ip: str = "",
    user_agent: str = "",
    detail: str = "",
) -> None:
    db.add(
        models.KeyAuditEvent(
            car_id=car_id,
            actor_user_id=actor_user_id,
            digital_key_id=digital_key_id,
            action=action,
            result=result,
            reason=reason,
            ip=ip,
            user_agent=user_agent,
            detail=detail[:2000],
        )
    )


def _reservation_snapshot(reservation: models.Reservation) -> str:
    return json.dumps(
        {
            "reservation_id": reservation.id,
            "car": reservation.car.name if reservation.car else None,
            "member": reservation.member.name if reservation.member else None,
            "start_time": reservation.start_time.isoformat(),
            "end_time": reservation.end_time.isoformat(),
            "note": reservation.note,
        },
        ensure_ascii=False,
    )


def _active_device(db: Session, car_id: int) -> models.KeyDevice | None:
    return (
        db.query(models.KeyDevice)
        .filter(
            models.KeyDevice.car_id == car_id,
            models.KeyDevice.status == "active",
        )
        .first()
    )


def _in_use(db: Session, car_id: int, now: datetime):
    return (
        db.query(models.Reservation)
        .filter(
            models.Reservation.car_id == car_id,
            models.Reservation.start_time <= now,
            models.Reservation.end_time > now,
        )
        .first()
    )


def _provider_issue(db: Session, key: models.DigitalKey, now: datetime) -> bool:
    if not key.recipient or not key.recipient.provider_recipient_id:
        key.status = "failed"
        key.last_error = "ベンダー受取人IDが未設定です"
        _audit(
            db,
            car_id=key.car_id,
            actor_user_id=key.recipient_user_id,
            digital_key_id=key.id,
            action="issue",
            result="failure",
            reason=key.reason,
            detail=key.last_error,
        )
        return False

    if not key.device:
        key.status = "failed"
        key.last_error = "キーボックスが登録されていません"
        _audit(
            db,
            car_id=key.car_id,
            actor_user_id=key.recipient_user_id,
            digital_key_id=key.id,
            action="issue",
            result="failure",
            reason=key.reason,
            detail=key.last_error,
        )
        return False

    provider = get_provider()
    try:
        result = provider.issue_key(
            device=key.device,
            recipient_id=key.recipient.provider_recipient_id,
            valid_from=key.valid_from,
            valid_to=key.valid_to,
            idempotency_key=f"digital-key-{key.id}",
            reason=key.reason,
        )
    except Exception as exc:  # noqa: BLE001 - プロバイダ依存の例外を保存する
        key.status = "failed"
        key.last_error = str(exc)[:1000]
        _audit(
            db,
            car_id=key.car_id,
            actor_user_id=key.recipient_user_id,
            digital_key_id=key.id,
            action="issue",
            result="failure",
            reason=key.reason,
            detail=key.last_error,
        )
        return False

    key.provider_key_id = result.get("provider_key_id")
    key.status = "issued"
    key.issued_at = now
    key.last_error = ""
    _audit(
        db,
        car_id=key.car_id,
        actor_user_id=key.recipient_user_id,
        digital_key_id=key.id,
        action="issue",
        result="success",
        reason=key.reason,
        detail=json.dumps(result, ensure_ascii=False, default=str)[:2000],
    )
    return True


def schedule_reservation_key(
    db: Session,
    reservation: models.Reservation,
    recipient: models.User | None,
    now: datetime | None = None,
    force: bool = False,
) -> models.DigitalKey | None:
    if not digital_key_enabled():
        return None
    now = now or pricing.now_jst()

    existing = (
        db.query(models.DigitalKey)
        .filter(
            models.DigitalKey.reservation_id == reservation.id,
            models.DigitalKey.purpose == "reservation",
        )
        .first()
    )
    if existing and not force:
        return existing

    device = _active_device(db, reservation.car_id)
    if not device:
        return None

    valid_from, valid_to = pricing.key_validity(
        reservation.start_time, reservation.end_time
    )
    issue_after = pricing.key_issue_after(reservation.start_time)

    key = models.DigitalKey(
        reservation_id=reservation.id,
        car_id=reservation.car_id,
        recipient_user_id=recipient.id if recipient else None,
        device_id=device.id,
        purpose="reservation",
        valid_from=valid_from,
        valid_to=valid_to,
        issue_after=issue_after,
        status="scheduled",
        reservation_snapshot=_reservation_snapshot(reservation),
    )
    db.add(key)
    db.flush()

    _audit(
        db,
        car_id=reservation.car_id,
        actor_user_id=recipient.id if recipient else None,
        digital_key_id=key.id,
        action="schedule",
        result="success",
        detail=f"issue_after={issue_after.isoformat()}",
    )

    if now >= issue_after:
        _provider_issue(db, key, now)

    return key


def issue_due(db: Session, now: datetime | None = None) -> dict[str, int]:
    now = now or pricing.now_jst()

    expired = (
        db.query(models.DigitalKey)
        .filter(
            models.DigitalKey.status.in_(["issued", "pending"]),
            models.DigitalKey.valid_to < now,
        )
        .all()
    )
    for key in expired:
        key.status = "expired"

    due = (
        db.query(models.DigitalKey)
        .filter(
            models.DigitalKey.status == "scheduled",
            models.DigitalKey.issue_after.isnot(None),
            models.DigitalKey.issue_after <= now,
        )
        .all()
    )
    issued = 0
    for key in due:
        if _provider_issue(db, key, now):
            issued += 1

    db.commit()
    return {"due": len(due), "issued": issued, "expired": len(expired)}


def revoke_reservation_keys(
    db: Session,
    reservation: models.Reservation,
    actor: models.User,
    request,
) -> None:
    ip, user_agent = request_meta(request)
    keys = (
        db.query(models.DigitalKey)
        .filter(
            models.DigitalKey.reservation_id == reservation.id,
            models.DigitalKey.purpose == "reservation",
            models.DigitalKey.status != "revoked",
        )
        .all()
    )
    provider = get_provider()
    for key in keys:
        if key.provider_key_id:
            try:
                provider.revoke_key(key.provider_key_id)
                key.status = "revoked"
                key.revoked_at = pricing.now_jst()
                _audit(
                    db,
                    car_id=key.car_id,
                    actor_user_id=actor.id,
                    digital_key_id=key.id,
                    action="revoke",
                    result="success",
                    reason=key.reason,
                    ip=ip,
                    user_agent=user_agent,
                )
            except Exception as exc:  # noqa: BLE001
                key.status = "revoke_failed"
                key.last_error = str(exc)[:1000]
                _audit(
                    db,
                    car_id=key.car_id,
                    actor_user_id=actor.id,
                    digital_key_id=key.id,
                    action="revoke",
                    result="failure",
                    reason=key.reason,
                    ip=ip,
                    user_agent=user_agent,
                    detail=key.last_error,
                )
        else:
            key.status = "revoked"
            key.revoked_at = pricing.now_jst()
        key.reservation_id = None


def revoke_key(
    db: Session,
    key: models.DigitalKey,
    actor: models.User,
    request,
) -> models.DigitalKey:
    ip, user_agent = request_meta(request)
    provider = get_provider()
    if key.provider_key_id:
        try:
            provider.revoke_key(key.provider_key_id)
            key.status = "revoked"
            key.revoked_at = pricing.now_jst()
            _audit(
                db,
                car_id=key.car_id,
                actor_user_id=actor.id,
                digital_key_id=key.id,
                action="revoke",
                result="success",
                reason=key.reason,
                ip=ip,
                user_agent=user_agent,
            )
        except Exception as exc:  # noqa: BLE001
            key.status = "revoke_failed"
            key.last_error = str(exc)[:1000]
            _audit(
                db,
                car_id=key.car_id,
                actor_user_id=actor.id,
                digital_key_id=key.id,
                action="revoke",
                result="failure",
                reason=key.reason,
                ip=ip,
                user_agent=user_agent,
                detail=key.last_error,
            )
    else:
        key.status = "revoked"
        key.revoked_at = pricing.now_jst()
        _audit(
            db,
            car_id=key.car_id,
            actor_user_id=actor.id,
            digital_key_id=key.id,
            action="revoke",
            result="success",
            reason=key.reason,
            ip=ip,
            user_agent=user_agent,
        )
    db.commit()
    db.refresh(key)
    return key


def reset_master_attempts() -> None:
    with _master_lock:
        _master_attempts.clear()


def _check_master_rate(admin_id: int, car_id: int) -> None:
    now = time.monotonic()
    checks = [(f"admin:{admin_id}", _MASTER_ADMIN_LIMIT), (f"car:{car_id}", _MASTER_CAR_LIMIT)]
    with _master_lock:
        for key, limit in checks:
            attempts = _master_attempts[key]
            while attempts and now - attempts[0] > _MASTER_WINDOW_SECONDS:
                attempts.popleft()
            if len(attempts) >= limit:
                raise KeyServiceError(
                    429, "マスターキーの発行回数が上限に達しました。しばらく待ってください。"
                )
        for key, _ in checks:
            _master_attempts[key].append(now)


def verify_admin_password(admin: models.User, password: str) -> None:
    if not verify_password_hash(password, admin.password_hash):
        raise KeyServiceError(403, "パスワードが正しくありません")


def _master_preflight(
    db: Session, admin: models.User, car_id: int, confirm_in_use: bool, now: datetime
) -> models.KeyDevice:
    if not digital_key_enabled():
        raise KeyServiceError(503, "デジタルキー機能は無効です")
    device = _active_device(db, car_id)
    if not device:
        raise KeyServiceError(409, "この車にはキーボックスが登録されていません")

    active = _in_use(db, car_id, now)
    if active and not confirm_in_use:
        raise KeyServiceError(
            409, "この車は現在利用中です。確認のうえ、もう一度実行してください。"
        )
    return device


def issue_master_key(
    db: Session,
    admin: models.User,
    car: models.Car,
    password: str,
    reason: str,
    confirm_in_use: bool,
    request,
    now: datetime | None = None,
) -> models.DigitalKey:
    now = now or pricing.now_jst()
    _check_master_rate(admin.id, car.id)
    verify_admin_password(admin, password)
    device = _master_preflight(db, admin, car.id, confirm_in_use, now)
    ip, user_agent = request_meta(request)
    active = _in_use(db, car.id, now)

    key = models.DigitalKey(
        reservation_id=None,
        car_id=car.id,
        recipient_user_id=admin.id,
        device_id=device.id,
        purpose="master",
        valid_from=now,
        valid_to=now + timedelta(minutes=MASTER_KEY_MINUTES),
        issue_after=now,
        status="pending",
        reason=reason,
        requested_ip=ip,
        requested_user_agent=user_agent,
        was_in_use=bool(active),
        reservation_snapshot="",
    )
    db.add(key)
    db.flush()
    _provider_issue(db, key, now)
    db.commit()
    db.refresh(key)
    return key


def remote_unlock(
    db: Session,
    admin: models.User,
    car: models.Car,
    password: str,
    reason: str,
    confirm_in_use: bool,
    request,
    now: datetime | None = None,
) -> dict:
    now = now or pricing.now_jst()
    _check_master_rate(admin.id, car.id)
    verify_admin_password(admin, password)
    device = _master_preflight(db, admin, car.id, confirm_in_use, now)
    ip, user_agent = request_meta(request)
    active = _in_use(db, car.id, now)

    provider = get_provider()
    try:
        result = provider.remote_unlock(device=device, actor_id=admin.id)
    except Exception as exc:  # noqa: BLE001
        _audit(
            db,
            car_id=car.id,
            actor_user_id=admin.id,
            digital_key_id=None,
            action="remote_unlock",
            result="failure",
            reason=reason,
            ip=ip,
            user_agent=user_agent,
            detail=str(exc),
        )
        db.commit()
        raise KeyServiceError(502, "遠隔解錠に失敗しました") from exc

    _audit(
        db,
        car_id=car.id,
        actor_user_id=admin.id,
        digital_key_id=None,
        action="remote_unlock",
        result="success",
        reason=reason,
        ip=ip,
        user_agent=user_agent,
        detail=json.dumps(result, ensure_ascii=False, default=str),
    )
    db.commit()
    return {"ok": True, "result": result, "was_in_use": bool(active)}
