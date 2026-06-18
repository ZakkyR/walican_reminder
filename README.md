# Walican Reminder

旅行・イベントの割り勘・立替精算を管理するWebアプリ。  
Discord OAuthでログインし、未払いメンバーへのリマインドをDiscord Botがチャンネルに通知します。

## 機能

- **Discord OAuth2 ログイン** — Discordアカウントでサインイン
- **仲間グループ管理** — よく一緒に旅行するメンバーをグループ登録
- **イベント管理** — 旅行・食事などのイベントを作成し、参加者を管理
- **支出管理** — 立替金額・参加者・カスタム負担額を記録
- **精算計算** — 最小送金数アルゴリズムで誰が誰にいくら払うかを自動計算
- **支払済みマーク** — 精算完了を記録、既払い分を保持したまま再計算
- **Discord通知設定** — 未払いメンバーへの通知をDiscord Botで送信（Azure Functions）

## 技術スタック

| レイヤー | 技術 |
|---|---|
| バックエンド | Python 3.12 / FastAPI 0.115 |
| テンプレート | Jinja2 3.1 |
| フロントエンド | HTMX 1.9.12 + Vanilla CSS |
| ORM | SQLAlchemy 2.x (sync) |
| DB（本番） | Azure SQL Database |
| DB（テスト） | SQLite |
| マイグレーション | Alembic |
| 認証 | Discord OAuth2 (authlib) |
| 通知スケジューラ | Azure Functions（別リポジトリ） |
| ホスティング | Azure App Service F1（無料） |

## ローカル開発セットアップ

### 前提条件

- Python 3.12+
- Discord Developer Portal でアプリを作成済み

### 手順

```bash
# 1. リポジトリをクローン
git clone https://github.com/ZakkyR/walican_reminder.git
cd walican_reminder

# 2. 仮想環境を作成・有効化
python -m venv .venv
# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

# 3. 依存関係をインストール
pip install -r requirements.txt

# 4. 環境変数を設定
cp .env.example .env
# .env を編集して各値を入力

# 5. DBマイグレーション（SQLiteで動作確認する場合）
DATABASE_URL=sqlite:///./dev.db alembic upgrade head

# 6. 起動
uvicorn app.main:app --reload
```

ブラウザで `http://localhost:8000` を開きます。

## 環境変数

`.env.example` をコピーして `.env` を作成し、以下を設定します。

| 変数名 | 説明 |
|---|---|
| `DATABASE_URL` | DB接続文字列（SQLite or Azure SQL） |
| `DISCORD_CLIENT_ID` | Discord OAuthアプリのクライアントID |
| `DISCORD_CLIENT_SECRET` | Discord OAuthアプリのクライアントシークレット |
| `DISCORD_BOT_TOKEN` | Discord BotトークN |
| `DISCORD_REDIRECT_URI` | OAuth2コールバックURL |
| `SESSION_SECRET` | セッション署名用シークレット（64文字以上のランダム文字列） |
| `FUNCTIONS_URL` | Azure FunctionsのベースURL（通知機能、任意） |
| `FUNCTIONS_KEY` | Azure FunctionsのアクセスキーN（通知機能、任意） |

`SESSION_SECRET` の生成例:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Discord Developer Portal 設定

1. [Discord Developer Portal](https://discord.com/developers/applications) でアプリを作成
2. **OAuth2 → Redirects** に以下を追加:
   - ローカル: `http://localhost:8000/auth/callback`
   - 本番: `https://<your-app>.azurewebsites.net/auth/callback`
3. **Bot** タブでBotを作成し、トークンを取得

## Azure App Service へのデプロイ

### 1. Azureリソースの作成

```bash
az group create --name walican-rg --location japaneast
az appservice plan create --name walican-plan --resource-group walican-rg --sku F1 --is-linux
az webapp create --name walican-reminder --resource-group walican-rg --plan walican-plan --runtime "PYTHON:3.12"
az webapp config set --name walican-reminder --resource-group walican-rg --startup-file "startup.sh"
```

### 2. Azure SQL Database の接続文字列を取得

Azure Portal → SQL Database → 接続文字列 → ODBC からコピーし、`mssql+pyodbc://` 形式に変換:

```
mssql+pyodbc://user:password@server.database.windows.net/dbname?driver=ODBC+Driver+18+for+SQL+Server
```

### 3. 環境変数の設定

```bash
az webapp config appsettings set --name walican-reminder --resource-group walican-rg --settings \
  DATABASE_URL="mssql+pyodbc://..." \
  DISCORD_CLIENT_ID="..." \
  DISCORD_CLIENT_SECRET="..." \
  DISCORD_BOT_TOKEN="..." \
  DISCORD_REDIRECT_URI="https://walican-reminder.azurewebsites.net/auth/callback" \
  SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

### 4. デプロイ

```bash
zip -r deploy.zip . -x "*.git*" "__pycache__/*" "*.db" ".env"
az webapp deployment source config-zip --name walican-reminder --resource-group walican-rg --src deploy.zip
```

## テスト

```bash
pytest tests/ -v
```

## ライセンス

MIT
