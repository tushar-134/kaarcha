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


def app(environ, start_response):
    if "dbg=1" in environ.get("QUERY_STRING", ""):
        start_response("200 OK", [("Content-Type", "application/json")])
        keys = {k: str(v) for k, v in sorted(environ.items())
                if k in ("PATH_INFO", "QUERY_STRING", "REQUEST_METHOD", "SCRIPT_NAME")}
        return [json.dumps(keys, indent=1).encode()]
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
