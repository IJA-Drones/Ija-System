"""Read RedGPS into the configured database; --watch polls without an open panel."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask
from app.extensions import db
from app.modules.veiculos.redgps_sync import sync_redgps
from config import Config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    if not app.config["REDGPS_SYNC_ENABLED"]:
        parser.error("REDGPS_SYNC_ENABLED precisa estar habilitado no ambiente.")
    while True:
        with app.app_context():
            result = sync_redgps()
            print(json.dumps(result, ensure_ascii=False), flush=True)
        if not args.watch:
            return 1 if result.get("error") else 0
        time.sleep(app.config["REDGPS_POLL_INTERVAL_SECONDS"])


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
