# Walican Reminder — Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FastAPI + HTMX の割り勘精算 Web アプリを構築する（Discord OAuth 認証、仲間グループ管理、イベント・支出・精算管理）。

**Architecture:** FastAPI が Jinja2 テンプレートを返し、HTMX で部分更新する。SQLAlchemy 2.x（sync）が Azure SQL（本番）と SQLite（テスト）両方に接続。Discord OAuth2 は authlib + Starlette SessionMiddleware で処理。

**Tech Stack:** Python 3.12, FastAPI 0.115+, SQLAlchemy 2.x (sync), Jinja2, HTMX 1.9, authlib, pyodbc, alembic, pytest

## Global Constraints

- Python 3.12+、FastAPI 0.115+、SQLAlchemy 2.x（sync のみ、asyncio 不使用）
- 本番: Azure SQL（`mssql+pyodbc://`）、テスト: SQLite（`sqlite:///./test.db`）
- 金額はすべて `DECIMAL(12,0)`（整数円、小数なし）
- シークレットは環境変数のみ（コードに直書き禁止）
- セッションは Starlette SessionMiddleware（署名済み Cookie）
- HTMX リクエスト（`HX-Request: true`）には HTML フラグメントのみ返す（`<html>` タグ不要）
- 認証必須ルート: `/login`、`/auth/callback`、`/logout` 以外はすべてログイン必須

---

## ファイル構成

```
app/
  __init__.py
  main.py              FastAPI インスタンス、ミドルウェア、ルーター登録
  config.py            pydantic-settings による環境変数
  database.py          SQLAlchemy engine / SessionLocal / Base / get_db
  models/
    __init__.py        全モデルを re-export（Alembic 検出用）
    user.py            User
    friend_group.py    FriendGroup, FriendGroupMember
    event.py           Event, EventParticipant
    expense.py         Expense, ExpenseParticipant
    payment.py         Payment
    notification.py    NotificationSetting
  routers/
    __init__.py
    auth.py            /login, /auth/callback, /logout
    home.py            /（イベント一覧）
    groups.py          /groups/*
    events.py          /events/*
    expenses.py        /events/{id}/expenses/*
    payments.py        /events/{id}/payments/*
    notifications.py   /events/{id}/notification
  services/
    __init__.py
    settlement.py      calculate_settlement(), apply_settlement()
  templates/
    base.html
    login.html
    home.html
    groups/
      list.html
      detail.html
      partials/member_row.html
    events/
      new.html
      detail.html
      partials/
        expenses_tab.html
        payments_tab.html
        notification_tab.html
        expense_row.html
        payment_row.html
  static/
    style.css
tests/
  conftest.py
  test_settlement.py
  test_groups.py
  test_events.py
  test_expenses.py
  test_payments.py
alembic/
  env.py
  versions/
    0001_initial.py
requirements.txt
.env.example
alembic.ini
startup.sh
```

---

### Task 1: プロジェクトスキャフォールド

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `app/__init__.py`, `app/main.py`, `app/config.py`, `app/database.py`
- Create: `startup.sh`

**Interfaces:**
- Produces: `get_db()` → `Generator[Session, None, None]`、`settings` オブジェクト（全タスクで使用）

- [ ] **Step 1: `requirements.txt` を作成**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.36
alembic==1.13.2
jinja2==3.1.4
python-multipart==0.0.12
authlib==1.3.2
httpx==0.27.2
pydantic-settings==2.5.2
itsdangerous==2.2.0
pyodbc==5.2.0
pytest==8.3.3
pytest-mock==3.14.0
```

- [ ] **Step 2: `.env.example` を作成**

```
DATABASE_URL=mssql+pyodbc://user:password@server.database.windows.net/dbname?driver=ODBC+Driver+18+for+SQL+Server
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_REDIRECT_URI=http://localhost:8000/auth/callback
SESSION_SECRET=change-me-to-random-64-chars
FUNCTIONS_URL=
FUNCTIONS_KEY=
```

- [ ] **Step 3: `app/config.py` を作成**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    discord_client_id: str
    discord_client_secret: str
    discord_bot_token: str
    discord_redirect_uri: str
    session_secret: str
    functions_url: str = ""
    functions_key: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 4: `app/database.py` を作成**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from typing import Generator
from app.config import settings

engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 5: `app/main.py` を作成**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.config import settings

app = FastAPI(title="Walican Reminder")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
```

- [ ] **Step 6: `app/__init__.py`、`app/models/__init__.py`、`app/routers/__init__.py`、`app/services/__init__.py` を空ファイルで作成**

```bash
mkdir -p app/models app/routers app/services app/templates/groups/partials app/templates/events/partials app/static tests alembic/versions
touch app/__init__.py app/models/__init__.py app/routers/__init__.py app/services/__init__.py
```

- [ ] **Step 7: `startup.sh` を作成**

```bash
#!/bin/bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 8: pip install して起動確認**

```bash
cp .env.example .env  # 値は後で設定
pip install -r requirements.txt
uvicorn app.main:app --reload
```

期待出力: `Uvicorn running on http://127.0.0.1:8000`

- [ ] **Step 9: git init してコミット**

```bash
git init
echo ".env" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
echo "test.db" >> .gitignore
git add .
git commit -m "feat: project scaffold"
```

---

### Task 2: データベースモデル

**Files:**
- Create: `app/models/user.py`, `app/models/friend_group.py`, `app/models/event.py`
- Create: `app/models/expense.py`, `app/models/payment.py`, `app/models/notification.py`
- Modify: `app/models/__init__.py`

**Interfaces:**
- Produces: `User`, `FriendGroup`, `FriendGroupMember`, `Event`, `EventParticipant`, `Expense`, `ExpenseParticipant`, `Payment`, `NotificationSetting` クラス

- [ ] **Step 1: `app/models/user.py` を作成**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    discord_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    discord_username: Mapped[str] = mapped_column(String(100))
    discord_avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: `app/models/friend_group.py` を作成**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class FriendGroup(Base):
    __tablename__ = "friend_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    members: Mapped[list["FriendGroupMember"]] = relationship("FriendGroupMember", back_populates="group", cascade="all, delete-orphan")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])

class FriendGroupMember(Base):
    __tablename__ = "friend_group_members"

    friend_group_id: Mapped[str] = mapped_column(String(36), ForeignKey("friend_groups.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)

    group: Mapped["FriendGroup"] = relationship("FriendGroup", back_populates="members")
    user: Mapped["User"] = relationship("User")
```

- [ ] **Step 3: `app/models/event.py` を作成**

```python
import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum

class EventStatus(str, enum.Enum):
    active = "active"
    completed = "completed"

class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    payment_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus), default=EventStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    participants: Mapped[list["EventParticipant"]] = relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="event", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="event", cascade="all, delete-orphan")

class EventParticipant(Base):
    __tablename__ = "event_participants"

    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)

    event: Mapped["Event"] = relationship("Event", back_populates="participants")
    user: Mapped["User"] = relationship("User")
```

- [ ] **Step 4: `app/models/expense.py` を作成**

```python
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"))
    title: Mapped[str] = mapped_column(String(200))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 0))
    paid_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    event: Mapped["Event"] = relationship("Event", back_populates="expenses")
    payer: Mapped["User"] = relationship("User", foreign_keys=[paid_by])
    participants: Mapped[list["ExpenseParticipant"]] = relationship("ExpenseParticipant", back_populates="expense", cascade="all, delete-orphan")

class ExpenseParticipant(Base):
    __tablename__ = "expense_participants"

    expense_id: Mapped[str] = mapped_column(String(36), ForeignKey("expenses.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    custom_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 0), nullable=True)

    expense: Mapped["Expense"] = relationship("Expense", back_populates="participants")
    user: Mapped["User"] = relationship("User")
```

- [ ] **Step 5: `app/models/payment.py` を作成**

```python
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, ForeignKey, Numeric, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum

class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"))
    from_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    to_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 0))
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.pending)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    event: Mapped["Event"] = relationship("Event", back_populates="payments")
    from_user: Mapped["User"] = relationship("User", foreign_keys=[from_user_id])
    to_user: Mapped["User"] = relationship("User", foreign_keys=[to_user_id])
```

- [ ] **Step 6: `app/models/notification.py` を作成**

```python
import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, ForeignKey, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum

class NotificationMode(str, enum.Enum):
    scheduled = "scheduled"
    deadline = "deadline"
    from_date = "from_date"

class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), unique=True)
    discord_channel_id: Mapped[str] = mapped_column(String(20))
    mode: Mapped[NotificationMode] = mapped_column(Enum(NotificationMode))
    schedule_cron: Mapped[str | None] = mapped_column(String(50), nullable=True)
    deadline_days_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadline_days_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notify_from_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notify_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    event: Mapped["Event"] = relationship("Event")
```

- [ ] **Step 7: `app/models/__init__.py` で全モデルを re-export（Alembic 検出用）**

```python
from app.models.user import User
from app.models.friend_group import FriendGroup, FriendGroupMember
from app.models.event import Event, EventParticipant, EventStatus
from app.models.expense import Expense, ExpenseParticipant
from app.models.payment import Payment, PaymentStatus
from app.models.notification import NotificationSetting, NotificationMode

__all__ = [
    "User", "FriendGroup", "FriendGroupMember",
    "Event", "EventParticipant", "EventStatus",
    "Expense", "ExpenseParticipant",
    "Payment", "PaymentStatus",
    "NotificationSetting", "NotificationMode",
]
```

- [ ] **Step 8: コミット**

```bash
git add app/models/
git commit -m "feat: add SQLAlchemy models"
```

---

### Task 3: Alembic マイグレーション

**Files:**
- Create: `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_initial.py`

**Interfaces:**
- Produces: DB スキーマ（テスト・本番共通）

- [ ] **Step 1: Alembic 初期化**

```bash
alembic init alembic
```

- [ ] **Step 2: `alembic.ini` の `sqlalchemy.url` 行をコメントアウト**

`alembic.ini` の以下の行を:
```
sqlalchemy.url = driver://user:pass@localhost/dbname
```
これに変更:
```
# sqlalchemy.url は alembic/env.py で設定
```

- [ ] **Step 3: `alembic/env.py` を上書き**

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.config import settings
from app.database import Base
import app.models  # noqa: F401 — モデルを Base に登録させる

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: 初期マイグレーションを自動生成**

```bash
alembic revision --autogenerate -m "initial"
```

期待出力: `Generating alembic/versions/xxxx_initial.py`

- [ ] **Step 5: `tests/conftest.py` を作成（SQLite でテスト DB を構築）**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.models.user import User

TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def user(db):
    u = User(discord_id="123456789", discord_username="TestUser")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

@pytest.fixture
def auth_client(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
    return client
```

- [ ] **Step 6: pytest が通ることを確認**

```bash
pytest tests/ -v
```

期待出力: `no tests ran` または `0 passed` — エラーなし

- [ ] **Step 7: コミット**

```bash
git add alembic/ alembic.ini tests/conftest.py
git commit -m "feat: alembic migrations and test setup"
```

---

### Task 4: Discord OAuth 認証

**Files:**
- Create: `app/routers/auth.py`
- Create: `app/templates/login.html`
- Modify: `app/main.py`

**Interfaces:**
- Produces: `get_current_user(request, db) → User`（全ルーターで使用）、`/login`、`/auth/callback`、`/logout`

- [ ] **Step 1: `tests/test_auth.py` の失敗テストを書く**

```python
def test_login_redirects_to_discord(client):
    response = client.get("/login", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "discord.com" in response.headers["location"]

def test_logout_clears_session(auth_client):
    response = auth_client.get("/logout", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/"

def test_protected_route_redirects_when_not_logged_in(client):
    response = client.get("/groups", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/login" in response.headers["location"]
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/test_auth.py -v
```

期待出力: `FAILED` — ルートが存在しない

- [ ] **Step 3: `app/routers/auth.py` を作成**

```python
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from app.config import settings
from app.database import get_db
from app.models.user import User

router = APIRouter()

oauth = OAuth()
oauth.register(
    name="discord",
    client_id=settings.discord_client_id,
    client_secret=settings.discord_client_secret,
    authorize_url="https://discord.com/api/oauth2/authorize",
    access_token_url="https://discord.com/api/oauth2/token",
    api_base_url="https://discord.com/api/v10/",
    client_kwargs={"scope": "identify"},
)

@router.get("/login")
async def login(request: Request):
    return await oauth.discord.authorize_redirect(request, settings.discord_redirect_uri)

@router.get("/auth/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.discord.authorize_access_token(request)
    discord_user = await oauth.discord.get("users/@me", token=token)
    data = discord_user.json()

    user = db.query(User).filter(User.discord_id == data["id"]).first()
    if not user:
        user = User(
            discord_id=data["id"],
            discord_username=data["username"],
            discord_avatar_url=f"https://cdn.discordapp.com/avatars/{data['id']}/{data.get('avatar')}.png" if data.get("avatar") else None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.discord_username = data["username"]
        db.commit()

    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=302)

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=302, headers={"location": "/login"})
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=302, headers={"location": "/login"})
    return user
```

- [ ] **Step 4: `app/main.py` にルーターを登録**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.config import settings
from app.routers import auth

app = FastAPI(title="Walican Reminder")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth.router)
```

- [ ] **Step 5: `app/templates/login.html` を作成**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ログイン — Walican Reminder</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div class="login-page">
    <h1>🧾 Walican Reminder</h1>
    <p>旅行・イベントの割り勘を管理するアプリです</p>
    <a href="/login" class="btn btn-discord">Discord でログイン</a>
  </div>
</body>
</html>
```

- [ ] **Step 6: テストを実行（`/login` と `/logout` のテストが通ること）**

```bash
pytest tests/test_auth.py::test_logout_clears_session tests/test_auth.py::test_protected_route_redirects_when_not_logged_in -v
```

期待出力: `PASSED`（`/login` の Discord リダイレクトは mock なしでは失敗するためスキップ）

- [ ] **Step 7: コミット**

```bash
git add app/routers/auth.py app/templates/login.html app/main.py
git commit -m "feat: Discord OAuth authentication"
```

---

### Task 5: 精算計算サービス（TDD）

**Files:**
- Create: `app/services/settlement.py`
- Create: `tests/test_settlement.py`

**Interfaces:**
- Produces:
  - `calculate_settlement(expenses: list[ExpenseInput]) -> list[tuple[str, str, Decimal]]`
  - `ExpenseInput(paid_by: str, total_amount: Decimal, participants: list[ParticipantInput])`
  - `ParticipantInput(user_id: str, custom_amount: Decimal | None)`
  - 返り値: `[(from_user_id, to_user_id, amount), ...]`

- [ ] **Step 1: `tests/test_settlement.py` の失敗テストを書く**

```python
from decimal import Decimal
from app.services.settlement import calculate_settlement, ExpenseInput, ParticipantInput

def test_equal_split_two_people():
    # A が 10000 円立替、A と B で均等割り → B が A に 5000 円
    expenses = [ExpenseInput(
        paid_by="A",
        total_amount=Decimal(10000),
        participants=[
            ParticipantInput(user_id="A", custom_amount=None),
            ParticipantInput(user_id="B", custom_amount=None),
        ]
    )]
    result = calculate_settlement(expenses)
    assert result == [("B", "A", Decimal(5000))]

def test_custom_amount():
    # A が 10000 円立替、A は 3000 円、B は 7000 円カスタム
    expenses = [ExpenseInput(
        paid_by="A",
        total_amount=Decimal(10000),
        participants=[
            ParticipantInput(user_id="A", custom_amount=Decimal(3000)),
            ParticipantInput(user_id="B", custom_amount=Decimal(7000)),
        ]
    )]
    result = calculate_settlement(expenses)
    assert result == [("B", "A", Decimal(7000))]

def test_mixed_split():
    # A が 9000 円立替、A はカスタム 3000 円、B と C は均等（各 3000 円）
    expenses = [ExpenseInput(
        paid_by="A",
        total_amount=Decimal(9000),
        participants=[
            ParticipantInput(user_id="A", custom_amount=Decimal(3000)),
            ParticipantInput(user_id="B", custom_amount=None),
            ParticipantInput(user_id="C", custom_amount=None),
        ]
    )]
    result = calculate_settlement(expenses)
    assert len(result) == 2
    assert ("B", "A", Decimal(3000)) in result
    assert ("C", "A", Decimal(3000)) in result

def test_multiple_expenses_minimize_transactions():
    # A が 6000 円立替（A,B,C 均等 2000 ずつ）
    # B が 3000 円立替（A,B 均等 1500 ずつ）
    # 最終: A が B に 500 円、C が A に 2000 円
    expenses = [
        ExpenseInput(
            paid_by="A",
            total_amount=Decimal(6000),
            participants=[
                ParticipantInput(user_id="A", custom_amount=None),
                ParticipantInput(user_id="B", custom_amount=None),
                ParticipantInput(user_id="C", custom_amount=None),
            ]
        ),
        ExpenseInput(
            paid_by="B",
            total_amount=Decimal(3000),
            participants=[
                ParticipantInput(user_id="A", custom_amount=None),
                ParticipantInput(user_id="B", custom_amount=None),
            ]
        ),
    ]
    result = calculate_settlement(expenses)
    # A: +6000-2000-1500 = +2500（受け取り側）
    # B: +3000-2000-1500 = -500（支払い側）
    # C: -2000（支払い側）
    # B が A に 500、C が A に 2000
    assert len(result) == 2
    assert ("B", "A", Decimal(500)) in result
    assert ("C", "A", Decimal(2000)) in result

def test_no_expenses_returns_empty():
    assert calculate_settlement([]) == []

def test_single_payer_excluded_from_participants():
    # A が 1000 円立替、参加者は B のみ → A は負担なし、B が 1000 円支払い
    expenses = [ExpenseInput(
        paid_by="A",
        total_amount=Decimal(1000),
        participants=[ParticipantInput(user_id="B", custom_amount=None)],
    )]
    result = calculate_settlement(expenses)
    assert result == [("B", "A", Decimal(1000))]
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/test_settlement.py -v
```

期待出力: `ImportError` または `FAILED` — `settlement.py` が存在しない

- [ ] **Step 3: `app/services/settlement.py` を作成**

```python
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

@dataclass
class ParticipantInput:
    user_id: str
    custom_amount: Decimal | None

@dataclass
class ExpenseInput:
    paid_by: str
    total_amount: Decimal
    participants: list[ParticipantInput]

def _round(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

def calculate_settlement(expenses: list[ExpenseInput]) -> list[tuple[str, str, Decimal]]:
    balances: dict[str, Decimal] = {}

    for expense in expenses:
        custom = [(p.user_id, p.custom_amount) for p in expense.participants if p.custom_amount is not None]
        equal_users = [p.user_id for p in expense.participants if p.custom_amount is None]

        custom_total = sum(amt for _, amt in custom)
        equal_share = _round((expense.total_amount - custom_total) / len(equal_users)) if equal_users else Decimal(0)

        balances[expense.paid_by] = balances.get(expense.paid_by, Decimal(0)) + expense.total_amount

        for uid, amt in custom:
            balances[uid] = balances.get(uid, Decimal(0)) - amt
        for uid in equal_users:
            balances[uid] = balances.get(uid, Decimal(0)) - equal_share

    creditors = sorted([(uid, bal) for uid, bal in balances.items() if bal > 0], key=lambda x: x[1])
    debtors = sorted([(uid, -bal) for uid, bal in balances.items() if bal < 0], key=lambda x: x[1])

    payments = []
    while creditors and debtors:
        cred_id, cred_amt = creditors.pop()
        debt_id, debt_amt = debtors.pop()
        amount = min(cred_amt, debt_amt)
        payments.append((debt_id, cred_id, amount))
        if cred_amt > debt_amt:
            creditors.append((cred_id, cred_amt - debt_amt))
            creditors.sort(key=lambda x: x[1])
        elif debt_amt > cred_amt:
            debtors.append((debt_id, debt_amt - cred_amt))
            debtors.sort(key=lambda x: x[1])

    return payments
```

- [ ] **Step 4: テストを実行して全件パスを確認**

```bash
pytest tests/test_settlement.py -v
```

期待出力: `6 passed`

- [ ] **Step 5: コミット**

```bash
git add app/services/settlement.py tests/test_settlement.py
git commit -m "feat: settlement calculation service (TDD)"
```

---

### Task 6: ベーステンプレートとホーム画面

**Files:**
- Create: `app/templates/base.html`, `app/templates/home.html`
- Create: `app/static/style.css`
- Create: `app/routers/home.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `get_current_user`（Task 4）
- Produces: `GET /` → イベント一覧カード表示

- [ ] **Step 1: `app/templates/base.html` を作成**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Walican Reminder{% endblock %}</title>
  <script src="https://unpkg.com/htmx.org@1.9.12" defer></script>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <nav class="nav">
    <a href="/" class="nav-brand">🧾 Walican Reminder</a>
    <div class="nav-links">
      <a href="/groups">仲間グループ</a>
      <span class="nav-user">{{ user.discord_username }}</span>
      <a href="/logout">ログアウト</a>
    </div>
  </nav>
  <main class="container">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: `app/static/style.css` を作成（最小限のレスポンシブ CSS）**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f7fa; color: #333; }
.nav { background: #fff; border-bottom: 1px solid #e0e0e0; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; }
.nav-brand { font-weight: bold; font-size: 1.1rem; text-decoration: none; color: #333; }
.nav-links { display: flex; gap: 16px; align-items: center; }
.nav-links a { text-decoration: none; color: #555; }
.container { max-width: 800px; margin: 0 auto; padding: 20px; }
.card { background: #fff; border-radius: 10px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
.card-title { font-size: 1rem; font-weight: 600; margin-bottom: 4px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }
.badge-danger { background: #fff0f0; color: #d32f2f; }
.badge-success { background: #f0fff4; color: #2e7d32; }
.btn { display: inline-block; padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer; font-size: 0.9rem; text-decoration: none; }
.btn-primary { background: #5865f2; color: #fff; }
.btn-discord { background: #5865f2; color: #fff; padding: 12px 24px; font-size: 1rem; }
.btn-danger { background: #d32f2f; color: #fff; }
.btn-secondary { background: #e0e0e0; color: #333; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 4px; font-size: 0.875rem; font-weight: 500; }
.form-group input, .form-group select, .form-group textarea { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 0.9rem; }
.tabs { display: flex; border-bottom: 2px solid #e0e0e0; margin-bottom: 20px; }
.tab { padding: 8px 16px; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab.active { border-bottom-color: #5865f2; color: #5865f2; font-weight: 600; }
.login-page { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; gap: 16px; text-align: center; }
.text-danger { color: #d32f2f; }
.text-success { color: #2e7d32; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
```

- [ ] **Step 3: `app/routers/home.py` を作成**

```python
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.payment import Payment, PaymentStatus

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.event import EventParticipant
    participated = db.query(Event).join(EventParticipant, EventParticipant.event_id == Event.id).filter(
        EventParticipant.user_id == user.id
    ).order_by(Event.created_at.desc()).all()

    events_with_stats = []
    for event in participated:
        pending_count = db.query(Payment).filter(
            Payment.event_id == event.id,
            Payment.status == PaymentStatus.pending
        ).count()
        events_with_stats.append({"event": event, "pending_count": pending_count})

    return templates.TemplateResponse("home.html", {
        "request": request,
        "user": user,
        "events_with_stats": events_with_stats,
    })
```

- [ ] **Step 4: `app/templates/home.html` を作成**

```html
{% extends "base.html" %}
{% block title %}ホーム — Walican Reminder{% endblock %}
{% block content %}
<div class="page-header">
  <h1>イベント一覧</h1>
  <a href="/events/new" class="btn btn-primary">＋ イベント作成</a>
</div>

{% if events_with_stats %}
  {% for item in events_with_stats %}
    <a href="/events/{{ item.event.id }}" style="text-decoration:none; color:inherit;">
      <div class="card">
        <div class="card-title">{{ item.event.name }}</div>
        {% if item.event.status.value == "completed" %}
          <span class="badge badge-success">✓ 完了</span>
        {% elif item.pending_count > 0 %}
          <span class="badge badge-danger">● 未払い {{ item.pending_count }}件</span>
        {% else %}
          <span class="badge badge-success">✓ 全員支払済み</span>
        {% endif %}
        {% if item.event.payment_deadline %}
          <div style="font-size:0.8rem; color:#888; margin-top:4px;">期限: {{ item.event.payment_deadline }}</div>
        {% endif %}
      </div>
    </a>
  {% endfor %}
{% else %}
  <p style="color:#888; text-align:center; margin-top:40px;">イベントがありません。「＋ イベント作成」から始めましょう。</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: `app/main.py` にルーターを追加**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.config import settings
from app.routers import auth, home

app = FastAPI(title="Walican Reminder")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth.router)
app.include_router(home.router)
```

- [ ] **Step 6: 手動確認（サーバー起動→ブラウザ）**

```bash
uvicorn app.main:app --reload
```

ブラウザで `http://localhost:8000/` を開き `/login` にリダイレクトされることを確認。

- [ ] **Step 7: コミット**

```bash
git add app/routers/home.py app/templates/ app/static/
git commit -m "feat: home page with event list"
```

---

### Task 7: 仲間グループ CRUD

**Files:**
- Create: `app/routers/groups.py`
- Create: `app/templates/groups/list.html`, `app/templates/groups/detail.html`
- Create: `app/templates/groups/partials/member_row.html`
- Create: `tests/test_groups.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `get_current_user`、`FriendGroup`、`FriendGroupMember`、`User`
- Produces: `/groups/*` ルート群

- [ ] **Step 1: `tests/test_groups.py` の失敗テストを書く**

```python
from app.models.friend_group import FriendGroup, FriendGroupMember

def test_create_group(auth_client, db, user):
    response = auth_client.post("/groups", data={"name": "旅行仲間"}, follow_redirects=False)
    assert response.status_code in (302, 303)
    group = db.query(FriendGroup).filter(FriendGroup.name == "旅行仲間").first()
    assert group is not None
    assert group.created_by == user.id

def test_add_member_to_group(auth_client, db, user):
    from app.models.user import User
    other = User(discord_id="999", discord_username="OtherUser")
    db.add(other)
    group = FriendGroup(name="Test", created_by=user.id)
    db.add(group)
    db.commit()
    db.refresh(group)

    response = auth_client.post(f"/groups/{group.id}/members", data={"username": "OtherUser"}, follow_redirects=False)
    assert response.status_code in (200, 302, 303)
    member = db.query(FriendGroupMember).filter(
        FriendGroupMember.friend_group_id == group.id,
        FriendGroupMember.user_id == other.id,
    ).first()
    assert member is not None

def test_delete_member(auth_client, db, user):
    from app.models.user import User
    other = User(discord_id="888", discord_username="ToDelete")
    db.add(other)
    group = FriendGroup(name="Test2", created_by=user.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    db.refresh(other)
    member = FriendGroupMember(friend_group_id=group.id, user_id=other.id)
    db.add(member)
    db.commit()

    response = auth_client.delete(f"/groups/{group.id}/members/{other.id}", follow_redirects=False)
    assert response.status_code in (200, 302, 303)
    assert db.query(FriendGroupMember).filter(
        FriendGroupMember.friend_group_id == group.id,
        FriendGroupMember.user_id == other.id,
    ).first() is None
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/test_groups.py -v
```

期待出力: `FAILED` — ルートが存在しない

- [ ] **Step 3: `app/routers/groups.py` を作成**

```python
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.friend_group import FriendGroup, FriendGroupMember

router = APIRouter(prefix="/groups")
templates = Jinja2Templates(directory="app/templates")

def _require_group_owner(group_id: str, user: User, db: Session) -> FriendGroup:
    group = db.get(FriendGroup, group_id)
    if not group or group.created_by != user.id:
        raise HTTPException(status_code=404)
    return group

@router.get("", response_class=HTMLResponse)
async def list_groups(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    groups = db.query(FriendGroup).filter(FriendGroup.created_by == user.id).all()
    return templates.TemplateResponse("groups/list.html", {"request": request, "user": user, "groups": groups})

@router.post("")
async def create_group(name: str = Form(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group = FriendGroup(name=name, created_by=user.id)
    db.add(group)
    db.commit()
    return RedirectResponse(f"/groups/{group.id}", status_code=303)

@router.get("/{group_id}", response_class=HTMLResponse)
async def group_detail(group_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group = _require_group_owner(group_id, user, db)
    members = [m.user for m in group.members]
    return templates.TemplateResponse("groups/detail.html", {"request": request, "user": user, "group": group, "members": members})

@router.post("/{group_id}/members", response_class=HTMLResponse)
async def add_member(group_id: str, request: Request, username: str = Form(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group = _require_group_owner(group_id, user, db)
    target = db.query(User).filter(User.discord_username == username).first()
    if not target:
        return HTMLResponse(f'<p class="text-danger">ユーザー「{username}」は見つかりません（一度でもログインしている必要があります）</p>', status_code=200)
    exists = db.query(FriendGroupMember).filter(
        FriendGroupMember.friend_group_id == group_id,
        FriendGroupMember.user_id == target.id,
    ).first()
    if not exists:
        db.add(FriendGroupMember(friend_group_id=group_id, user_id=target.id))
        db.commit()
    db.refresh(group)
    return templates.TemplateResponse("groups/partials/member_row.html", {"request": request, "member": target, "group": group})

@router.delete("/{group_id}/members/{user_id}")
async def remove_member(group_id: str, user_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_group_owner(group_id, user, db)
    db.query(FriendGroupMember).filter(
        FriendGroupMember.friend_group_id == group_id,
        FriendGroupMember.user_id == user_id,
    ).delete()
    db.commit()
    return HTMLResponse("", status_code=200)
```

- [ ] **Step 4: テンプレートを作成（`app/templates/groups/list.html`）**

```html
{% extends "base.html" %}
{% block title %}仲間グループ — Walican Reminder{% endblock %}
{% block content %}
<div class="page-header">
  <h1>仲間グループ</h1>
</div>
<div class="card">
  <form method="post" action="/groups">
    <div class="form-group">
      <label>グループ名</label>
      <input type="text" name="name" required placeholder="例: 旅行仲間">
    </div>
    <button type="submit" class="btn btn-primary">作成</button>
  </form>
</div>
{% for group in groups %}
  <a href="/groups/{{ group.id }}" style="text-decoration:none;color:inherit;">
    <div class="card">
      <div class="card-title">{{ group.name }}</div>
      <div style="font-size:0.8rem;color:#888;">{{ group.members|length }}人</div>
    </div>
  </a>
{% endfor %}
{% endblock %}
```

- [ ] **Step 5: `app/templates/groups/detail.html` を作成**

```html
{% extends "base.html" %}
{% block title %}{{ group.name }} — Walican Reminder{% endblock %}
{% block content %}
<div class="page-header">
  <h1>{{ group.name }}</h1>
  <a href="/groups" class="btn btn-secondary">← 戻る</a>
</div>

<div class="card">
  <h3 style="margin-bottom:12px;">メンバー</h3>
  <div id="member-list">
    {% for member in members %}
      <div id="member-{{ member.id }}" style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f0f0f0;">
        <span>{{ member.discord_username }}</span>
        {% if member.id != user.id %}
          <button class="btn btn-danger" style="padding:2px 10px;font-size:0.8rem;"
            hx-delete="/groups/{{ group.id }}/members/{{ member.id }}"
            hx-target="#member-{{ member.id }}"
            hx-swap="outerHTML">削除</button>
        {% endif %}
      </div>
    {% endfor %}
  </div>

  <form hx-post="/groups/{{ group.id }}/members" hx-target="#member-list" hx-swap="beforeend" style="margin-top:12px;display:flex;gap:8px;">
    <input type="text" name="username" placeholder="Discord ユーザー名" style="flex:1;padding:8px;border:1px solid #ddd;border-radius:6px;">
    <button type="submit" class="btn btn-primary">追加</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 6: `app/templates/groups/partials/member_row.html` を作成**

```html
<div id="member-{{ member.id }}" style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f0f0f0;">
  <span>{{ member.discord_username }}</span>
  <button class="btn btn-danger" style="padding:2px 10px;font-size:0.8rem;"
    hx-delete="/groups/{{ group.id }}/members/{{ member.id }}"
    hx-target="#member-{{ member.id }}"
    hx-swap="outerHTML">削除</button>
</div>
```

- [ ] **Step 7: `app/main.py` にルーター追加、テスト実行**

`app/main.py` の import と include_router に `groups` を追加:
```python
from app.routers import auth, home, groups
...
app.include_router(groups.router)
```

```bash
pytest tests/test_groups.py -v
```

期待出力: `3 passed`

- [ ] **Step 8: コミット**

```bash
git add app/routers/groups.py app/templates/groups/ app/main.py tests/test_groups.py
git commit -m "feat: friend group CRUD"
```

---

### Task 8: イベント CRUD

**Files:**
- Create: `app/routers/events.py`
- Create: `app/templates/events/new.html`, `app/templates/events/detail.html`
- Create: `tests/test_events.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `get_current_user`、`Event`、`EventParticipant`、`FriendGroup`、`FriendGroupMember`
- Produces: `/events/*` ルート群

- [ ] **Step 1: `tests/test_events.py` の失敗テストを書く**

```python
from app.models.event import Event, EventParticipant, EventStatus
from app.models.user import User

def test_create_event(auth_client, db, user):
    response = auth_client.post("/events", data={
        "name": "北海道旅行",
        "description": "2025年夏",
        "payment_deadline": "2025-08-31",
        "participant_ids": [user.id],
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    event = db.query(Event).filter(Event.name == "北海道旅行").first()
    assert event is not None
    assert db.query(EventParticipant).filter(EventParticipant.event_id == event.id).count() == 1

def test_create_event_with_friend_group(auth_client, db, user):
    from app.models.friend_group import FriendGroup, FriendGroupMember
    other = User(discord_id="777", discord_username="GroupUser")
    db.add(other)
    group = FriendGroup(name="旅行仲間", created_by=user.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    db.refresh(other)
    db.add(FriendGroupMember(friend_group_id=group.id, user_id=other.id))
    db.commit()

    response = auth_client.post("/events", data={
        "name": "グループイベント",
        "friend_group_id": group.id,
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    event = db.query(Event).filter(Event.name == "グループイベント").first()
    participants = db.query(EventParticipant).filter(EventParticipant.event_id == event.id).all()
    participant_ids = {p.user_id for p in participants}
    assert user.id in participant_ids
    assert other.id in participant_ids

def test_complete_event(auth_client, db, user):
    event = Event(name="完了テスト", created_by=user.id)
    db.add(event)
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.commit()
    db.refresh(event)

    response = auth_client.post(f"/events/{event.id}/complete", follow_redirects=False)
    assert response.status_code in (302, 303)
    db.refresh(event)
    assert event.status == EventStatus.completed
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/test_events.py -v
```

期待出力: `FAILED`

- [ ] **Step 3: `app/routers/events.py` を作成**

```python
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.event import Event, EventParticipant, EventStatus
from app.models.friend_group import FriendGroup, FriendGroupMember

router = APIRouter(prefix="/events")
templates = Jinja2Templates(directory="app/templates")

def _require_participant(event_id: str, user: User, db: Session) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404)
    is_participant = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == user.id,
    ).first()
    if not is_participant:
        raise HTTPException(status_code=403)
    return event

@router.get("/new", response_class=HTMLResponse)
async def new_event_form(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    groups = db.query(FriendGroup).filter(FriendGroup.created_by == user.id).all()
    all_users = db.query(User).filter(User.id != user.id).all()
    return templates.TemplateResponse("events/new.html", {
        "request": request, "user": user, "groups": groups, "all_users": all_users,
    })

@router.post("")
async def create_event(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    payment_deadline: Optional[str] = Form(None),
    friend_group_id: Optional[str] = Form(None),
    participant_ids: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from datetime import date
    deadline = date.fromisoformat(payment_deadline) if payment_deadline else None
    event = Event(name=name, description=description, payment_deadline=deadline, created_by=user.id)
    db.add(event)
    db.flush()

    participant_set = {user.id}
    if friend_group_id:
        members = db.query(FriendGroupMember).filter(FriendGroupMember.friend_group_id == friend_group_id).all()
        participant_set.update(m.user_id for m in members)
    participant_set.update(participant_ids)

    for uid in participant_set:
        db.add(EventParticipant(event_id=event.id, user_id=uid))
    db.commit()
    return RedirectResponse(f"/events/{event.id}", status_code=303)

@router.get("/{event_id}", response_class=HTMLResponse)
async def event_detail(event_id: str, request: Request, tab: str = "expenses", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = _require_participant(event_id, user, db)
    participants = [p.user for p in event.participants]
    return templates.TemplateResponse("events/detail.html", {
        "request": request, "user": user, "event": event,
        "participants": participants, "tab": tab,
    })

@router.post("/{event_id}/complete")
async def complete_event(event_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = _require_participant(event_id, user, db)
    event.status = EventStatus.completed
    db.commit()
    return RedirectResponse(f"/events/{event_id}", status_code=303)
```

- [ ] **Step 4: `app/templates/events/new.html` を作成**

```html
{% extends "base.html" %}
{% block title %}イベント作成 — Walican Reminder{% endblock %}
{% block content %}
<div class="page-header">
  <h1>イベント作成</h1>
  <a href="/" class="btn btn-secondary">← 戻る</a>
</div>
<div class="card">
  <form method="post" action="/events">
    <div class="form-group">
      <label>イベント名 *</label>
      <input type="text" name="name" required placeholder="例: 北海道旅行 2025">
    </div>
    <div class="form-group">
      <label>説明</label>
      <textarea name="description" rows="2" placeholder="メモ（任意）"></textarea>
    </div>
    <div class="form-group">
      <label>支払期限</label>
      <input type="date" name="payment_deadline">
    </div>
    <div class="form-group">
      <label>仲間グループから一括追加（任意）</label>
      <select name="friend_group_id">
        <option value="">選択しない</option>
        {% for group in groups %}
          <option value="{{ group.id }}">{{ group.name }}（{{ group.members|length }}人）</option>
        {% endfor %}
      </select>
    </div>
    <div class="form-group">
      <label>個別追加（任意、複数選択可）</label>
      <select name="participant_ids" multiple style="height:120px;">
        {% for u in all_users %}
          <option value="{{ u.id }}">{{ u.discord_username }}</option>
        {% endfor %}
      </select>
    </div>
    <button type="submit" class="btn btn-primary">作成</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: `app/templates/events/detail.html` を作成（タブ構造）**

```html
{% extends "base.html" %}
{% block title %}{{ event.name }} — Walican Reminder{% endblock %}
{% block content %}
<div class="page-header">
  <h1>{{ event.name }}</h1>
  <div style="display:flex;gap:8px;">
    {% if event.status.value == "active" %}
      <form method="post" action="/events/{{ event.id }}/complete" style="display:inline;">
        <button type="submit" class="btn btn-secondary" onclick="return confirm('完了にしますか？')">完了にする</button>
      </form>
    {% else %}
      <span class="badge badge-success">✓ 完了済み</span>
    {% endif %}
    <a href="/" class="btn btn-secondary">← 戻る</a>
  </div>
</div>

<div class="tabs">
  <a href="/events/{{ event.id }}?tab=expenses" class="tab {% if tab == 'expenses' %}active{% endif %}">支出</a>
  <a href="/events/{{ event.id }}?tab=payments" class="tab {% if tab == 'payments' %}active{% endif %}">精算状況</a>
  <a href="/events/{{ event.id }}?tab=notification" class="tab {% if tab == 'notification' %}active{% endif %}">通知設定</a>
</div>

{% if tab == "expenses" %}
  {% include "events/partials/expenses_tab.html" %}
{% elif tab == "payments" %}
  {% include "events/partials/payments_tab.html" %}
{% elif tab == "notification" %}
  {% include "events/partials/notification_tab.html" %}
{% endif %}
{% endblock %}
```

- [ ] **Step 6: `app/main.py` にルーター追加、テスト実行**

```python
from app.routers import auth, home, groups, events
...
app.include_router(events.router)
```

```bash
pytest tests/test_events.py -v
```

期待出力: `3 passed`

- [ ] **Step 7: コミット**

```bash
git add app/routers/events.py app/templates/events/ app/main.py tests/test_events.py
git commit -m "feat: event CRUD with participant management"
```

---

### Task 9: 支出管理と精算再計算

**Files:**
- Create: `app/routers/expenses.py`
- Create: `app/templates/events/partials/expenses_tab.html`
- Create: `app/templates/events/partials/expense_row.html`
- Create: `tests/test_expenses.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `calculate_settlement()`（Task 5）、`ExpenseInput`、`ParticipantInput`
- Produces: `/events/{id}/expenses/*`、`apply_settlement(event_id, db)` 関数

- [ ] **Step 1: `tests/test_expenses.py` の失敗テストを書く**

```python
from decimal import Decimal
from app.models.event import Event, EventParticipant
from app.models.expense import Expense, ExpenseParticipant
from app.models.payment import Payment, PaymentStatus
from app.models.user import User

def _create_event_with_users(db, creator, others):
    event = Event(name="精算テスト", created_by=creator.id)
    db.add(event)
    db.flush()
    for u in [creator] + others:
        db.add(EventParticipant(event_id=event.id, user_id=u.id))
    db.commit()
    db.refresh(event)
    return event

def test_add_expense_creates_payment(auth_client, db, user):
    other = User(discord_id="001", discord_username="Other1")
    db.add(other)
    db.commit()
    db.refresh(other)
    event = _create_event_with_users(db, user, [other])

    response = auth_client.post(f"/events/{event.id}/expenses", data={
        "title": "ホテル代",
        "total_amount": "10000",
        "paid_by": user.id,
        "participant_ids": [user.id, other.id],
    }, follow_redirects=False)
    assert response.status_code in (200, 302, 303)

    payments = db.query(Payment).filter(Payment.event_id == event.id).all()
    assert len(payments) == 1
    assert payments[0].from_user_id == other.id
    assert payments[0].to_user_id == user.id
    assert payments[0].amount == Decimal(5000)

def test_delete_expense_recalculates(auth_client, db, user):
    other = User(discord_id="002", discord_username="Other2")
    db.add(other)
    db.commit()
    db.refresh(other)
    event = _create_event_with_users(db, user, [other])

    expense = Expense(event_id=event.id, title="食費", total_amount=Decimal(6000), paid_by=user.id)
    db.add(expense)
    db.flush()
    db.add(ExpenseParticipant(expense_id=expense.id, user_id=user.id, custom_amount=None))
    db.add(ExpenseParticipant(expense_id=expense.id, user_id=other.id, custom_amount=None))
    db.commit()
    db.refresh(expense)

    from app.services.settlement import apply_settlement
    apply_settlement(event.id, db)
    assert db.query(Payment).filter(Payment.event_id == event.id).count() == 1

    response = auth_client.delete(f"/events/{event.id}/expenses/{expense.id}", follow_redirects=False)
    assert response.status_code in (200, 302, 303)
    assert db.query(Payment).filter(Payment.event_id == event.id, Payment.status == PaymentStatus.pending).count() == 0
```

- [ ] **Step 2: `app/services/settlement.py` に `apply_settlement()` を追加**

```python
# 既存コードの末尾に追加

from sqlalchemy.orm import Session

def apply_settlement(event_id: str, db: Session) -> None:
    from app.models.expense import Expense, ExpenseParticipant
    from app.models.payment import Payment, PaymentStatus

    expenses_db = db.query(Expense).filter(Expense.event_id == event_id).all()

    inputs = []
    for exp in expenses_db:
        participants = [
            ParticipantInput(user_id=p.user_id, custom_amount=p.custom_amount)
            for p in exp.participants
        ]
        inputs.append(ExpenseInput(
            paid_by=exp.paid_by,
            total_amount=exp.total_amount,
            participants=participants,
        ))

    new_payments = calculate_settlement(inputs)

    # paid 済みを保持しつつ pending を再計算
    paid = db.query(Payment).filter(
        Payment.event_id == event_id,
        Payment.status == PaymentStatus.paid,
    ).all()
    paid_amounts: dict[tuple[str, str], Decimal] = {}
    for p in paid:
        key = (p.from_user_id, p.to_user_id)
        paid_amounts[key] = paid_amounts.get(key, Decimal(0)) + p.amount

    db.query(Payment).filter(
        Payment.event_id == event_id,
        Payment.status == PaymentStatus.pending,
    ).delete()

    for from_uid, to_uid, amount in new_payments:
        already_paid = paid_amounts.get((from_uid, to_uid), Decimal(0))
        remaining = amount - already_paid
        if remaining > 0:
            db.add(Payment(event_id=event_id, from_user_id=from_uid, to_user_id=to_uid, amount=remaining))

    db.commit()
```

- [ ] **Step 3: `app/routers/expenses.py` を作成**

```python
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from decimal import Decimal
from typing import Optional
from app.database import get_db
from app.routers.auth import get_current_user
from app.routers.events import _require_participant
from app.models.user import User
from app.models.expense import Expense, ExpenseParticipant
from app.services.settlement import apply_settlement

router = APIRouter(prefix="/events/{event_id}/expenses")
templates = Jinja2Templates(directory="app/templates")

@router.post("")
async def add_expense(
    event_id: str,
    request: Request,
    title: str = Form(...),
    total_amount: str = Form(...),
    paid_by: str = Form(...),
    participant_ids: list[str] = Form(...),
    custom_amounts: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_participant(event_id, user, db)
    expense = Expense(
        event_id=event_id,
        title=title,
        total_amount=Decimal(total_amount),
        paid_by=paid_by,
    )
    db.add(expense)
    db.flush()

    for i, uid in enumerate(participant_ids):
        custom = Decimal(custom_amounts[i]) if i < len(custom_amounts) and custom_amounts[i] else None
        db.add(ExpenseParticipant(expense_id=expense.id, user_id=uid, custom_amount=custom))

    db.commit()
    apply_settlement(event_id, db)
    return RedirectResponse(f"/events/{event_id}?tab=expenses", status_code=303)

@router.delete("/{expense_id}")
async def delete_expense(
    event_id: str,
    expense_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_participant(event_id, user, db)
    expense = db.get(Expense, expense_id)
    if not expense or expense.event_id != event_id:
        raise HTTPException(status_code=404)
    db.delete(expense)
    db.commit()
    apply_settlement(event_id, db)
    return RedirectResponse(f"/events/{event_id}?tab=expenses", status_code=303)
```

- [ ] **Step 4: `app/templates/events/partials/expenses_tab.html` を作成**

```html
<div class="card" style="margin-bottom:16px;">
  <h3 style="margin-bottom:12px;">支出追加</h3>
  <form method="post" action="/events/{{ event.id }}/expenses">
    <div class="form-group">
      <label>タイトル *</label>
      <input type="text" name="title" required placeholder="例: ホテル代">
    </div>
    <div class="form-group">
      <label>金額（円）*</label>
      <input type="number" name="total_amount" required min="1">
    </div>
    <div class="form-group">
      <label>立替者 *</label>
      <select name="paid_by" required>
        {% for p in participants %}
          <option value="{{ p.id }}">{{ p.discord_username }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="form-group">
      <label>参加者（カスタム金額は空欄で均等割り）</label>
      {% for p in participants %}
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
          <input type="checkbox" name="participant_ids" value="{{ p.id }}" id="p_{{ p.id }}" checked>
          <label for="p_{{ p.id }}" style="margin:0;flex:1;">{{ p.discord_username }}</label>
          <input type="number" name="custom_amounts" placeholder="カスタム金額" style="width:120px;">
        </div>
      {% endfor %}
    </div>
    <button type="submit" class="btn btn-primary">追加</button>
  </form>
</div>

<h3 style="margin-bottom:12px;">支出一覧</h3>
{% for expense in event.expenses %}
  <div class="card" style="margin-bottom:8px;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <div>
        <div class="card-title">{{ expense.title }}</div>
        <div style="font-size:0.85rem;color:#888;">¥{{ "{:,}".format(expense.total_amount|int) }} — 立替: {{ expense.payer.discord_username }}</div>
        <div style="font-size:0.8rem;color:#aaa;">
          {% for ep in expense.participants %}{{ ep.user.discord_username }}{% if ep.custom_amount %}(¥{{ ep.custom_amount|int }}){% endif %}{% if not loop.last %}、{% endif %}{% endfor %}
        </div>
      </div>
      <form method="post" action="/events/{{ event.id }}/expenses/{{ expense.id }}?_method=DELETE" style="display:inline;">
        <input type="hidden" name="_method" value="DELETE">
        <button type="submit" class="btn btn-danger" style="padding:4px 10px;font-size:0.8rem;"
          onclick="return confirm('削除しますか？')"
          hx-delete="/events/{{ event.id }}/expenses/{{ expense.id }}"
          hx-confirm="削除しますか？"
          hx-target="closest .card"
          hx-swap="outerHTML">削除</button>
      </form>
    </div>
  </div>
{% else %}
  <p style="color:#888;">支出がまだありません。</p>
{% endfor %}
```

- [ ] **Step 5: `app/main.py` にルーター追加、テスト実行**

```python
from app.routers import auth, home, groups, events, expenses
...
app.include_router(expenses.router)
```

```bash
pytest tests/test_expenses.py -v
```

期待出力: `2 passed`

- [ ] **Step 6: コミット**

```bash
git add app/routers/expenses.py app/templates/events/partials/expenses_tab.html app/services/settlement.py app/main.py tests/test_expenses.py
git commit -m "feat: expense management with settlement recalculation"
```

---

### Task 10: 精算ステータス管理

**Files:**
- Create: `app/routers/payments.py`
- Create: `app/templates/events/partials/payments_tab.html`
- Create: `tests/test_payments.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `Payment`、`PaymentStatus`、`_require_participant`
- Produces: `POST /events/{id}/payments/{pid}/pay`

- [ ] **Step 1: `tests/test_payments.py` の失敗テストを書く**

```python
from decimal import Decimal
from app.models.event import Event, EventParticipant
from app.models.payment import Payment, PaymentStatus
from app.models.user import User

def test_mark_payment_as_paid(auth_client, db, user):
    other = User(discord_id="010", discord_username="Payer")
    db.add(other)
    event = Event(name="精算テスト", created_by=user.id)
    db.add(event)
    db.flush()
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.add(EventParticipant(event_id=event.id, user_id=other.id))
    payment = Payment(event_id=event.id, from_user_id=other.id, to_user_id=user.id, amount=Decimal(5000))
    db.add(payment)
    db.commit()
    db.refresh(payment)

    response = auth_client.post(f"/events/{event.id}/payments/{payment.id}/pay", follow_redirects=False)
    assert response.status_code in (200, 302, 303)
    db.refresh(payment)
    assert payment.status == PaymentStatus.paid
    assert payment.paid_at is not None

def test_unmark_payment(auth_client, db, user):
    from datetime import datetime
    other = User(discord_id="011", discord_username="Payer2")
    db.add(other)
    event = Event(name="精算テスト2", created_by=user.id)
    db.add(event)
    db.flush()
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.add(EventParticipant(event_id=event.id, user_id=other.id))
    payment = Payment(event_id=event.id, from_user_id=other.id, to_user_id=user.id,
                      amount=Decimal(3000), status=PaymentStatus.paid, paid_at=datetime.utcnow())
    db.add(payment)
    db.commit()
    db.refresh(payment)

    response = auth_client.post(f"/events/{event.id}/payments/{payment.id}/pay", follow_redirects=False)
    assert response.status_code in (200, 302, 303)
    db.refresh(payment)
    assert payment.status == PaymentStatus.pending
    assert payment.paid_at is None
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/test_payments.py -v
```

期待出力: `FAILED`

- [ ] **Step 3: `app/routers/payments.py` を作成**

```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.routers.auth import get_current_user
from app.routers.events import _require_participant
from app.models.user import User
from app.models.payment import Payment, PaymentStatus

router = APIRouter(prefix="/events/{event_id}/payments")

@router.post("/{payment_id}/pay")
async def toggle_payment(
    event_id: str,
    payment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_participant(event_id, user, db)
    payment = db.get(Payment, payment_id)
    if not payment or payment.event_id != event_id:
        raise HTTPException(status_code=404)

    if payment.status == PaymentStatus.pending:
        payment.status = PaymentStatus.paid
        payment.paid_at = datetime.utcnow()
    else:
        payment.status = PaymentStatus.pending
        payment.paid_at = None
    db.commit()
    return RedirectResponse(f"/events/{event_id}?tab=payments", status_code=303)
```

- [ ] **Step 4: `app/templates/events/partials/payments_tab.html` を作成**

```html
<h3 style="margin-bottom:12px;">精算状況</h3>
{% set payments = event.payments %}
{% if payments %}
  {% for payment in payments %}
    <div class="card" style="margin-bottom:8px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
          <span style="font-weight:600;">{{ payment.from_user.discord_username }}</span>
          → {{ payment.to_user.discord_username }}
          <span style="margin-left:8px;font-weight:600;">¥{{ "{:,}".format(payment.amount|int) }}</span>
        </div>
        <form method="post" action="/events/{{ event.id }}/payments/{{ payment.id }}/pay">
          {% if payment.status.value == "paid" %}
            <button type="submit" class="btn btn-secondary" style="padding:4px 12px;font-size:0.85rem;">✓ 支払済み</button>
          {% else %}
            <button type="submit" class="btn btn-primary" style="padding:4px 12px;font-size:0.85rem;">支払済みにする</button>
          {% endif %}
        </form>
      </div>
    </div>
  {% endfor %}
{% else %}
  <p style="color:#888;">支出を追加すると精算額が表示されます。</p>
{% endif %}
```

- [ ] **Step 5: `app/main.py` にルーター追加、テスト実行**

```python
from app.routers import auth, home, groups, events, expenses, payments
...
app.include_router(payments.router)
```

```bash
pytest tests/test_payments.py -v
```

期待出力: `2 passed`

- [ ] **Step 6: コミット**

```bash
git add app/routers/payments.py app/templates/events/partials/payments_tab.html app/main.py tests/test_payments.py
git commit -m "feat: payment status toggle"
```

---

### Task 11: 通知設定 UI

**Files:**
- Create: `app/routers/notifications.py`
- Create: `app/templates/events/partials/notification_tab.html`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `NotificationSetting`、`NotificationMode`
- Produces: `GET/POST /events/{id}/notification`

- [ ] **Step 1: `app/routers/notifications.py` を作成**

```python
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.routers.auth import get_current_user
from app.routers.events import _require_participant
from app.models.user import User
from app.models.notification import NotificationSetting, NotificationMode

router = APIRouter(prefix="/events/{event_id}/notification")
templates = Jinja2Templates(directory="app/templates")

@router.post("")
async def save_notification(
    event_id: str,
    discord_channel_id: str = Form(...),
    mode: str = Form(...),
    schedule_cron: Optional[str] = Form(None),
    deadline_days_before: Optional[int] = Form(None),
    deadline_days_after: Optional[int] = Form(None),
    notify_from_date: Optional[str] = Form(None),
    notify_interval_days: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_participant(event_id, user, db)
    from datetime import date
    setting = db.query(NotificationSetting).filter(NotificationSetting.event_id == event_id).first()
    if not setting:
        setting = NotificationSetting(event_id=event_id)
        db.add(setting)

    setting.discord_channel_id = discord_channel_id
    setting.mode = NotificationMode(mode)
    setting.schedule_cron = schedule_cron or None
    setting.deadline_days_before = deadline_days_before
    setting.deadline_days_after = deadline_days_after
    setting.notify_from_date = date.fromisoformat(notify_from_date) if notify_from_date else None
    setting.notify_interval_days = notify_interval_days
    db.commit()
    return RedirectResponse(f"/events/{event_id}?tab=notification", status_code=303)

@router.post("/send-now")
async def send_now(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.config import settings
    import httpx
    _require_participant(event_id, user, db)
    if settings.functions_url and settings.functions_key:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.functions_url}/api/notify/{event_id}",
                headers={"x-functions-key": settings.functions_key},
                timeout=10,
            )
    return RedirectResponse(f"/events/{event_id}?tab=notification", status_code=303)
```

- [ ] **Step 2: `app/templates/events/partials/notification_tab.html` を作成**

```html
{% set ns = event.notification_setting if event.notification_setting else none %}
<div class="card">
  <h3 style="margin-bottom:16px;">通知設定</h3>
  <form method="post" action="/events/{{ event.id }}/notification">
    <div class="form-group">
      <label>Discord チャンネル ID *</label>
      <input type="text" name="discord_channel_id" required value="{{ ns.discord_channel_id if ns else '' }}" placeholder="例: 1234567890123456789">
      <small style="color:#888;">チャンネルを右クリック → 「IDをコピー」</small>
    </div>

    <div class="form-group">
      <label>通知モード *</label>
      <select name="mode" id="mode-select" onchange="document.querySelectorAll('.mode-section').forEach(el=>el.style.display='none');document.getElementById('mode-'+this.value).style.display='block';">
        <option value="scheduled" {% if ns and ns.mode.value == 'scheduled' %}selected{% endif %}>定期スケジュール</option>
        <option value="deadline" {% if ns and ns.mode.value == 'deadline' %}selected{% endif %}>支払期限ベース</option>
        <option value="from_date" {% if ns and ns.mode.value == 'from_date' %}selected{% endif %}>指定日以降</option>
      </select>
    </div>

    <div id="mode-scheduled" class="mode-section" style="display:{% if not ns or ns.mode.value == 'scheduled' %}block{% else %}none{% endif %};">
      <div class="form-group">
        <label>Cron 式（例: <code>0 12 * * 1</code> = 毎週月曜12時）</label>
        <input type="text" name="schedule_cron" value="{{ ns.schedule_cron if ns else '' }}" placeholder="0 12 * * 1">
      </div>
    </div>

    <div id="mode-deadline" class="mode-section" style="display:{% if ns and ns.mode.value == 'deadline' %}block{% else %}none{% endif %};">
      <div class="form-group">
        <label>期限N日前から通知</label>
        <input type="number" name="deadline_days_before" value="{{ ns.deadline_days_before if ns else 3 }}" min="0">
      </div>
      <div class="form-group">
        <label>期限N日後まで通知</label>
        <input type="number" name="deadline_days_after" value="{{ ns.deadline_days_after if ns else 7 }}" min="0">
      </div>
    </div>

    <div id="mode-from_date" class="mode-section" style="display:{% if ns and ns.mode.value == 'from_date' %}block{% else %}none{% endif %};">
      <div class="form-group">
        <label>通知開始日</label>
        <input type="date" name="notify_from_date" value="{{ ns.notify_from_date if ns else '' }}">
      </div>
      <div class="form-group">
        <label>通知間隔（日）</label>
        <input type="number" name="notify_interval_days" value="{{ ns.notify_interval_days if ns else 3 }}" min="1">
      </div>
    </div>

    <button type="submit" class="btn btn-primary">保存</button>
  </form>

  {% if ns %}
    <form method="post" action="/events/{{ event.id }}/notification/send-now" style="margin-top:16px;">
      <button type="submit" class="btn btn-secondary">今すぐ通知を送信</button>
    </form>
    {% if ns.last_notified_at %}
      <p style="font-size:0.8rem;color:#888;margin-top:8px;">最終通知: {{ ns.last_notified_at }}</p>
    {% endif %}
  {% endif %}
</div>
```

- [ ] **Step 3: `Event` モデルに `notification_setting` リレーションを追加**

`app/models/event.py` の `Event` クラスの `relationships` に追加:
```python
notification_setting: Mapped["NotificationSetting | None"] = relationship("NotificationSetting", back_populates="event", uselist=False)
```

`app/models/notification.py` の `NotificationSetting` に逆リレーションを追加:
```python
event: Mapped["Event"] = relationship("Event", back_populates="notification_setting")
```

- [ ] **Step 4: `app/main.py` にルーター追加**

```python
from app.routers import auth, home, groups, events, expenses, payments, notifications
...
app.include_router(notifications.router)
```

- [ ] **Step 5: 手動確認**

```bash
uvicorn app.main:app --reload
```

ブラウザで `/events/{id}?tab=notification` を開き、フォームが表示されることを確認。

- [ ] **Step 6: コミット**

```bash
git add app/routers/notifications.py app/templates/events/partials/notification_tab.html app/models/event.py app/models/notification.py app/main.py
git commit -m "feat: notification settings UI"
```

---

### Task 12: Azure App Service デプロイ

**Files:**
- Modify: `startup.sh`
- Create: `.github/workflows/deploy.yml`（任意）

**Interfaces:**
- Consumes: 全タスクの成果物
- Produces: Azure App Service で動作する Web アプリ

- [ ] **Step 1: `startup.sh` を最終版に更新**

```bash
#!/bin/bash
set -e
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

- [ ] **Step 2: Azure App Service を作成（Azure Portal または Azure CLI）**

```bash
az group create --name walican-rg --location japaneast
az appservice plan create --name walican-plan --resource-group walican-rg --sku F1 --is-linux
az webapp create --name walican-reminder --resource-group walican-rg --plan walican-plan --runtime "PYTHON:3.12"
az webapp config set --name walican-reminder --resource-group walican-rg --startup-file "startup.sh"
```

- [ ] **Step 3: 環境変数を Azure App Service に設定**

```bash
az webapp config appsettings set --name walican-reminder --resource-group walican-rg --settings \
  DATABASE_URL="mssql+pyodbc://..." \
  DISCORD_CLIENT_ID="..." \
  DISCORD_CLIENT_SECRET="..." \
  DISCORD_BOT_TOKEN="..." \
  DISCORD_REDIRECT_URI="https://walican-reminder.azurewebsites.net/auth/callback" \
  SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  FUNCTIONS_URL="" \
  FUNCTIONS_KEY=""
```

- [ ] **Step 4: デプロイ（zip deploy）**

```bash
zip -r deploy.zip . -x "*.git*" "__pycache__/*" "test.db" ".env"
az webapp deployment source config-zip --name walican-reminder --resource-group walican-rg --src deploy.zip
```

- [ ] **Step 5: 動作確認**

```bash
az webapp browse --name walican-reminder --resource-group walican-rg
```

ブラウザで `https://walican-reminder.azurewebsites.net/` が開き、Discord ログイン画面が表示されることを確認。

- [ ] **Step 6: Discord Developer Portal で OAuth2 Redirect URI を追加**

`https://walican-reminder.azurewebsites.net/auth/callback` を Redirect URI に追加。

- [ ] **Step 7: 全テスト実行**

```bash
pytest tests/ -v
```

期待出力: すべて `PASSED`

- [ ] **Step 8: 最終コミット**

```bash
git add startup.sh
git commit -m "feat: Azure App Service deployment config"
git tag v1.0.0-webapp
```

---

## 実装後の次のステップ

**Plan B: Azure Functions 通知システム** を別プランとして実装する。

内容:
- `functions/function_app.py`: タイマートリガー（毎時）+ HTTP トリガー（手動通知）
- `functions/shared/discord_notify.py`: Discord Bot API でチャンネルにメンション送信
- `NotificationSetting` の `scheduled` / `deadline` / `from_date` 各モードの条件評価
- Azure Functions のデプロイ設定
- `FUNCTIONS_URL` と `FUNCTIONS_KEY` を App Service の環境変数に設定して「今すぐ送信」ボタンを有効化
