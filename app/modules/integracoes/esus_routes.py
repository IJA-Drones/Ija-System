"""Telas, API para terceiros e painel de agentes da integração e-SUS APS (PEC)."""

from datetime import date, timedelta
from functools import wraps

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import case, func

from app.extensions import db
from app.models import Prefeitura
from app.modules.gestao_ti.permissions import route_access
from app.modules.vigilancia.access import can_coordinate_field
from app.modules.vigilancia.results import municipality_ibge
from app.shared.access import is_admin_global_user
from app.shared.mail import cifrar
from . import esus
from .esus import EsusConfig, EsusDomicilio, EsusExecucao, EsusVisita

DESFECHO_LABEL = {"realizada": "Realizada", "recusada": "Recusada", "ausente": "Ausente", "nao_informado": "Não informado"}


def _coordenacao(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not (is_admin_global_user(current_user) or can_coordinate_field(current_user)) or not route_access(current_user, True):
            abort(403)
        return view(*args, **kwargs)
    return guarded


def _admin_global(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not is_admin_global_user(current_user) or not route_access(current_user, True):
            abort(403)
        return view(*args, **kwargs)
    return guarded


def _int(raw):
    return int(raw) if raw and raw.isascii() and raw.isdecimal() and len(raw) <= 10 else None


def _prefeitura(source=None):
    """Admin global escolhe a prefeitura; os demais ficam presos à própria."""
    raw = (source or request.args).get("prefeitura_id", "")
    if is_admin_global_user(current_user):
        if raw and _int(raw) is None:
            abort(400)
        return _int(raw)
    pid = getattr(current_user, "prefeitura_id", None)
    if not pid or (raw and raw != str(pid)):
        abort(403)
    return pid


def _periodo(args, padrao_dias=30, maximo=366):
    hoje = date.today()
    try:
        ate = date.fromisoformat(args.get("ate")) if args.get("ate") else hoje
        de = date.fromisoformat(args.get("de")) if args.get("de") else ate - timedelta(days=padrao_dias - 1)
    except ValueError:
        abort(400, description="Período inválido (use AAAA-MM-DD).")
    if de > ate:
        de, ate = ate, de
    return max(de, ate - timedelta(days=maximo)), ate


def _filtrar(query, args, de, ate):
    query = query.filter(EsusVisita.data >= de, EsusVisita.data <= ate)
    profissional = (args.get("profissional") or "").strip()[:255]
    if profissional:
        termo = profissional.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter((EsusVisita.profissional_cns == profissional) | EsusVisita.profissional_nome.ilike(f"%{termo}%", escape="\\"))
    if args.get("categoria") in {"ACS", "ACE"}:
        query = query.filter(EsusVisita.categoria == args["categoria"])
    if args.get("desfecho") in DESFECHO_LABEL:
        query = query.filter(EsusVisita.desfecho == args["desfecho"])
    if args.get("microarea"):
        query = query.filter(EsusVisita.microarea == args["microarea"][:3])
    if args.get("aedes") in {"1", "true", "sim"}:
        query = query.filter(EsusVisita.motivo_aedes.is_(True))
    return query


def _visita_json(v):
    return {"id": v.chave, "ficha_uuid": v.ficha_uuid, "data": v.data.isoformat(), "hora": v.hora, "turno": v.turno,
            "profissional": {"nome": v.profissional_nome, "cns": v.profissional_cns, "cbo": v.cbo, "categoria": v.categoria},
            "equipe": {"ine": v.equipe_ine, "nome": v.equipe_nome}, "unidade": {"cnes": v.unidade_cnes, "nome": v.unidade_nome},
            "microarea": v.microarea, "domicilio_uuid": v.domicilio_uuid, "tipo_imovel": v.tipo_imovel,
            "desfecho": v.desfecho, "motivos": v.motivos.split("; ") if v.motivos else [], "motivo_aedes": v.motivo_aedes,
            "latitude": v.latitude, "longitude": v.longitude, "origem": v.origem}


def _execucao_json(e):
    return {"id": e.id, "processo": e.processo, "forma": e.forma, "modo": e.modo, "status": e.status,
            "iniciado_em": e.iniciado_em.isoformat(timespec="seconds"),
            "finalizado_em": e.finalizado_em.isoformat(timespec="seconds") if e.finalizado_em else None,
            "lidos": e.lidos, "inseridos": e.inseridos, "atualizados": e.atualizados, "removidos": e.removidos,
            "erros": e.erros, "mensagem": e.mensagem}


def status_payload(cfg, limite=10):
    pid = cfg.prefeitura_id
    execucoes = EsusExecucao.query.filter_by(prefeitura_id=pid).order_by(EsusExecucao.id.desc()).limit(limite).all()
    ultima_ok = {p: EsusExecucao.query.filter_by(prefeitura_id=pid, processo=p, status="concluida").order_by(EsusExecucao.id.desc()).first()
                 for p in esus.PROCESSOS}
    visitas = db.session.query(func.count(EsusVisita.id), func.min(EsusVisita.data), func.max(EsusVisita.data),
                               func.count(func.distinct(EsusVisita.profissional_nome))).filter(EsusVisita.prefeitura_id == pid).one()
    return {"prefeitura_id": pid, "modo": cfg.modo, "ativo": cfg.ativo, "intervalo_min": cfg.intervalo_min,
            "em_execucao": esus.em_execucao(pid),
            "totais": {"visitas": visitas[0], "profissionais": visitas[3],
                       "domicilios": EsusDomicilio.query.filter_by(prefeitura_id=pid).count(),
                       "primeira_visita": visitas[1].isoformat() if visitas[1] else None,
                       "ultima_visita": visitas[2].isoformat() if visitas[2] else None},
            "ultima_sincronizacao": {p: (e.finalizado_em.isoformat(timespec="seconds") if e and e.finalizado_em else None)
                                     for p, e in ultima_ok.items()},
            "execucoes": [_execucao_json(e) for e in execucoes]}


def producao(pid, de, ate):
    """Produção por profissional (Ficha de Visita Domiciliar e Territorial) e pontos para o mapa."""
    base = EsusVisita.query.filter(EsusVisita.prefeitura_id == pid, EsusVisita.data >= de, EsusVisita.data <= ate)
    soma = lambda cond: func.sum(case((cond, 1), else_=0))
    linhas = (base.with_entities(EsusVisita.profissional_nome, EsusVisita.profissional_cns, EsusVisita.categoria,
                                 func.max(EsusVisita.microarea), func.count(func.distinct(EsusVisita.microarea)), func.max(EsusVisita.equipe_nome), func.count(EsusVisita.id),
                                 soma(EsusVisita.desfecho == "realizada"), soma(EsusVisita.desfecho == "recusada"),
                                 soma(EsusVisita.desfecho == "ausente"), soma(EsusVisita.motivo_aedes.is_(True)),
                                 func.count(EsusVisita.latitude), func.count(func.distinct(EsusVisita.data)), func.max(EsusVisita.data))
              .group_by(EsusVisita.profissional_nome, EsusVisita.profissional_cns, EsusVisita.categoria)
              .order_by(func.count(EsusVisita.id).desc()).all())
    profissionais = [{"nome": r[0], "cns": r[1], "categoria": r[2], "microarea": r[3] if r[4] <= 1 else f"{r[4]} microáreas",
                      "equipe": r[5], "visitas": r[6], "realizadas": int(r[7] or 0), "recusadas": int(r[8] or 0),
                      "ausentes": int(r[9] or 0), "aedes": int(r[10] or 0), "com_gps": r[11], "dias": r[12],
                      "media_dia": round(r[6] / r[12], 1) if r[12] else 0, "ultima": r[13].isoformat() if r[13] else None} for r in linhas]
    pontos = [[v.latitude, v.longitude, v.profissional_nome, v.data.isoformat(), v.hora, v.desfecho, v.motivo_aedes, v.microarea]
              for v in base.filter(EsusVisita.latitude.isnot(None)).order_by(EsusVisita.data.desc()).limit(3000)]
    kpis = {k: sum(p[k] for p in profissionais) for k in ("visitas", "realizadas", "recusadas", "ausentes", "aedes", "com_gps")}
    kpis["profissionais"] = len(profissionais)
    return {"de": de.isoformat(), "ate": ate.isoformat(), "kpis": kpis, "profissionais": profissionais, "pontos": pontos}


def _validate_csrf(pid):
    from app.modules.configuracoes.routes import _validate_post
    _validate_post(pid)


def register_routes(bp):
    @bp.record_once
    def install_worker(state):
        esus.register_worker(state.app)

    @bp.get("/integracoes/esus", endpoint="integracoes_esus")
    @_coordenacao
    def tela():
        from app.modules.configuracoes.routes import _csrf_token
        pid = _prefeitura()
        global_user = is_admin_global_user(current_user)
        if pid is None and global_user:
            primeira = EsusConfig.query.order_by(EsusConfig.prefeitura_id).first()
            pid = primeira.prefeitura_id if primeira else None
        cfg = EsusConfig.query.filter_by(prefeitura_id=pid).first() if pid else None
        de, ate = _periodo(request.args)
        page = max(1, _int(request.args.get("pagina", "")) or 1)
        visitas = profissionais = None
        resumo = {}
        if cfg:
            query = _filtrar(EsusVisita.query.filter(EsusVisita.prefeitura_id == pid), request.args, de, ate)
            visitas = query.order_by(EsusVisita.data.desc(), EsusVisita.hora.desc(), EsusVisita.id.desc()).paginate(page=page, per_page=50, error_out=False)
            resumo = dict(query.with_entities(EsusVisita.desfecho, func.count(EsusVisita.id)).group_by(EsusVisita.desfecho).all())
            resumo["aedes"] = query.filter(EsusVisita.motivo_aedes.is_(True)).count()
            profissionais = [r[0] for r in db.session.query(EsusVisita.profissional_nome).filter(EsusVisita.prefeitura_id == pid)
                             .distinct().order_by(EsusVisita.profissional_nome)]
        prefeituras = Prefeitura.query.filter_by(ativa=True).order_by(Prefeitura.nome).all() if global_user else []
        return render_template("integracoes_esus.html", cfg=cfg, status=status_payload(cfg) if cfg else None, prefeitura_id=pid,
                               prefeituras=prefeituras, global_user=global_user, visitas=visitas, profissionais=profissionais or [],
                               resumo=resumo, de=de, ate=ate, desfechos=DESFECHO_LABEL, csrf=_csrf_token(),
                               prefeitura_nome=(db.session.get(Prefeitura, pid).nome if pid else ""))

    @bp.post("/integracoes/esus/sincronizar", endpoint="integracoes_esus_sincronizar")
    @_coordenacao
    def sincronizar():
        pid = _prefeitura(request.form)
        if pid is None:
            abort(400)
        _validate_csrf(pid)
        if EsusConfig.query.filter_by(prefeitura_id=pid).first() is None:
            abort(404)
        if esus.em_execucao(pid):
            flash("Já existe uma sincronização em andamento para esta prefeitura.", "warning")
        elif request.form.get("forma") == "assincrona":
            esus.iniciar_em_segundo_plano(pid, current_user.id)
            flash("Sincronização iniciada em segundo plano. Acompanhe as execuções abaixo.", "info")
        else:
            resultados = esus.sincronizar_tudo(pid, "sincrona", current_user.id)
            falhas = [e for e in resultados if e.status != "concluida"]
            if falhas:
                flash("Falha na sincronização: " + " | ".join(e.mensagem or "erro" for e in falhas), "danger")
            else:
                flash("Sincronização concluída: " + "; ".join(f"{e.processo}: {e.lidos} lidos, {e.inseridos} novos, {e.atualizados} atualizados, {e.removidos} removidos" for e in resultados) + ".", "success")
        return redirect(url_for("main.integracoes_esus", prefeitura_id=pid), code=303)

    @bp.route("/integracoes/esus/configuracao", methods=["GET", "POST"], endpoint="integracoes_esus_config")
    @_admin_global
    def configuracao():
        from app.modules.configuracoes.routes import _csrf_token
        source = request.form if request.method == "POST" else request.args
        pid = _prefeitura(source)
        prefeituras = Prefeitura.query.filter_by(ativa=True).order_by(Prefeitura.nome).all()
        if pid is None and prefeituras:
            pid = prefeituras[0].id
        prefeitura = db.session.get(Prefeitura, pid) if pid else None
        if pid and prefeitura is None:
            abort(404)
        cfg = EsusConfig.query.filter_by(prefeitura_id=pid).first() if pid else None
        novo_token = erro = None
        if request.method == "POST" and prefeitura:
            _validate_csrf(pid)
            acao = request.form.get("acao", "salvar")
            if cfg is None and acao != "salvar":
                erro = "Salve a configuração antes."
            elif acao == "salvar":
                form = request.form
                modo = form.get("modo")
                ibge = form.get("ibge", "").strip()
                porta = _int(form.get("porta", "5432"))
                intervalo = _int(form.get("intervalo_min", "0"))
                if modo not in {"pec", "simulado"} or not (ibge.isdecimal() and len(ibge) == 7) or not porta or not 1 <= porta <= 65535 \
                        or intervalo is None or intervalo > 1440 or (0 < intervalo < 5):
                    erro = "Confira o modo, o código IBGE (7 dígitos), a porta e o intervalo (0 ou de 5 a 1440 minutos)."
                elif modo == "pec" and not (form.get("host", "").strip() and form.get("base", "").strip() and form.get("usuario", "").strip()):
                    erro = "No modo Banco do PEC, informe host, base e usuário."
                else:
                    if cfg is None:
                        cfg = EsusConfig(prefeitura_id=pid)
                        db.session.add(cfg)
                    cfg.modo, cfg.ibge, cfg.intervalo_min, cfg.ativo = modo, ibge, intervalo, form.get("ativo") == "on"
                    if modo == "pec":  # no modo simulado os campos do PEC ficam desabilitados e são preservados
                        cfg.host = form.get("host", "").strip()[:200]
                        cfg.base = form.get("base", "").strip()[:120]
                        cfg.usuario = form.get("usuario", "").strip()[:120]
                        cfg.porta = porta
                        if form.get("senha"):
                            cfg.senha_cifrada = cifrar(form["senha"])
                    cfg.atualizado_por_id = current_user.id
                    db.session.commit()
                    flash("Configuração da integração e-SUS salva.", "success")
                    return redirect(url_for("main.integracoes_esus_config", prefeitura_id=pid), code=303)
            elif acao == "testar":
                try:
                    total = esus.testar_conexao(cfg)
                    flash(f"Conexão OK ({'PEC simulado' if cfg.modo == 'simulado' else 'banco do PEC'}): {total} visita(s) domiciliar(es) em tb_fat_visita_domiciliar.", "success")
                except Exception as exc:
                    flash(esus._mensagem(exc), "danger")
                return redirect(url_for("main.integracoes_esus_config", prefeitura_id=pid), code=303)
            elif acao == "gerar_simulado":
                def num(name, default, low, high):
                    value = _int(request.form.get(name, "")) or default
                    return min(max(value, low), high)
                try:
                    centro = (float(request.form.get("lat") or -8.3558), float(request.form.get("lng") or -36.6978))
                    if not (-34 <= centro[0] <= 6 and -74 <= centro[1] <= -28):
                        raise ValueError
                except ValueError:
                    erro = "Centro do município inválido."
                else:
                    resumo = esus.gerar_simulado(cfg.ibge, prefeitura.nome, centro, acs=num("acs", 6, 1, 12), ace=num("ace", 2, 0, 6),
                                                 domicilios=num("domicilios", 300, 10, 5000), visitas=num("visitas", 1500, 10, 20000),
                                                 dias=num("dias", 30, 1, 90))
                    esus.limpar_sincronizados_simulados(pid)
                    flash(f"PEC simulado gerado: {resumo['acs']} ACS, {resumo['ace']} ACE, {resumo['domicilios']} domicílios e {resumo['visitas']} visitas nos últimos {resumo['dias']} dias. Sincronize para trazer os dados.", "success")
                    return redirect(url_for("main.integracoes_esus_config", prefeitura_id=pid), code=303)
            elif acao == "gerar_token":
                novo_token = esus.gerar_token(cfg)
                db.session.commit()
            elif acao == "revogar_token":
                cfg.token_hash = cfg.token_prefixo = cfg.token_criado_em = None
                db.session.commit()
                flash("Token de integração revogado.", "success")
                return redirect(url_for("main.integracoes_esus_config", prefeitura_id=pid), code=303)
        ibge_padrao = municipality_ibge(current_app.config.get("VIGILANCIA_MUNICIPIOS_IBGE", {}), pid) if pid else None
        response = render_template("integracoes_esus_config.html", cfg=cfg, prefeitura=prefeitura, prefeituras=prefeituras,
                                   novo_token=novo_token, erro=erro, csrf=_csrf_token(), ibge_padrao=ibge_padrao or "",
                                   tem_senha=bool(cfg and cfg.senha_cifrada), sim_schema=esus.SIM_SCHEMA)
        return (response, 400) if erro else response

    @bp.get("/api/vigilancia/agentes/esus", endpoint="vigilancia_agentes_esus")
    @_coordenacao
    def agentes_esus():
        pid = _prefeitura()
        if pid is None:
            return jsonify(error="Selecione uma prefeitura."), 400
        from app.modules.vigilancia.agent_tracking import _period
        de, ate = _period()
        cfg = EsusConfig.query.filter_by(prefeitura_id=pid).first()
        if cfg is None:
            return jsonify(configurado=False, de=de.isoformat(), ate=ate.isoformat())
        data = producao(pid, de, ate)
        data.update(configurado=True, modo=cfg.modo,
                    ultima_sincronizacao=status_payload(cfg, limite=1)["ultima_sincronizacao"]["visitas"])
        return jsonify(data)

    # -------------------------------------------------- API para terceiros (token de integração)
    def _token_config():
        cfg = esus.config_por_token(request.headers.get("Authorization", ""))
        if cfg is None:
            response = jsonify(error="Token de integração ausente ou inválido.")
            response.status_code = 401
            response.headers["WWW-Authenticate"] = 'Bearer realm="ija-esus"'
            return None, response
        return cfg, None

    @bp.get("/api/integracoes/esus/status", endpoint="api_esus_status")
    def api_status():
        cfg, erro = _token_config()
        if erro:
            return erro
        return jsonify(status_payload(cfg))

    @bp.get("/api/integracoes/esus/visitas", endpoint="api_esus_visitas")
    def api_visitas():
        cfg, erro = _token_config()
        if erro:
            return erro
        de, ate = _periodo(request.args)
        page = max(1, _int(request.args.get("page", "")) or 1)
        per_page = min(max(_int(request.args.get("per_page", "")) or 100, 1), 500)
        query = _filtrar(EsusVisita.query.filter(EsusVisita.prefeitura_id == cfg.prefeitura_id), request.args, de, ate)
        pagina = query.order_by(EsusVisita.data.desc(), EsusVisita.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return jsonify(prefeitura_id=cfg.prefeitura_id, de=de.isoformat(), ate=ate.isoformat(), page=page, per_page=per_page,
                       total=pagina.total, pages=pagina.pages, items=[_visita_json(v) for v in pagina.items])
