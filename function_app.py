import logging
import os
from datetime import datetime, timedelta

import azure.functions as func

logger = logging.getLogger(__name__)
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

_DISCORD_API = "https://discord.com/api/v10"


def _get_session():
    from app.database import SessionLocal
    return SessionLocal()


def _post_to_channel(channel_id: str, content: str, bot_token: str) -> bool:
    import httpx
    try:
        resp = httpx.post(
            f"{_DISCORD_API}/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {bot_token}"},
            json={"content": content},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError as e:
        logger.error("Discord post failed: %s", e)
        return False


def _build_message(event, unpaid_payments: list, app_base_url: str) -> str:
    seen_ids: set[str] = set()
    mentions: list[str] = []
    for p in unpaid_payments:
        uid = p.from_user.discord_id
        if not p.from_user.is_guest and uid not in seen_ids:
            seen_ids.add(uid)
            mentions.append(f"<@{uid}>")

    lines = [f"\U0001f4b0 **{event.name}** に未払いがあります！", ""]
    for p in unpaid_payments:
        amount = int(p.amount)
        lines.append(
            f"  • {p.from_user.discord_username} → {p.to_user.discord_username}: ￥{amount:,}"
        )
    lines += ["", f"精算状況: <{app_base_url}/events/{event.id}?tab=payments>"]
    if mentions:
        lines += ["", " ".join(mentions) + " よろしくお願いします！"]
    return "\n".join(lines)


def _do_notify(event_id: str, db, bot_token: str, app_base_url: str) -> bool:
    from app.models.event import Event
    from app.models.payment import PaymentStatus

    from app.models.event import EventStatus
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event or not event.notification_setting:
        logger.warning("Event %s: not found or has no notification setting", event_id)
        return False

    if event.status == EventStatus.completed:
        logger.info("Event %s: completed, skipping notification", event_id)
        return False

    unpaid = [p for p in event.payments if p.status == PaymentStatus.pending]
    if not unpaid:
        logger.info("Event %s: no unpaid payments, skipping", event_id)
        return False

    content = _build_message(event, unpaid, app_base_url)
    ns = event.notification_setting
    success = _post_to_channel(ns.discord_channel_id, content, bot_token)
    if success:
        ns.last_notified_at = datetime.utcnow()
        db.commit()
    return success


def _check_cron(cron_expr: str | None, last_notified: datetime | None, now: datetime) -> bool:
    if not cron_expr:
        return False
    try:
        from croniter import croniter
        base = last_notified or datetime(1970, 1, 1)
        return croniter(cron_expr, base).get_next(datetime) <= now
    except Exception as e:
        logger.warning("Invalid cron '%s': %s", cron_expr, e)
        return False


def _should_notify(ns, now: datetime, today) -> bool:
    from app.models.notification import NotificationMode

    if ns.mode == NotificationMode.scheduled:
        return _check_cron(ns.schedule_cron, ns.last_notified_at, now)

    if ns.mode == NotificationMode.deadline:
        event = ns.event
        if not (event and event.payment_deadline):
            return False
        days_before = ns.deadline_days_before or 0
        days_after = ns.deadline_days_after or 0
        start = event.payment_deadline - timedelta(days=days_before)
        end = event.payment_deadline + timedelta(days=days_after)
        if not (start <= today <= end):
            return False
        last = ns.last_notified_at
        return last is None or last.date() < today

    if ns.mode == NotificationMode.from_date:
        if not ns.notify_from_date or today < ns.notify_from_date:
            return False
        interval = ns.notify_interval_days or 1
        last = ns.last_notified_at
        if last is None:
            return True
        return last.date() < today or (today - last.date()).days >= interval

    return False


@app.route(route="notify/{event_id}", methods=["POST"])
def notify_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP trigger: POST /api/notify/{event_id}  —  called by the web app's send-now endpoint."""
    event_id = req.route_params.get("event_id", "")
    if not event_id:
        return func.HttpResponse("event_id required", status_code=400)

    bot_token = os.environ.get("DISCORD_BOT_TOKEN", "")
    app_base_url = os.environ.get("APP_BASE_URL", "").rstrip("/")
    if not bot_token or not app_base_url:
        logger.error("notify_http: DISCORD_BOT_TOKEN or APP_BASE_URL not set")
        return func.HttpResponse("Missing configuration", status_code=500)

    db = _get_session()
    try:
        sent = _do_notify(event_id, db, bot_token, app_base_url)
        return func.HttpResponse("sent" if sent else "skipped", status_code=200)
    except Exception:
        logger.exception("notify_http error for event %s", event_id)
        return func.HttpResponse("internal error", status_code=500)
    finally:
        db.close()


@app.timer_trigger(schedule="0 0 0 * * *", arg_name="timer", run_on_startup=False)
def notify_timer(timer: func.TimerRequest) -> None:
    """Timer trigger: runs daily at 00:00 UTC (09:00 JST) to check all notification settings."""
    bot_token = os.environ.get("DISCORD_BOT_TOKEN", "")
    app_base_url = os.environ.get("APP_BASE_URL", "").rstrip("/")
    if not bot_token or not app_base_url:
        logger.error("notify_timer: DISCORD_BOT_TOKEN or APP_BASE_URL not set")
        return

    from app.models.notification import NotificationSetting

    now = datetime.utcnow()
    today = now.date()

    db = _get_session()
    try:
        settings_list = db.query(NotificationSetting).all()
        for ns in settings_list:
            if not ns.discord_channel_id:
                continue
            try:
                if _should_notify(ns, now, today):
                    _do_notify(ns.event_id, db, bot_token, app_base_url)
            except Exception:
                logger.exception("Error processing event %s", ns.event_id)
    except Exception:
        logger.exception("notify_timer: DB query failed")
    finally:
        db.close()
