import logging
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

_DISCORD_API = "https://discord.com/api/v10"


def _post_to_channel(channel_id: str, content: str, bot_token: str) -> bool:
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


def notify_event(event_id: str, db, bot_token: str, app_base_url: str) -> bool:
    from app.models.event import Event, EventStatus
    from app.models.payment import PaymentStatus

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event or not event.notification_setting:
        logger.warning("Event %s: not found or has no notification setting", event_id)
        return False

    if event.status == EventStatus.completed:
        logger.info("Event %s: completed, skipping", event_id)
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


def run_all_notifications(db, bot_token: str, app_base_url: str) -> int:
    from app.models.notification import NotificationSetting

    now = datetime.utcnow()
    today = now.date()
    sent = 0

    settings_list = db.query(NotificationSetting).all()
    for ns in settings_list:
        if not ns.discord_channel_id:
            continue
        try:
            if _should_notify(ns, now, today):
                if notify_event(ns.event_id, db, bot_token, app_base_url):
                    sent += 1
        except Exception:
            logger.exception("Error processing event %s", ns.event_id)

    return sent
