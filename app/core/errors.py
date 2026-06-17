import uuid

from flask import current_app, jsonify, render_template, request
from werkzeug.exceptions import HTTPException


def _error_payload(code: int):
    defaults = {
        400: ("Requisicao invalida", "A solicitacao nao pode ser processada. Verifique os dados e tente novamente."),
        401: ("Nao autenticado", "Voce precisa fazer login para continuar."),
        403: ("Acesso negado", "Voce nao tem permissao para acessar este recurso."),
        404: ("Pagina nao encontrada", "O endereco acessado nao existe ou foi movido."),
        405: ("Metodo nao permitido", "Essa acao nao e permitida para esta rota."),
        408: ("Tempo esgotado", "A solicitacao demorou demais. Tente novamente."),
        409: ("Conflito", "Houve um conflito ao processar sua solicitacao."),
        410: ("Recurso indisponivel", "Esse conteudo nao esta mais disponivel."),
        415: ("Midia nao suportada", "Formato de arquivo ou dados nao suportado."),
        422: ("Nao foi possivel processar", "Verifique os campos informados e tente novamente."),
        429: ("Muitas tentativas", "Voce fez muitas solicitacoes em pouco tempo. Aguarde e tente novamente."),
        500: ("Erro interno", "Ocorreu um erro no servidor. Tente novamente em instantes."),
        502: ("Gateway invalido", "Servico temporariamente indisponivel. Tente novamente."),
        503: ("Servico indisponivel", "Servico em manutencao ou sobrecarregado. Tente novamente mais tarde."),
    }
    return defaults.get(code, ("Ocorreu um problema", "Nao foi possivel concluir sua solicitacao no momento. Tente novamente."))


def _render_error(code: int, titulo=None, mensagem=None):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())[:8]
    if not titulo or not mensagem:
        default_title, default_message = _error_payload(code)
        titulo = titulo or default_title
        mensagem = mensagem or default_message

    if _wants_json_response():
        return jsonify({
            "success": False,
            "error": mensagem,
            "code": code,
            "request_id": request_id,
        }), code

    return render_template(
        "erro.html",
        codigo=code,
        titulo=titulo,
        mensagem=mensagem,
        request_id=request_id,
    ), code


def _wants_json_response():
    if request.path.startswith("/api/") or "/api/" in request.path:
        return True
    if request.is_json:
        return True
    return (
        request.accept_mimetypes["application/json"]
        >= request.accept_mimetypes["text/html"]
    )


def register_error_handlers(bp):
    @bp.app_errorhandler(404)
    def pagina_nao_encontrada(e):
        return _render_error(
            404,
            titulo="Pagina nao encontrada",
            mensagem="Ops! A pagina que voce esta procurando nao existe ou foi movida.",
        )

    @bp.app_errorhandler(500)
    def erro_interno(e):
        return _render_error(
            500,
            titulo="Erro Interno do Servidor",
            mensagem="Desculpe, algo deu errado do nosso lado. Tente novamente mais tarde.",
        )

    @bp.app_errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        return _render_error(e.code or 500)

    @bp.app_errorhandler(Exception)
    def handle_exception(e: Exception):
        try:
            current_app.logger.exception(e)
        except Exception:
            pass
        return _render_error(500)
