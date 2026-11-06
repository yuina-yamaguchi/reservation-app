from __future__ import annotations

import uuid
from typing import Any


class MockKeyProvider:
    """実機・ベンダーAPIがない環境で鍵の発行・失効を模擬する。"""

    def issue_key(
        self,
        *,
        device,
        recipient_id: str,
        valid_from,
        valid_to,
        idempotency_key: str,
        reason: str = "",
    ) -> dict[str, Any]:
        return {
            "provider_key_id": f"mock-{uuid.uuid4().hex}",
            "deep_link": f"mockkey://unlock/{device.provider_device_id}",
            "valid_from": valid_from.isoformat(),
            "valid_to": valid_to.isoformat(),
            "recipient_id": recipient_id,
        }

    def revoke_key(self, provider_key_id: str) -> None:
        return None

    def remote_unlock(self, *, device, actor_id: int) -> dict[str, Any]:
        return {
            "ok": True,
            "detail": f"mock remote unlock: {device.provider_device_id} by user {actor_id}",
        }

    def get_device_status(self, device) -> dict[str, Any]:
        return {
            "status": "active",
            "battery": 100,
            "provider_device_id": device.provider_device_id,
        }
