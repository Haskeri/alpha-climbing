"""Серверная часть мобильного приложения «Alpha» — учёт восхождений альпинистского клуба."""
import logging
import os
import socket
import time
from logging.handlers import RotatingFileHandler

from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .models import db

__version__ = "1.0.0"


def _database_url():
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    data_dir = os.environ.get("ALPHA_DATA_DIR", os.path.join(os.getcwd(), "data"))
    os.makedirs(data_dir, exist_ok=True)
    return "sqlite:///" + os.path.join(data_dir, "alpha.db")


def _setup_logging(app):
    log_dir = os.environ.get("ALPHA_LOG_DIR", os.path.join(os.getcwd(), "logs"))
    os.makedirs(log_dir, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "alpha.log"), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    app.logger.handlers = [file_handler, stream_handler]
    app.logger.setLevel(logging.INFO)


def _wait_for_db(app, attempts=30, delay=2):
    for attempt in range(1, attempts + 1):
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError:
            app.logger.warning("БД недоступна, попытка %s/%s", attempt, attempts)
            time.sleep(delay)
    raise RuntimeError("Не удалось подключиться к базе данных")


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("ALPHA_SECRET_KEY", "dev-secret-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = _database_url()
    app.config["JSON_AS_ASCII"] = False
    app.json.ensure_ascii = False

    _setup_logging(app)
    db.init_app(app)

    from .api import api

    app.register_blueprint(api, url_prefix="/api")

    @app.after_request
    def cors(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        return response

    with app.app_context():
        _wait_for_db(app)
        db.create_all()
        if os.environ.get("ALPHA_SEED", "1") == "1":
            from .seed import seed_if_empty

            seed_if_empty(app)
        app.logger.info(
            "Alpha API %s запущен на %s, БД: %s",
            __version__,
            socket.gethostname(),
            db.engine.url.get_backend_name(),
        )
    return app
