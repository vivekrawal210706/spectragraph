"""SpectraGraph Flask application package."""


def create_app():
    """Application factory for SpectraGraph (also exposed on the app package for Gunicorn)."""
    from flask import Flask
    from app.routes import main
    from db.database import init_db

    flask_app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    flask_app.config["SECRET_KEY"] = "spectragraph-dev-key"
    flask_app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload
    flask_app.register_blueprint(main)
    with flask_app.app_context():
        init_db()
    return flask_app
