from __future__ import annotations

import os

from .mock import MockKeyProvider


def get_provider():
    name = os.getenv("KEY_PROVIDER", "mock").strip().lower() or "mock"
    if name == "mock":
        return MockKeyProvider()
    # ベンダー実装は選定後に追加する。未実装の場合はモックで動作させる。
    return MockKeyProvider()
