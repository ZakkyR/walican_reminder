import sentry_sdk
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.config import settings
from app.routers import auth, home, groups, events, expenses, payments, notifications, api, servers, internal

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        send_default_pii=False,
    )

app = FastAPI(title="Walican Reminder")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(groups.router)
app.include_router(events.router)
app.include_router(expenses.router)
app.include_router(payments.router)
app.include_router(notifications.router)
app.include_router(api.router)
app.include_router(servers.router)
app.include_router(internal.router)
