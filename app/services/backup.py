import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

RETAIN_DAYS = 7


def run_backup(db_path: str) -> str | None:
    """Create a dated SQLite backup and delete copies older than RETAIN_DAYS.

    Returns the backup file path on success, None on failure.
    Only operates on SQLite databases; silently skips other DB types.
    """
    src = Path(db_path)
    if not src.exists():
        logger.warning("backup: source not found: %s", db_path)
        return None

    backup_dir = src.parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    backup_path = backup_dir / f"walican_{today}.db"

    try:
        src_conn = sqlite3.connect(str(src))
        dst_conn = sqlite3.connect(str(backup_path))
        src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
    except Exception:
        logger.exception("backup: failed to write %s", backup_path)
        return None

    logger.info("backup: created %s", backup_path)
    _purge_old_backups(backup_dir)
    return str(backup_path)


def _purge_old_backups(backup_dir: Path) -> None:
    cutoff = datetime.utcnow() - timedelta(days=RETAIN_DAYS)
    for f in backup_dir.glob("walican_*.db"):
        try:
            date_str = f.stem.removeprefix("walican_")
            if datetime.strptime(date_str, "%Y-%m-%d") < cutoff:
                f.unlink()
                logger.info("backup: deleted %s", f.name)
        except (ValueError, OSError):
            pass
