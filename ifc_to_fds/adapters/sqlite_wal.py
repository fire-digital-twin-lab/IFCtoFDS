"""Khởi tạo WAL khi nhiều tiến trình cùng mở cơ sở dữ liệu SQLite."""

import sqlite3
from time import sleep


def _is_busy(error: sqlite3.OperationalError) -> bool:
    code = getattr(error, "sqlite_errorcode", None)
    if code is not None:
        # Primary SQLite result codes: SQLITE_BUSY (5), SQLITE_LOCKED (6).
        return (code & 0xFF) in (5, 6)
    # Python 3.10 chưa cung cấp sqlite_errorcode.
    return any(word in str(error).lower() for word in ("locked", "busy"))


def enable_wal(connection: sqlite3.Connection) -> None:
    """Xác nhận WAL, thử lại hữu hạn khi tiến trình khác giữ khóa."""
    for attempt in range(6):
        try:
            mode = connection.execute("PRAGMA journal_mode;").fetchone()[0]
            if mode != "wal":
                mode = connection.execute("PRAGMA journal_mode=WAL;").fetchone()[0]
        except sqlite3.OperationalError as error:
            if attempt == 5 or not _is_busy(error):
                raise
            sleep(0.05 * 2**attempt)
        else:
            if mode != "wal":
                raise RuntimeError(f"SQLite refused WAL journal mode: {mode}")
            return
