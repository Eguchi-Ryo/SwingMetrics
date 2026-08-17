from flask import Flask

from app.routes.main import main_bp


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["JSON_SORT_KEYS"] = False
    app.config["SECRET_KEY"] = "swingmetrics-dev-secret-key"
    app.register_blueprint(main_bp)
    return app
