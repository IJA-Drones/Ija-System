"""Public Azul: fixed guides and session-bound narration, without private tools."""
import hashlib
import hmac
import json

from flask import current_app, jsonify, request, session, url_for
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.modules.chatbot import voice
from .chatbot import chat_token, consume_quota
from .institutional import OCEANO_AZUL_SUMMARY, OCEANO_AZUL_URL

PAGES = {
    'main.portal_cidadao', 'main.portal_cidadao_boletim_dengue', 'main.portal_contatos',
    'main.portal_relato_saude', 'main.portal_relato_saude_recibo', 'main.portal_acoes',
    'main.portal_acao', 'main.app_download', 'main.privacidade', 'main.app_movel',
}
WELCOME = ('Olá! Sou a AZUL. Posso ajudar com saúde, prevenção, vigilância e uso do Portal do Cidadão, '
           'além dos contatos da Prefeitura e do canal institucional da Oceano Azul. '
           'Escolha uma dúvida abaixo ou escreva sua pergunta. Você também pode registrar um relato por aqui.')
QUICK_ANSWERS = {
    'Como registrar um foco?': 'Abra Registrar relato. No Portal do Cidadão, o formulário guia você por cinco etapas: ocorrência, endereço, identificação, detalhes e revisão. Depois de conferir os dados e o consentimento, clique em Confirmar e enviar. Guarde o protocolo exibido após a confirmação.',
    'Posso enviar fotos?': 'Sim! Na etapa Detalhes do relato, você pode anexar até cinco fotos ou vídeos. Os anexos são opcionais e ajudam a equipe a entender o problema. Envie os arquivos pelo formulário de relato, não pela conversa.',
    'Quais dados preciso informar?': 'Informe o tipo de ocorrência, o foco, logradouro, número, bairro e cidade, além de nome completo, CPF e telefone com DDD. Para Aedes, selecione também o tipo de local. RG e CEP são opcionais. Preencha seus dados pessoais somente nos campos do formulário e confirme o consentimento antes de enviar.',
    'O que acontece depois do envio?': 'Após a confirmação, seu relato recebe um protocolo. A COVISA analisa as informações, encaminha à coordenadoria e esta define a UVIS responsável. A unidade avalia o atendimento. O envio não garante visita imediata nem prazo de execução. Ainda não há consulta pública do andamento pelo chatbot.',
}


def available():
    return voice.available() and current_app.config.get('PORTAL_AZUL_VOICE_ENABLED', True)


def serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='azul-public-narration-v1')


def session_fingerprint():
    return hashlib.sha256(chat_token().encode()).hexdigest()


def offer(text):
    if ('main.portal_azul_voice' not in current_app.view_functions or not available()
            or not isinstance(text, str) or not 0 < len(text) <= voice.MAX_TEXT):
        return None
    return voice.recordings.decorate({'url': url_for('main.portal_azul_voice'),
            'token': serializer().dumps({'session': session_fingerprint(), 'text': text})}, text)


def context():
    if request.endpoint not in PAGES or request.method != 'GET':
        return {'public_azul': False}
    mobile = request.endpoint == 'main.app_movel'
    home = url_for('main.app_movel') if mobile else url_for('main.portal_cidadao')
    report_url = home + ('#relatar-foco' if mobile else '#portal-relato')
    health_url = home + '#caso-suspeito' if mobile else url_for('main.portal_relato_saude')
    steps = []

    def add(title, body, links=None, question=None):
        steps.append({'title': title, 'body': body, 'links': links or [],
                      'question': question, 'speech': offer(title + '. ' + body)})

    add('Conheça os caminhos do cidadão',
        'Use o relato de foco para comunicar um problema no ambiente. Para informar '
        'suspeita de adoecimento, use o formulário específico. A Azul ajuda a encontrar '
        'esses caminhos; seus dados pessoais devem ficar nos formulários.',
        [{'label': 'Relatar foco', 'url': report_url}, {'label': 'Suspeita de adoecimento', 'url': health_url}])
    add('Registre um foco com revisão',
        'Escolha a ocorrência e a prefeitura responsável. Confira o endereço, preencha '
        'a identificação e acrescente detalhes ou anexos. Revise tudo e confirme o '
        'consentimento antes de enviar. Guarde o protocolo após a confirmação do sistema.',
        [{'label': 'Registrar relato', 'url': report_url}], 'Como registrar um foco?')
    add('Use o formulário de saúde',
        'Uma suspeita de adoecimento é um relato confidencial para triagem da vigilância. '
        'Ela não representa diagnóstico ou confirmação de caso. Preencha os campos do '
        'formulário específico; não envie informações pessoais ou de saúde pelo chat.',
        [{'label': 'Abrir formulário de saúde', 'url': health_url}])
    add('Confira o boletim e as fontes',
        'No boletim, escolha o município, a doença e o ano. Confira o período e a fonte '
        'apresentados antes de interpretar os números. Dados de demonstração aparecem '
        'identificados e não representam casos reais.',
        [{'label': 'Abrir boletim', 'url': url_for('main.portal_cidadao_boletim_dengue')}])
    add('Encontre os contatos publicados',
        'Consulte os canais publicados pela prefeitura para saber como entrar em contato '
        'com o serviço responsável. A disponibilidade dessas informações depende do '
        'cadastro público do município.',
        [{'label': 'Contatos das prefeituras', 'url': url_for('main.portal_contatos')}])
    add('Converse ou ouça a Azul',
        'Escreva uma dúvida sobre saúde, prevenção ou uso do portal. Nas respostas com '
        'áudio disponível, escolha Ouvir resposta. A voz é gerada por inteligência '
        'artificial e só começa quando você pede. Você pode interromper quando quiser.')
    return {'public_azul': True, 'public_azul_guide': steps,
            'public_azul_transcribe_url': url_for('main.portal_azul_transcribe')
                if available() and current_app.config.get('AZUL_CONVERSATION_ENABLED', True) else '',
            'public_azul_tutorial_url': url_for('main.azul_tutorial', publico='publico')
                if 'main.azul_tutorial' in current_app.view_functions else None,
            'public_azul_has_form': request.endpoint == 'main.portal_cidadao',
            'public_azul_report_url': report_url, 'portal_chat_token': chat_token(),
            'public_azul_voice': available(), 'public_azul_speech': {
                'welcome': offer(WELCOME), 'welcome_text': WELCOME,
                'institutional': offer(OCEANO_AZUL_SUMMARY),
                'quick': {question: {'answer': answer, 'speech': offer(answer)}
                          for question, answer in QUICK_ANSWERS.items()}},
            'oceano_azul_summary': OCEANO_AZUL_SUMMARY, 'oceano_azul_url': OCEANO_AZUL_URL}


def reply():
    expected = session.get('portal_chat_token', '')
    supplied = request.headers.get('X-Portal-Chat-Token', '')
    if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
        return jsonify(error='Recarregue a página para usar a voz da Azul.'), 403
    if not request.is_json:
        return jsonify(error='Envie a solicitação em JSON.'), 415
    raw = request.stream.read(voice.MAX_BODY + 1)
    if len(raw) > voice.MAX_BODY:
        return jsonify(error='Solicitação de áudio muito longa.'), 413
    try:
        payload = json.loads(raw)
        token = payload.get('token') if isinstance(payload, dict) else None
        if not isinstance(token, str) or len(token) > 20000:
            raise ValueError
        source = serializer().loads(token, max_age=voice.TOKEN_AGE)
    except (ValueError, UnicodeError, BadSignature):
        return jsonify(error='Este áudio expirou. Recarregue a página ou peça uma nova resposta.'), 400
    if (not isinstance(source, dict) or not isinstance(source.get('session'), str)
            or not hmac.compare_digest(source['session'], session_fingerprint())):
        return jsonify(error='Este áudio pertence a outra sessão. Recarregue a página.'), 403
    text = source.get('text')
    if not isinstance(text, str) or not 0 < len(text) <= voice.MAX_TEXT:
        return jsonify(error='Não foi possível preparar este áudio.'), 400
    if not available():
        return jsonify(error='A voz está indisponível. Você pode continuar lendo a resposta.'), 503
    return voice.deliver(text, ['public', source['session']], lambda: consume_quota(voice=True))
