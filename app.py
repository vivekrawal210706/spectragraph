"""Flask application entry point for SpectraGraph."""

from flask import Flask
from app.routes import main
from db.database import init_db


def create_app():
    """Application factory for SpectraGraph."""
    app = Flask(
        __name__,
        template_folder="app/templates",
        static_folder="app/static",
    )
    app.config["SECRET_KEY"] = "spectragraph-dev-key"
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload
    app.register_blueprint(main)
    with app.app_context():
        init_db()
    return app


if __name__ == "__main__":
    import os
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
