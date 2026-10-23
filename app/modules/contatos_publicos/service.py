"""One explicitly published municipal directory, shared by the portal and Azul."""
import re
from urllib.parse import urlsplit, quote
from datetime import timezone
from zoneinfo import ZoneInfo
from flask import current_app
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models import Prefeitura, PrefeituraContatoPublico, PrefeituraContatoHistorico
from app.modules.consultas.mail import validate_recipient

FIELDS = ('telefone', 'whatsapp', 'instagram', 'email', 'horario', 'servicos')


def schema_ready():
    if 'sqlalchemy' not in current_app.extensions:
        return False
    return inspect(db.session.connection()).has_table(PrefeituraContatoPublico.__tablename__)


def snapshot(setting):
    return {**{key: getattr(setting, key, '') if setting else '' for key in FIELDS},
            'publicado': bool(setting and setting.publicado)}


def phone(value, label):
    if not value:
        return ''
    if not re.fullmatch(r'[+\d\s().-]+', value, re.ASCII):
        raise ValueError(f'Informe {label} com DDD, usando apenas números e pontuação de telefone.')
    digits = re.sub(r'\D', '', value)
    if len(digits) in (12, 13) and digits.startswith('55'):
        digits = digits[2:]
    if len(digits) not in (10, 11) or digits.startswith('0'):
        raise ValueError(f'Informe {label} brasileiro com DDD (10 ou 11 dígitos).')
    return '55' + digits


def instagram_handle(value):
    if not value:
        return ''
    if value.startswith(('https://', 'http://')):
        try:
            url = urlsplit(value)
            if url.scheme != 'https' or url.hostname not in ('instagram.com', 'www.instagram.com') or url.username or url.password or url.port or url.query or url.fragment:
                raise ValueError()
            value = url.path.strip('/')
        except ValueError:
            raise ValueError('Informe o @perfil ou o endereço HTTPS do perfil no Instagram, sem parâmetros.') from None
    value = value.removeprefix('@')
    if not re.fullmatch(r'[A-Za-z0-9_](?:[A-Za-z0-9_.]{0,28}[A-Za-z0-9_])?', value) or '..' in value or value.lower() in ('p', 'reel', 'reels', 'stories', 'explore', 'accounts', 'direct'):
        raise ValueError('Informe um perfil válido do Instagram, com até 30 caracteres.')
    return value


def validate(form):
    values = {}
    for field in FIELDS:
        value = (form.get(field) or '').strip()
        if len(value) > {'horario': 300, 'servicos': 6000}.get(field, 254):
            raise ValueError('Um dos campos excedeu o tamanho permitido. Confira o formulário.')
        if any(ord(c) < 32 and c not in '\n\t' for c in value):
            raise ValueError('O texto contém caracteres inválidos.')
        values[field] = value
    values['telefone'] = phone(values['telefone'], 'o telefone')
    values['whatsapp'] = phone(values['whatsapp'], 'o WhatsApp')
    values['instagram'] = instagram_handle(values['instagram'])
    if values['email']:
        validate_recipient(values['email'])
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", values['email']):
            raise ValueError('Informe um e-mail institucional válido, sem parâmetros ou endereços adicionais.')
    values['publicado'] = form.get('publicado') == '1'
    if values['publicado'] and not any(values[k] for k in ('telefone', 'whatsapp', 'instagram', 'email')):
        raise ValueError('Cadastre pelo menos um canal de contato antes de publicar.')
    return values


def save(setting, prefeitura_id, user, form):
    from sqlalchemy.orm.exc import StaleDataError
    value = form.get('versao', '')
    if not value.isascii() or not value.isdecimal() or len(value) > 10:
        raise ValueError('Recarregue a página antes de salvar.')
    if int(value) != (setting.versao if setting else 0):
        raise StaleDataError()
    values = validate(form)
    before = snapshot(setting)
    if setting is None:
        setting = PrefeituraContatoPublico(prefeitura_id=prefeitura_id)
        db.session.add(setting)
    for key, value in values.items():
        setattr(setting, key, value)
    setting.atualizado_por_id = user.id
    db.session.add(PrefeituraContatoHistorico(prefeitura_id=prefeitura_id, usuario_id=user.id,
                                            antes=before, depois=values))
    db.session.commit()


def display_phone(value):
    if not value:
        return ''
    local = value[2:]
    return f'({local[:2]}) {local[2:-4]}-{local[-4:]}'


def public_directory():
    """Allowlist only published fields. Never fall back to private report emails."""
    try:
        if not schema_ready():
            return {'disponivel': False, 'prefeituras': []}
        rows = db.session.query(Prefeitura, PrefeituraContatoPublico).outerjoin(
            PrefeituraContatoPublico, PrefeituraContatoPublico.prefeitura_id == Prefeitura.id
        ).filter(Prefeitura.ativa.is_(True)).order_by(Prefeitura.nome, Prefeitura.id).all()
        cities = []
        for city, setting in rows:
            data = {'id': city.id, 'nome': city.nome, 'publicado': bool(setting and setting.publicado)}
            if data['publicado']:
                data.update({k: getattr(setting, k) for k in FIELDS})
                data.update(email_url='mailto:' + quote(setting.email, safe='@') if setting.email else '',
                            telefone_exibicao=display_phone(setting.telefone), whatsapp_exibicao=display_phone(setting.whatsapp),
                            instagram_url=f'https://www.instagram.com/{setting.instagram}/' if setting.instagram else '',
                            whatsapp_url=f'https://wa.me/{setting.whatsapp}' if setting.whatsapp else '',
                            atualizado_em=setting.atualizado_em.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M'))
            cities.append(data)
        return {'disponivel': True, 'prefeituras': cities}
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning('Diretório público municipal temporariamente indisponível.')
        return {'disponivel': False, 'prefeituras': []}
