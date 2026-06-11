from sessions import SessionManager


class FakeConn:
    def __init__(self, session_id=None):
        self.session_id = session_id


def test_take_pending_empty_returns_none():
    assert SessionManager().take_pending() is None


def test_take_pending_pops_in_fifo_order():
    mgr = SessionManager()
    a, b = FakeConn(), FakeConn()
    mgr.add_pending(a)
    mgr.add_pending(b)
    assert mgr.take_pending() is a
    assert mgr.take_pending() is b
    assert mgr.take_pending() is None


def test_mark_active_moves_from_pending_to_active():
    mgr = SessionManager()
    conn = FakeConn("sid-1")
    mgr.add_pending(conn)
    mgr.mark_active(conn)
    assert mgr.get_active("sid-1") is conn
    # No longer pending.
    assert mgr.take_pending() is None


def test_get_active_unknown_returns_none():
    assert SessionManager().get_active("nope") is None


def test_remove_pending():
    mgr = SessionManager()
    conn = FakeConn()
    mgr.add_pending(conn)
    mgr.remove(conn)
    assert mgr.take_pending() is None


def test_remove_active():
    mgr = SessionManager()
    conn = FakeConn("sid-2")
    mgr.mark_active(conn)
    mgr.remove(conn)
    assert mgr.get_active("sid-2") is None


def test_remove_does_not_evict_a_newer_session_with_same_id():
    # A stale connection being removed must not clear a newer active conn that
    # happens to share the same session_id.
    mgr = SessionManager()
    old = FakeConn("same-id")
    new = FakeConn("same-id")
    mgr.mark_active(old)
    mgr.mark_active(new)  # replaces old in the active map
    mgr.remove(old)       # removing the stale one must leave `new` in place
    assert mgr.get_active("same-id") is new
