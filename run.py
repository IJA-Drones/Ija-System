import os

from app import create_app, db


app = create_app()


if __name__ == "__main__":
    if os.getenv("IJA_CREATE_ALL") == "1":
        with app.app_context():
            db.create_all()

    app.run(host="0.0.0.0", port=5001, debug=True)
