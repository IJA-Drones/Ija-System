"""Read battery cycle reports from an existing DJI Cloud API MQTT connection."""
import argparse
import logging
import os
import re
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    from flask import Flask
    from paho.mqtt import client as mqtt
    from sqlalchemy.exc import SQLAlchemyError

    from app.extensions import db
    from app.modules.equipamentos.dji_battery_sync import sync_battery_cycles
    from config import Config

    host = os.environ.get('DJI_MQTT_HOST', '').strip()
    username = os.environ.get('DJI_MQTT_USERNAME', '')
    password = os.environ.get('DJI_MQTT_PASSWORD', '')
    serials = {value.strip() for value in os.environ.get('DJI_MQTT_AIRCRAFT_SNS', '').split(',') if value.strip()}
    if not host or not username or not password or not serials:
        parser.error('Configure DJI_MQTT_HOST, DJI_MQTT_USERNAME, DJI_MQTT_PASSWORD e DJI_MQTT_AIRCRAFT_SNS.')
    if any(not re.fullmatch(r'[A-Za-z0-9-]{1,100}', serial) for serial in serials):
        parser.error('DJI_MQTT_AIRCRAFT_SNS deve conter números de série, separados por vírgula.')
    try:
        port = int(os.environ.get('DJI_MQTT_PORT', '8883'))
        if not 0 < port <= 65535:
            raise ValueError()
    except ValueError:
        parser.error('DJI_MQTT_PORT deve ser uma porta válida.')

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logger = logging.getLogger('dji-batteries')
    topics = {f'thing/product/{serial}/osd': serial for serial in serials}
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            logger.warning('O broker recusou a conexão MQTT.')
            return
        result, _ = client.subscribe([(topic, 0) for topic in sorted(topics)])
        if result != mqtt.MQTT_ERR_SUCCESS:
            logger.error('Não foi possível solicitar os tópicos de telemetria DJI.')

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        if any(code.is_failure for code in reason_codes):
            logger.warning('O broker negou acesso a um ou mais tópicos DJI. Confira as permissões de leitura.')
        else:
            logger.info('Aguardando telemetria de %s aeronave(s).', len(topics))

    def on_message(client, userdata, message):
        aircraft = topics.get(message.topic)
        if not aircraft or message.retain:
            return
        with app.app_context():
            try:
                updated = sync_battery_cycles(aircraft, message.payload)
            except SQLAlchemyError as exc:
                db.session.rollback()
                logger.error('Falha ao salvar a leitura DJI (%s).', type(exc).__name__)
                return
            if updated:
                logger.info('Ciclos atualizados para %s bateria(s).', updated)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(username, password)
    client.tls_set_context(ssl.create_default_context(cafile=os.environ.get('DJI_MQTT_CA_FILE') or None))
    client.reconnect_delay_set(min_delay=1, max_delay=120)
    client.on_connect, client.on_subscribe, client.on_message = on_connect, on_subscribe, on_message
    client.connect_async(host, port, keepalive=60)
    try:
        client.loop_forever(retry_first_connection=True)
    except KeyboardInterrupt:
        client.disconnect()


if __name__ == '__main__':
    main()
