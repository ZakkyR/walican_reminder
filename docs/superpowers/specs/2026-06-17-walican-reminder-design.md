# Walican Reminder — 設計ドキュメント

作成日: 2026-06-17

## 概要

旅行・イベントの割り勘・立替精算を管理するWebアプリ。Discord OAuthで認証し、未払いメンバーへのリマインドをDiscord Botがチャンネルに通知する。WebアプリはAzure App Service 無料プラン、通知機能はAzure Functions（無料枠）で運用する。

---

## アーキテクチャ

```
[ブラウザ]
  │  HTMX (部分更新)
  ▼
[Azure App Service F1 - 無料プラン]
  ├─ FastAPI + uvicorn (ASGIサーバー)
  │   ├─ Jinja2 テンプレート (HTML レスポンス)
  │   ├─ Discord OAuth2 認証
  │   └─ REST API エンドポイント
  └─ SQLAlchemy ORM

[Azure Functions - 無料枠（月100万回）]
  ├─ タイマートリガー（毎時0分）
  │   └─ NotificationSetting を確認して条件に合う通知を送信
  └─ HTTPトリガー（手動通知用）
      └─ Web UI の「今すぐ送信」ボタンから呼び出される

         ↓ 共有
[Azure SQL Database - 無料枠 32GB]

[Discord API]
  ├─ OAuth2 (ログイン認証)
  └─ Bot (チャンネルへのメンション通知)
```

### 技術スタック

| レイヤー | 技術 |
|---|---|
| バックエンド (Web) | Python 3.12 / FastAPI |
| テンプレート | Jinja2 |
| フロントエンド | HTMX + Vanilla CSS（レスポンシブ） |
| ORM | SQLAlchemy 2.x |
| DB | Azure SQL Database（無料枠） |
| 認証 | Discord OAuth2 (authlib) |
| 通知スケジューラ | Azure Functions（Python） |
| Bot通知 | discord.py（Azure Functions 内） |
| ホスティング (Web) | Azure App Service F1（無料） |
| ホスティング (通知) | Azure Functions 従量課金（無料枠内） |

### Azure リソース構成と制約

| リソース | プラン | 制約 |
|---|---|---|
| App Service | F1（無料） | RAM 1GB・CPU共有・アイドルスリープあり |
| Azure Functions | 従量課金 | 月100万回・400,000 GB-seconds まで無料 |
| Azure SQL Database | 無料枠 | 32GB まで無料 |

- App Service はアイドルスリープするが、通知は Functions が担うため影響なし
- Functions のタイマートリガーはスリープに関係なく定刻起動する

---

## データモデル

```sql
User
  id                  UUID PK
  discord_id          VARCHAR(20) UNIQUE
  discord_username    VARCHAR(100)
  discord_avatar_url  TEXT
  created_at          DATETIME

FriendGroup（仲間グループ）
  id                  UUID PK
  name                VARCHAR(100)
  created_by          UUID FK → User
  created_at          DATETIME

FriendGroupMember
  friend_group_id     UUID FK → FriendGroup
  user_id             UUID FK → User
  PRIMARY KEY (friend_group_id, user_id)

Event（イベント）
  id                  UUID PK
  name                VARCHAR(200)
  description         TEXT
  payment_deadline    DATE (nullable)
  created_by          UUID FK → User
  status              ENUM: active / completed
  created_at          DATETIME

EventParticipant（イベント参加者）
  event_id            UUID FK → Event
  user_id             UUID FK → User
  PRIMARY KEY (event_id, user_id)

Expense（支出項目）
  id                  UUID PK
  event_id            UUID FK → Event
  title               VARCHAR(200)
  total_amount        DECIMAL(12, 0)
  paid_by             UUID FK → User  ← 立替した人
  created_at          DATETIME

ExpenseParticipant（支出の負担者）
  expense_id          UUID FK → Expense
  user_id             UUID FK → User
  custom_amount       DECIMAL(12, 0) nullable  ← NULL = 均等割り
  PRIMARY KEY (expense_id, user_id)

Payment（精算レコード）
  id                  UUID PK
  event_id            UUID FK → Event
  from_user_id        UUID FK → User  ← 支払う人
  to_user_id          UUID FK → User  ← 受け取る人（立替した人）
  amount              DECIMAL(12, 0)
  status              ENUM: pending / paid
  paid_at             DATETIME nullable

NotificationSetting（通知設定）
  id                  UUID PK
  event_id            UUID FK → Event UNIQUE
  discord_channel_id  VARCHAR(20)
  mode                ENUM: scheduled / deadline / from_date
  schedule_cron       VARCHAR(50) nullable   ← "0 12 * * 1"（毎週月曜12時）
  deadline_days_before INT nullable          ← 支払期限N日前から通知
  deadline_days_after  INT nullable          ← 支払期限N日後まで通知
  notify_from_date    DATE nullable          ← この日以降に通知開始
  notify_interval_days INT nullable          ← from_dateモード時のN日間隔
  last_notified_at    DATETIME nullable      ← 重複送信防止用
```

---

## 精算計算ロジック

1. 各 `Expense` について参加者の負担額を算出
   - `custom_amount` が設定されている参加者はその金額
   - NULL の参加者は `(total_amount - Σcustom_amount) / NULL参加者数` で均等割り
2. 各参加者の「受け取り額（立替）」と「支払い額（負担）」を集計
3. 差額（債権・債務）から最小送金数アルゴリズムで `Payment` レコードを生成
4. 支出追加・編集・削除のたびに精算額を再計算。`status=paid` の `Payment` はそのまま保持し、残債務を新しい `Payment` レコードとして追加・更新する（既払い分を取り消さない）

---

## 機能一覧

### 認証
- Discord OAuth2 ログイン / ログアウト
- セッション管理（サーバーサイドセッション）

### 仲間グループ管理
- グループ一覧・作成・編集・削除
- Discordユーザー名で検索してメンバー追加・削除

### イベント管理
- イベント一覧（ホーム）：カードリスト形式、ステータス（未払い人数）表示
- イベント作成：名前・説明・支払期限を入力、仲間グループ一括追加 or ユーザー個別追加
- イベント編集・削除
- イベント完了マーク

### 支出管理
- 支出追加（タイトル・金額・立替者・参加者）
- 参加者ごとのカスタム負担額指定（未指定は均等割り）
- 支出編集・削除
- 精算額の自動再計算

### 精算ステータス管理
- 精算一覧：誰が誰にいくら払うかを一覧表示
- 「支払済み」マークのON/OFF
- 全員支払済みでイベントを完了状態に変更

### Discord通知（Azure Functions で実装）
- 通知設定（チャンネルID・モード）をイベントごとに設定
- **scheduledモード**：cron式に従って定期通知（毎時タイマーが条件評価）
- **deadlineモード**：支払期限のN日前 〜 N日後の期間に毎日通知
- **from_dateモード**：指定日以降、N日間隔で通知（全員支払済みで自動停止）
- 手動通知ボタン（Functions の HTTP トリガーを呼び出す）
- 通知メッセージ：未払いメンバーをメンション付きで列挙
- `last_notified_at` で重複送信を防止

---

## 画面構成

```
GET  /                        ホーム（イベント一覧カード）
GET  /login                   Discordログインリダイレクト
GET  /auth/callback           Discord OAuth コールバック
GET  /logout                  ログアウト

GET  /groups                  仲間グループ一覧
GET  /groups/new              仲間グループ作成フォーム
POST /groups                  仲間グループ作成
GET  /groups/{id}             仲間グループ詳細・メンバー管理
POST /groups/{id}/members     メンバー追加
DELETE /groups/{id}/members/{uid}  メンバー削除

GET  /events/new              イベント作成フォーム
POST /events                  イベント作成
GET  /events/{id}             イベント詳細（タブ：支出 / 精算状況 / 通知設定）
POST /events/{id}/expenses         支出追加
PUT  /events/{id}/expenses/{eid}   支出編集
DELETE /events/{id}/expenses/{eid} 支出削除
POST /events/{id}/payments/{pid}/pay  支払済みマーク
POST /events/{id}/complete    イベント完了
```

---

## Azure Functions 設計

### タイマートリガー（毎時0分）

全イベントの `NotificationSetting` を DB から取得し、以下を評価して通知する：

- **scheduledモード**：cron式をパースし「今が送信すべき時刻か」を判定
- **deadlineモード**：`payment_deadline - deadline_days_before ≤ 今日 ≤ payment_deadline + deadline_days_after` を判定
- **from_dateモード**：`notify_from_date ≤ 今日` かつ `(今日 - last_notified_at) ≥ notify_interval_days` を判定

重複防止：送信後に `last_notified_at` を更新。全員支払済みのイベントはスキップ。

### HTTPトリガー（手動通知）

- Web UI の「今すぐ送信」ボタンが `POST /api/notify/{event_id}` を呼び出す
- Functions が DB からイベント情報を取得して Discord へ即時送信
- App Service から Functions への呼び出しは Functions のアクセスキーで保護

---

## セキュリティ

- セッションはサーバーサイドで管理（クッキーにはセッションIDのみ）
- イベント・グループの閲覧・操作は参加者のみ可能（参加者チェックをAPIレイヤーで実施）
- Discord Bot Token・OAuth クライアントシークレットは Azure 環境変数で管理
- Functions の HTTP トリガーはアクセスキー認証で保護

---

## 非機能要件

- レスポンシブデザイン（スマートフォン・PC両対応）
- Azure App Service F1 無料プラン内で動作（RAM 1GB・CPU 共有・ストレージ 1GB）
- Azure SQL Database 無料枠内で動作（32GB）
- Azure Functions 無料枠内で動作（月100万回・400,000 GB-seconds）
