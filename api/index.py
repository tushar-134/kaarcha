"""Vercel serverless entry: expose the Flask app as a WSGI handler.

Vercel rewrites everything to /api/index.py, so the function sees
PATH_INFO=/api/index.py and the original URL path only in the ?p= query
parameter that vercel.json adds. Restore PATH_INFO from it.
"""
import json
import os
import sys
from urllib.parse import parse_qsl, urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

flask_app = create_app(db_path="/tmp/kharcha.db")

# Every serverless instance has its own /tmp database. Start each one with the
# same default members so instances agree on member ids even before any request.
def _ensure_default_members():
    import sqlite3
    from datetime import datetime, timezone
    con = sqlite3.connect("/tmp/kharcha.db")
    try:
        if con.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 0:
            now = datetime.now(timezone.utc).isoformat()
            for n in ("Tushar", "Nigamananda"):
                con.execute("INSERT OR IGNORE INTO members (name, created_at) VALUES (?, ?)", (n, now))
            con.commit()
    finally:
        con.close()

_ensure_default_members()


def app(environ, start_response):
    pairs = parse_qsl(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    path = None
    rest = []
    for k, v in pairs:
        if k == "p" and path is None:
            path = v
        else:
            rest.append((k, v))
    if path and path.startswith("/"):
        environ["PATH_INFO"] = path
        environ["QUERY_STRING"] = urlencode(rest)
    return flask_app(environ, start_response)
