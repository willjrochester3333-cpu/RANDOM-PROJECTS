"""Weather history in SQLite."""
import sqlite3
import threading
import time


class Store:
    def __init__(self, path: str):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._db:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS weather ("
                "ts INTEGER PRIMARY KEY, temp_c REAL, humidity REAL, pressure_hpa REAL)"
            )

    def add_weather(self, ts: float, temp_c: float, humidity: float, pressure_hpa: float) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO weather VALUES (?, ?, ?, ?)",
                (int(ts), temp_c, humidity, pressure_hpa),
            )

    def latest_weather(self) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT ts, temp_c, humidity, pressure_hpa FROM weather ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        return _row(row) if row else None

    def history(self, hours: float, max_points: int = 300) -> list[dict]:
        """Readings from the last `hours`, averaged into at most `max_points` buckets."""
        now = int(time.time())
        start = now - int(hours * 3600)
        bucket = max(60, int(hours * 3600 / max_points))
        with self._lock:
            rows = self._db.execute(
                "SELECT (ts / ?) * ?, AVG(temp_c), AVG(humidity), AVG(pressure_hpa) "
                "FROM weather WHERE ts >= ? GROUP BY ts / ? ORDER BY 1",
                (bucket, bucket, start, bucket),
            ).fetchall()
        return [_row(r) for r in rows]


def _row(r) -> dict:
    return {
        "ts": r[0],
        "temp_c": round(r[1], 1),
        "humidity": round(r[2], 1),
        "pressure_hpa": round(r[3], 1),
    }
