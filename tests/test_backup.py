import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.services.backup import run_backup, RETAIN_DAYS


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()


def test_run_backup_creates_file(tmp_path):
    src = tmp_path / "walican.db"
    _make_db(src)

    result = run_backup(str(src))

    assert result is not None
    backup_file = Path(result)
    assert backup_file.exists()
    assert backup_file.parent == tmp_path / "backups"


def test_run_backup_file_contains_data(tmp_path):
    src = tmp_path / "walican.db"
    _make_db(src)

    result = run_backup(str(src))

    conn = sqlite3.connect(result)
    row = conn.execute("SELECT id FROM t").fetchone()
    conn.close()
    assert row == (1,)


def test_run_backup_purges_old_files(tmp_path):
    src = tmp_path / "walican.db"
    _make_db(src)

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    old_date = (datetime.utcnow() - timedelta(days=RETAIN_DAYS + 1)).strftime("%Y-%m-%d")
    old_file = backup_dir / f"walican_{old_date}.db"
    old_file.write_bytes(b"old")

    run_backup(str(src))

    assert not old_file.exists()


def test_run_backup_keeps_recent_files(tmp_path):
    src = tmp_path / "walican.db"
    _make_db(src)

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    recent_date = (datetime.utcnow() - timedelta(days=RETAIN_DAYS - 1)).strftime("%Y-%m-%d")
    recent_file = backup_dir / f"walican_{recent_date}.db"
    recent_file.write_bytes(b"recent")

    run_backup(str(src))

    assert recent_file.exists()


def test_run_backup_missing_source(tmp_path):
    result = run_backup(str(tmp_path / "nonexistent.db"))
    assert result is None


def test_backup_endpoint_requires_key(client):
    response = client.post("/internal/backup", headers={"x-internal-key": "wrong"})
    assert response.status_code == 403


def test_backup_endpoint_returns_path(auth_client, tmp_path):
    fake_db = tmp_path / "walican.db"
    _make_db(fake_db)

    with patch("app.routers.internal.settings") as mock_settings, \
         patch("app.routers.internal.run_backup", return_value=str(tmp_path / "backups" / "walican_2026-01-01.db")) as mock_backup:
        mock_settings.internal_notify_key = "secret"
        mock_settings.database_url = f"sqlite:///{fake_db}"
        response = auth_client.post(
            "/internal/backup",
            headers={"x-internal-key": "secret"},
        )

    assert response.status_code == 200
    assert "path" in response.json()
    mock_backup.assert_called_once()
