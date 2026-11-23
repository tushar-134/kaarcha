"""Kharcha Split backend - Flask app factory."""
import os

from flask import Flask, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException

from .db import close_db, init_db
from .routes import api


def create_app(db_path=None):
    app = Flask(__name__)
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kharcha.db")
    app.config["DB_PATH"] = db_path

    app.register_blueprint(api)
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "integration", "frontend")

    @app.get("/")
    def frontend_index():
        return send_from_directory(frontend_dir, "index.html")

    @app.get("/<any('app.js', 'api.js', 'styles.css'):asset>")
    def frontend_asset(asset):
        return send_from_directory(frontend_dir, asset)


    @app.errorhandler(HTTPException)
    def http_error(err):
        return jsonify({"error": {"code": "http_error", "message": err.description}}), err.code


    @app.after_request
    def add_cors_headers(response):
        # Local demo only: allow any origin so the peer's dev frontend can call the API.
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

    return app
