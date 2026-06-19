"""
Azure SQL → SQLite 移行スクリプト

使い方:
  SOURCE_DATABASE_URL="Driver={ODBC Driver 18 for SQL Server};Server=tcp:xxx.database.windows.net,1433;..." \
  TARGET_DATABASE_URL="sqlite:///./walican_migration.db" \
  python scripts/migrate_to_sqlite.py

SOURCE_DATABASE_URL: 現在の Azure SQL 接続文字列（App Service の環境変数と同じ値）
TARGET_DATABASE_URL: 出力先 SQLite ファイルパス（省略時: ./walican_migration.db）
"""

import os
import sys
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, make_transient

# --- 接続文字列を解決 ---
src_raw = os.environ.get("SOURCE_DATABASE_URL")
if not src_raw:
    print("ERROR: SOURCE_DATABASE_URL が設定されていません")
    sys.exit(1)

dst_raw = os.environ.get("TARGET_DATABASE_URL", "sqlite:///./walican_migration.db")

# Azure SQL の ODBC 接続文字列を SQLAlchemy URL に変換
if src_raw.startswith("Driver="):
    src_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(src_raw)}"
else:
    src_url = src_raw

src_engine = create_engine(src_url, echo=False)
dst_engine = create_engine(dst_raw, echo=False, connect_args={"check_same_thread": False})

# --- モデルを全てインポートしてスキーマを作成 ---
from app.database import Base
from app.models.user import User
from app.models.friend_group import FriendGroup, FriendGroupMember
from app.models.event import Event, EventParticipant
from app.models.expense import Expense, ExpenseParticipant
from app.models.payment import Payment
from app.models.notification import NotificationSetting
from app.models.user_guild import UserGuild
from app.models.bot_guild import BotGuild

print("SQLite スキーマを作成中...")
Base.metadata.create_all(dst_engine)

SrcSession = sessionmaker(bind=src_engine, autocommit=False, autoflush=False)
DstSession = sessionmaker(bind=dst_engine, autocommit=False, autoflush=False)

src = SrcSession()
dst = DstSession()

# FK 制約を一時的に無効化（SQLite）
dst.execute(text("PRAGMA foreign_keys = OFF"))
dst.commit()

# テーブルをFK依存順にコピー
TABLES = [
    User,
    FriendGroup,
    Event,
    BotGuild,
    UserGuild,
    FriendGroupMember,
    EventParticipant,
    Expense,
    ExpenseParticipant,
    Payment,
    NotificationSetting,
]

total = 0
for Model in TABLES:
    rows = src.query(Model).all()
    count = len(rows)
    print(f"  {Model.__tablename__}: {count} 件")
    for row in rows:
        src.expunge(row)
        make_transient(row)
        dst.merge(row)
    dst.commit()
    total += count

dst.execute(text("PRAGMA foreign_keys = ON"))
dst.commit()

src.close()
dst.close()

print(f"\n完了: 合計 {total} 件を移行しました")
print(f"出力ファイル: {dst_raw.replace('sqlite:///', '')}")
