"""Read RedGPS into the configured database; --watch polls without an open panel."""
import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask
from app.extensions import db
from app.modules.veiculos.redgps_sync import sync_redgps
from app.modules.veiculos.redgps_history import import_redgps_history
from app.clients.redgps_client import RedGPSError


def main(config_class=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--positions-only", action="store_true", help="Coletar somente posições, sem pré-carregar trajetos.")
    parser.add_argument("--history-date", type=date.fromisoformat, help="Recuperar um dia de rotas (AAAA-MM-DD).")
    parser.add_argument("--history-timezone", help="Fuso do histórico confirmado com a OLLOG, por exemplo America/Sao_Paulo ou UTC.")
    parser.add_argument("--plate", action="append", help="Limitar recuperação a esta placa; pode repetir.")
    args = parser.parse_args()
    if config_class is None:
        from config import Config
        config_class = Config
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    if not app.config["REDGPS_SYNC_ENABLED"]:
        parser.error("REDGPS_SYNC_ENABLED precisa estar habilitado no ambiente.")
    if args.history_date:
        if args.watch or not args.history_timezone:
            parser.error("Use --history-timezone com --history-date, sem --watch.")
        with app.app_context():
            try:
                result = import_redgps_history(args.history_date, args.history_timezone, args.plate)
            except (RedGPSError, ValueError, KeyError, SQLAlchemyError):
                print(json.dumps({"error": "Não foi possível recuperar o histórico; confira configuração, fuso e acesso ao provedor."}), flush=True)
                return 1
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return 0
    if args.history_timezone or args.plate:
        parser.error("--history-timezone e --plate exigem --history-date.")
    next_history = 0
    previous_day = None
    while True:
        with app.app_context():
            result = sync_redgps()
            if not args.positions_only and time.monotonic() >= next_history:
                from app.modules.veiculos.tracking_period import parse_tracking_period
                today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
                first = today - timedelta(days=1) if args.watch and previous_day != today else today
                period = parse_tracking_period({"start": f"{first.isoformat()}T00:00", "end": f"{today.isoformat()}T23:59"})
                try:
                    result["history"] = import_redgps_history(today, app.config.get("REDGPS_HISTORY_TIMEZONE", "America/Sao_Paulo"), period=period)
                    if result["history"].get("busy"):
                        next_history = time.monotonic() + 60
                    else:
                        next_history = time.monotonic() + max(60, int(app.config.get("REDGPS_HISTORY_SYNC_INTERVAL_SECONDS", 300)))
                        previous_day = today
                except (RedGPSError, ValueError, KeyError, SQLAlchemyError):
                    result["history"] = {"error": True}
                    next_history = time.monotonic() + 60
            print(json.dumps(result, ensure_ascii=False), flush=True)
        if not args.watch:
            return 1 if result.get("error") or result.get("history", {}).get("error") or result.get("history", {}).get("busy") else 0
        time.sleep(app.config["REDGPS_POLL_INTERVAL_SECONDS"])


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
