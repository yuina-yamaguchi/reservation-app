from __future__ import annotations

from typing import Any, Protocol


class KeyProvider(Protocol):
    def issue_key(
        self,
        *,
        device,
        recipient_id: str,
        valid_from,
        valid_to,
        idempotency_key: str,
        reason: str = "",
    ) -> dict[str, Any]: ...

    def revoke_key(self, provider_key_id: str) -> None: ...

    def remote_unlock(self, *, device, actor_id: int) -> dict[str, Any]: ...

    def get_device_status(self, device) -> dict[str, Any]: ...
