import os

# Set test environment variables before any app modules are imported
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("DISCORD_CLIENT_ID", "test_client_id")
os.environ.setdefault("DISCORD_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("DISCORD_BOT_TOKEN", "test_bot_token")
os.environ.setdefault("DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback")
os.environ.setdefault("SESSION_SECRET", "test-secret-key-for-pytest-only")
