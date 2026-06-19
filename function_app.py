import logging
import os

import azure.functions as func
import httpx

logger = logging.getLogger(__name__)
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.timer_trigger(schedule="0 0 0 * * *", arg_name="timer", run_on_startup=False)
def notify_timer(timer: func.TimerRequest) -> None:
    """Timer trigger: runs daily at 00:00 UTC (09:00 JST)."""
    app_base_url = os.environ.get("APP_BASE_URL", "").rstrip("/")
    internal_notify_key = os.environ.get("INTERNAL_NOTIFY_KEY", "")

    if not app_base_url or not internal_notify_key:
        logger.error("APP_BASE_URL or INTERNAL_NOTIFY_KEY not set")
        return

    try:
        resp = httpx.post(
            f"{app_base_url}/internal/notify",
            headers={"x-internal-key": internal_notify_key},
            timeout=30,
        )
        resp.raise_for_status()
        logger.info("notify_timer: %s", resp.text)
    except httpx.HTTPError as e:
        logger.error("notify_timer failed: %s", e)
