"""In-memory registry of app connections and their (activated) sessions.

A connection starts *pending* (the app has connected but no browser has claimed
it via the form yet). When a browser submits a matching session ID it becomes
*active*, keyed by that ID. Everything lives only as long as the app connection.
"""


class SessionManager:
    def __init__(self) -> None:
        self._pending: list = []          # connections awaiting activation
        self._active: dict = {}           # session_id -> connection

    def add_pending(self, conn) -> None:
        self._pending.append(conn)

    def take_pending(self):
        """Pop one pending app connection (assumes a single app per server)."""
        return self._pending.pop(0) if self._pending else None

    def mark_active(self, conn) -> None:
        if conn in self._pending:
            self._pending.remove(conn)
        self._active[conn.session_id] = conn

    def get_active(self, session_id: str):
        return self._active.get(session_id)

    def remove(self, conn) -> None:
        if conn in self._pending:
            self._pending.remove(conn)
        sid = getattr(conn, "session_id", None)
        if sid and self._active.get(sid) is conn:
            del self._active[sid]
