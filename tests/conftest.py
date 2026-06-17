import os

# Set test environment variables before any app modules are imported
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ.setdefault("DISCORD_CLIENT_ID", "test_client_id")
os.environ.setdefault("DISCORD_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("DISCORD_BOT_TOKEN", "test_bot_token")
os.environ.setdefault("DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback")
os.environ.setdefault("SESSION_SECRET", "test-secret-key-for-pytest-only")

import json
import base64
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
    """TestClient with session cookie set for the given user."""
    import itsdangerous
    from app.config import settings

    # Build the Starlette session cookie using itsdangerous.TimestampSigner
    # (matches starlette.middleware.sessions.SessionMiddleware internals)
    signer = itsdangerous.TimestampSigner(str(settings.session_secret))
    session_data = {"user_id": user.id}
    data = base64.b64encode(json.dumps(session_data).encode("utf-8"))
    signed = signer.sign(data).decode("utf-8")
    client.cookies.set("session", signed)
    return client
