# 予約アプリ

学生マンションやシェアハウスなどで複数の車を共有するための、レスポンシブWeb＋PWAの予約管理アプリです。
住人は名字で登録します。部屋番号は個人情報保護のため登録できません。
ユーザー名とパスワードでログインし、管理者と利用者でできる操作を分けています。
スマートフォンのホーム画面に追加してアプリのように使えます。

## 本番環境

- URL: https://reservation-app.fastapicloud.dev
- ホスティング: FastAPI Cloud（アプリ名 `reservation-app`）
- データベース: Turso（DBスラッグ `reservation-app`）

## 機能

- ユーザー名＋パスワードログイン（署名付きCookie）
- 管理者と利用者の権限分離
- 管理者: 車・住人・ユーザーの管理、全予約の作成・キャンセル
- 利用者: 紐付いた住人としての予約、自分の予約のキャンセル
- 車の登録・編集・削除（管理者）
- 住人（名字）の登録・編集・削除（管理者）
- 車・利用者・日時を指定した予約
- 同じ車の時間帯重複を防止
- 月間カレンダーと選択日の予約詳細
- 予約一覧（過去）とキャンセル
- 予約完了後、予約日を選択したカレンダー表示へ自動遷移
- ホーム画面で各車の「使用中／空き」を表示
- モバイル・タブレット・PCに対応したレスポンシブUI
- PWA（ホーム画面追加・オフライン時は保存済みデータを表示）
- 予約がある車・住人は削除できない安全設計
- 住人に紐付くユーザーがいる場合も住人を削除できない安全設計

定期予約機能はありません。

## 権限

| 操作 | 管理者 | 利用者 |
|---|---|---|
| 車の登録・編集・削除 | ○ | × |
| 住人の登録・編集・削除 | ○ | × |
| ユーザーの登録・編集・削除 | ○ | × |
| 全員分の予約作成 | ○ | × |
| 自分の予約作成 | ○ | ○ |
| 全員分の予約キャンセル | ○ | × |
| 自分の予約キャンセル | ○ | ○ |
| 設定画面の表示 | ○ | × |

利用者は、管理画面で紐付けた住人としてのみ予約できます。予約時に別の住人IDを送信しても、
サーバー側でログイン中の利用者の住人IDに上書きされます。

## 技術構成

- Python 3.11+（FastAPI Cloudへのデプロイは3.12に固定）
- FastAPI / Pydantic / SQLAlchemy
- SQLite（ローカル）／Turso（本番）
- HTML / CSS / JavaScript（フレームワーク不使用）
- pytest（APIテスト）

## ファイル構成

```text
car-manager/
├── app/
│   ├── main.py            # FastAPIアプリ本体・静的配信
│   ├── config.py          # 環境変数
│   ├── database.py        # SQLite / Turso 接続
│   ├── models.py          # テーブル定義
│   ├── schemas.py         # リクエスト/レスポンス型
│   ├── auth.py            # パスワードハッシュ・署名Cookie・権限・試行制限
│   ├── bootstrap.py       # 初回管理者アカウント作成
│   ├── seed_data.py       # 初期データ定義
│   └── routers/
│       ├── auth.py
│       ├── admin.py       # 初期データ投入API
│       ├── cars.py
│       ├── members.py
│       ├── users.py       # ユーザー管理API（管理者のみ）
│       └── reservations.py
├── static/
│   ├── index.html
│   ├── app.css
│   ├── app.js
│   ├── manifest.json
│   ├── service-worker.js
│   └── icons/
├── tests/
├── seed.py                # ローカル用の初期データ投入
├── seed_remote.py         # デプロイ済みアプリへの初期データ投入
├── remove_room_number_members.py  # 部屋番号住人の削除（ローカル用）
├── remove_room_number_members_remote.py  # 部屋番号住人の削除（本番用）
├── generate_icons.py      # PWAアイコン生成（開発用）
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .python-version         # FastAPI Cloud用Python固定（3.12）
└── README.md
```

## ローカル起動

### 1. 仮想環境と依存パッケージ

```powershell
cd C:\Users\yxyam\my-opencode-samples\car-manager
python -m venv --system-site-packages .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

### 2. 環境変数

このワークスペースでは `.env` を作成済みです。別の場所にコピーした場合は
`.env.example` を `.env` にコピーして値を設定してください。

初回起動時、ユーザーが1人も登録されていなければ `.env` の
`ADMIN_USERNAME`（省略時 `admin`）と `APP_PASSWORD` で管理者アカウントを作成します。
以降のログインは、管理画面で作成したユーザー名とパスワードを使います。
初回セットアップ時は `.env.example` をコピーし、`APP_PASSWORD` と
`SESSION_SECRET` を必ず変更してください。
`SESSION_SECRET` はランダムな長い文字列にしてください。

### 3. 初期データ投入

```powershell
python seed.py
```

車3台（プリウス・ヴォクシー・フィット）と住人4人（名字）が登録されます。
既にデータがある場合はスキップされるため、再実行しても安全です。
既存のDBに住人が登録済みの場合は変更されないため、設定画面から編集してください。
部屋番号で登録済みの住人がいる場合は、次のスクリプトで削除できます。
予約がある住人はスキップされるため、先に予約をキャンセルしてから再実行してください。

```powershell
python remove_room_number_members.py
```

デプロイ済みアプリの場合は次を使います。パスワードは実行時に非表示で入力されます。

```powershell
$env:APP_URL = "https://reservation-app.fastapicloud.dev"
python remove_room_number_members_remote.py
Remove-Item Env:APP_URL
```

### 4. サーバー起動

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

ブラウザで `http://localhost:8000` を開き、管理者のユーザー名とパスワードを入力します。
初期管理者は `admin`（`ADMIN_USERNAME` で変更可）／`APP_PASSWORD` の値です。
ログイン後、設定画面から利用者ユーザーを作成し、住人を紐付けてください。
APIドキュメントは `http://localhost:8000/docs` です。

### 5. テスト

```powershell
python -m pytest -q
```

## スマートフォンから使う

1. PCとスマートフォンを同じWi-Fiに接続
2. PCのIPv4アドレスを確認（`ipconfig`）
3. スマートフォンで `http://<PCのIP>:8000` を開く
4. ブラウザのメニューから「ホーム画面に追加」

## API

すべて `/api` 配下です。ログインが必要なAPIは未認証の場合 `401` を返します。

| メソッド | パス | 権限 | 説明 |
|---|---|---|---|
| POST | `/api/auth/login` | 不要 | ログイン（`username` / `password`） |
| POST | `/api/auth/logout` | 不要 | ログアウト |
| GET | `/api/auth/me` | ログイン済み | ログイン中のユーザー情報 |
| GET | `/api/health` | 不要 | ヘルスチェック |
| POST | `/api/admin/seed` | 管理者 | 空のテーブルに初期データを投入 |
| GET | `/api/cars/` | ログイン済み | 車一覧 |
| POST | `/api/cars/` | 管理者 | 車を登録 |
| PUT | `/api/cars/{id}` | 管理者 | 車を更新 |
| DELETE | `/api/cars/{id}` | 管理者 | 車を削除（予約ありは409） |
| GET | `/api/members/` | ログイン済み | 住人一覧 |
| POST | `/api/members/` | 管理者 | 住人を登録（名字） |
| PUT | `/api/members/{id}` | 管理者 | 住人を更新 |
| DELETE | `/api/members/{id}` | 管理者 | 住人を削除（予約・ユーザー紐付きは409） |
| GET | `/api/users/` | 管理者 | ユーザー一覧 |
| POST | `/api/users/` | 管理者 | ユーザーを登録 |
| PUT | `/api/users/{id}` | 管理者 | ユーザーを更新 |
| DELETE | `/api/users/{id}` | 管理者 | ユーザーを削除 |
| GET | `/api/reservations/` | ログイン済み | 予約一覧（開始日時順） |
| GET | `/api/reservations/{id}` | ログイン済み | 予約詳細 |
| POST | `/api/reservations/` | ログイン済み | 予約作成（重複時409） |
| DELETE | `/api/reservations/{id}` | ログイン済み | 予約キャンセル（利用者は自分の予約のみ） |

利用者が予約を作成する場合、`member_id` はログイン中のユーザーに紐付く住人IDへ
サーバー側で上書きされます。利用者が他の住人の予約をキャンセルしようとすると `403` を返します。
最後の管理者は削除・降格できません。

## 環境変数

| 変数 | 必須 | 説明 |
|---|---|---|
| `APP_PASSWORD` | 本番必須 | 初回管理者アカウント作成用パスワード |
| `ADMIN_USERNAME` | 任意 | 初回管理者のユーザー名（既定 `admin`） |
| `SESSION_SECRET` | 本番必須 | Cookie署名用の秘密鍵 |
| `COOKIE_SECURE` | 本番で`true` | HTTPS時のみCookieを送る |
| `SESSION_MAX_AGE_SECONDS` | 任意 | セッション有効期間（既定30日） |
| `DATABASE_PATH` | 任意 | ローカルSQLiteのパス |
| `TURSO_DATABASE_URL` | 任意 | Tursoの接続URL |
| `TURSO_AUTH_TOKEN` | 任意 | Tursoの認証トークン |

`TURSO_DATABASE_URL` と `TURSO_AUTH_TOKEN` の両方を設定するとTursoに接続し、
どちらも未設定の場合はローカルSQLiteを使います。片方だけ設定した場合は
設定ミスを防ぐため起動時にエラーになります。

`sqlalchemy-libsql` はネイティブ拡張を必要とするため、`requirements.txt` では
Linux（FastAPI Cloudなどのデプロイ環境）に限定してインストールする指定にしています。
Windows/macOSのローカル開発ではSQLiteを使うためインストールされません。

## FastAPI Cloud + Turso へのデプロイ

### 0. デプロイ用Pythonの固定

このプロジェクトには `.python-version` があり、FastAPI CloudではPython 3.12を使用します。
FastAPI Cloudの既定Python 3.14では `libsql-experimental` のLinux用ホイールが提供されておらず、
Turso接続パッケージのインストールに失敗するためです。

### 1. TursoのDB作成

TursoのDB名は**小文字英数字とハイフンのみ**使用できます。
DBスラッグは `reservation-app` とします。

WindowsではTurso CLIが`winget`に無いため、Webダッシュボードから作成するのが簡単です。

1. Tursoのダッシュボードで `reservation-app` を作成
2. Database URL（`libsql://...`）をコピー
3. 書き込み可能なトークンを作成して安全な場所に保管

WSLのTurso CLIを使う場合：

```powershell
wsl
curl -sSfL https://get.tur.so/install.sh | bash
turso auth login
turso db create reservation-app
turso db show --url reservation-app
turso db tokens create reservation-app
```

### 2. FastAPI Cloudのアプリ作成とリンク

FastAPI CLIはこの環境ではPATHに無いため、`python -m fastapi` を使います。
WindowsのCP932コンソールで絵文字出力により失敗するのを防ぐため、UTF-8を設定します。

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
python -m fastapi login
python -m fastapi cloud apps create --name reservation-app --link
```

既存アプリをリンクする場合は次を使います。

```powershell
python -m fastapi cloud link
```

### 3. 環境変数の設定

`APP_PASSWORD` と `SESSION_SECRET` は必須です。`APP_PASSWORD` はユーザーが
1人もいない初回起動時に管理者アカウントを作るためだけに使われます。
環境変数を設定してから初回デプロイしてください。秘密値はダッシュボードから設定するか、
値なしでCLIを実行すると非表示入力になります。

```powershell
python -m fastapi cloud env set TURSO_DATABASE_URL "libsql://reservation-app-<your-org>.turso.io"
python -m fastapi cloud env set COOKIE_SECURE "true"
python -m fastapi cloud env set ADMIN_USERNAME "admin"

python -m fastapi cloud env set --secret TURSO_AUTH_TOKEN
python -m fastapi cloud env set --secret APP_PASSWORD
python -m fastapi cloud env set --secret SESSION_SECRET
```

初回起動時は `ADMIN_USERNAME`（既定 `admin`）と `APP_PASSWORD` で管理者アカウントが
自動作成されます。既にユーザーが存在する場合は作成されません。

`SESSION_SECRET` は次のコマンドで生成できます。

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 4. デプロイ

```powershell
python -m fastapi deploy
```

### 5. 初期データ投入

デプロイ済みアプリに投入する場合は、ログイン後に初期データ投入APIを呼び出す
`seed_remote.py` を使います。ユーザー名は `ADMIN_USERNAME`（既定 `admin`）、
パスワードは実行時に非表示で入力されます。

```powershell
$env:APP_URL = "https://<app>.fastapicloud.dev"
python seed_remote.py
Remove-Item Env:APP_URL
```

このAPIは認証が必要で、空のテーブルにだけ投入します。再実行しても重複しません。
Tursoの認証情報をローカルに置く必要はありません。

### 6. 動作確認

発行されたURL（例：`https://<app>.fastapicloud.dev`）を開き、ログインできることを確認します。
スマートフォンでは「ホーム画面に追加」でPWAとして利用できます。

ユーザー機能への更新後は旧形式のログインセッションが無効になるため、もう一度ログインしてください。

問題がある場合はログを確認します。

```powershell
python -m fastapi cloud logs --no-follow
```

## セキュリティ上の注意

- ユーザーごとにユーザー名・パスワード・権限・住人の紐付けを管理します。
- パスワードはPBKDF2-SHA256（260,000回）でハッシュ化して保存します。
- 初回管理者のパスワードは `APP_PASSWORD` です。初回ログイン後に管理画面から変更してください。
- 最後の管理者は削除・降格できません。自分自身も削除できません。
- `.env`、DBファイル、`.fastapicloud` はコミットしないでください。
- 本番では必ずHTTPSで運用し、`COOKIE_SECURE=true` を設定してください。
- `SESSION_SECRET` を変更すると、既存のログインセッションはすべて無効になります。
- ログイン試行は同一IPあたり5回／5分に制限しています（プロセス内の簡易制限）。

## データのリセット（ローカル）

```powershell
Remove-Item reservation_app.db
python seed.py
```

## Service Workerの更新

フロントエンドを更新した際は、`static/service-worker.js` の `CACHE_NAME` を
`reservation-app-v5` のように変更すると、古いキャッシュを確実に破棄できます。
