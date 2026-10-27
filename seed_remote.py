"""デプロイ済みアプリに初期データを投入するスクリプト。

使い方:
  $env:APP_URL = "https://your-app.fastapicloud.dev"
  $env:APP_PASSWORD = "本番のパスワード"
  python seed_remote.py

または:
  python seed_remote.py https://your-app.fastapicloud.dev
"""

import getpass
import os
import sys
import time

import httpx

USER_AGENT = "reservation-app-seed/1.0"


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

        response = _request(client, "POST", "/api/admin/seed")
        if response.status_code != 200:
            print(f"投入に失敗しました（{response.status_code}）: {response.text}")
            sys.exit(1)

        data = response.json()
        print(data.get("message", "完了しました"))
        print(
            f"車: {data.get('cars_created', 0)}件 / "
            f"住人: {data.get('members_created', 0)}件 を追加しました。"
        )


if __name__ == "__main__":
    main()
