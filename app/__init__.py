from flask import Flask

from app.config import Config, INSTANCE_DIR
from app.extensions import csrf, db


def create_app():
    app = Flask(
        __name__,
        instance_path=str(INSTANCE_DIR),
        instance_relative_config=True,
    )

    app.config.from_object(Config)

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)

    @app.route("/")
    def index():
        return "Lido Masa Takip Sistemi çalışıyor."

    return app