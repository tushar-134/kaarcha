#!/usr/bin/env python3
"""Run the Kharcha Split API locally: python3 run.py [--port 5000]"""
import argparse

from app import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--db", default=None, help="SQLite file path (default: ./kharcha.db)")
    args = parser.parse_args()

    app = create_app(db_path=args.db)
    app.run(host="127.0.0.1", port=args.port, debug=False)
