"""デプロイ済みアプリから部屋番号で登録された住人を削除するスクリプト。

予約がある住人は削除せず、スキップして表示します。
先に予約をキャンセルしてから再実行してください。

使い方:
  $env:APP_URL = "https://your-app.fastapicloud.dev"
  python remove_room_number_members_remote.py

または:
  python remove_room_number_members_remote.py https://your-app.fastapicloud.dev
"""

import getpass
import os
import sys
import time

import httpx

from app.schemas import ROOM_NUMBER_PATTERN

USER_AGENT = "reservation-app-cleanup/1.0"


def _request(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            return client.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    assert last_error is not None
    raise last_error


def main() -> None:
    base_url = os.getenv("APP_URL", "").strip()
    if not base_url and len(sys.argv) > 1:
        base_url = sys.argv[1].strip()

    if not base_url:
        print("APP_URL または第1引数にデプロイ先のURLを指定してください。")
        sys.exit(1)

    base_url = base_url.rstrip("/")
    password = os.getenv("APP_PASSWORD", "")
    if not password:
        password = getpass.getpass("APP_PASSWORD: ")

    transport = httpx.HTTPTransport(local_address="0.0.0.0", retries=5)
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        transport=transport,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        login = _request(
            client, "POST", "/api/auth/login", json={"password": password}
        )
        if login.status_code != 200:
            print(f"ログインに失敗しました（{login.status_code}）: {login.text}")
            sys.exit(1)

        response = _request(client, "GET", "/api/members/")
        if response.status_code != 200:
            print(f"住人一覧の取得に失敗しました（{response.status_code}）: {response.text}")
            sys.exit(1)

        targets = [
            member
            for member in response.json()
            if ROOM_NUMBER_PATTERN.fullmatch(member["name"])
        ]

        if not targets:
            print("部屋番号で登録された住人は見つかりませんでした。")
            return

        deleted = 0
        skipped = 0

        for member in targets:
            result = _request(client, "DELETE", f"/api/members/{member['id']}")
            if result.status_code == 204:
                print(f"削除: ID:{member['id']} {member['name']}")
                deleted += 1
            elif result.status_code == 409:
                print(f"スキップ: ID:{member['id']} {member['name']}（予約あり）")
                skipped += 1
            else:
                print(
                    "失敗: ID:{} {}（{}）: {}".format(
                        member["id"],
                        member["name"],
                        result.status_code,
                        result.text,
                    )
                )
                skipped += 1

        print(f"削除: {deleted}件 / スキップ: {skipped}件")


if __name__ == "__main__":
    main()
