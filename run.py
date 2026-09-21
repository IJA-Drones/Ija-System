import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def _env_flag(name, default=False):
    default_value = "1" if default else "0"
    return os.getenv(name, default_value).strip().lower() in {"1", "true", "yes", "on"}


# The short timeout is only for the local debug entry point. Production uses
# app:create_app() and keeps SESSION_IDLE_TIMEOUT_MINUTES.
if __name__ == "__main__" and _env_flag("FLASK_DEBUG", default=True):
    os.environ.setdefault("FLASK_DEBUG", "1")
    os.environ.setdefault("SESSION_IDLE_TIMEOUT_SECONDS", "30")

os.environ.setdefault("CSS_BUNDLE_AUTO_BUILD", "1")

from scripts.build_css_bundle import build_css_bundle

build_css_bundle()

from app import create_app, db


app = create_app()


if __name__ == "__main__":
    if os.getenv("IJA_CREATE_ALL") == "1":
        with app.app_context():
            db.create_all()

    debug = _env_flag("FLASK_DEBUG", default=True)
    use_reloader = _env_flag("FLASK_USE_RELOADER", default=False)
    app.run(host="0.0.0.0", port=5002, debug=debug, use_reloader=use_reloader)
