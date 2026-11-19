"""Second Agro package: scoped, read-only record assistance."""
from datetime import date
from flask import abort, url_for
from app.models import OrdemServicoAgro, RdMapeamentoAgro
from app.modules.chatbot import agro
from app.modules.consultas.service import QueryError


def tools(user):
    sources = agro.allowed_sources(user)
    result = []
    if sources:
        result.append({'type': 'function', 'name': 'buscar_agro_periodo', 'strict': True,
            'description': 'Busca Agro por período inclusivo. OS usa data de aplicação; RD do piloto usa data do relatório; demais fontes usam criação. Informe datas ISO ou vazio. Não ignore filtros não suportados. Use status oficiais; em andamento significa EM EXECUCAO. Não filtra equipe: o acesso já limita o escopo.',
            'parameters': {'type': 'object', 'additionalProperties': False,
                'required': ['fonte', 'q', 'status', 'inicio', 'fim'], 'properties': {
                    'fonte': {'type': 'string', 'enum': sources},
                    **{k: {'type': 'string'} for k in ('q', 'status', 'inicio', 'fim')}}}})
    kinds = [s for s in ('os', 'mapeamentos') if s in sources]
    if kinds:
        result.append({'type': 'function', 'name': 'detalhar_agro', 'strict': True,
            'description': 'Resume uma OS ou confere preenchimento salvo de OS/RD antes da conclusão. Exige ID explícito, nunca adivinhe. Para mapeamentos o ID é da RD (não orçamento). Não vê alterações ainda não salvas. Não altera registros.',
            'parameters': {'type': 'object', 'additionalProperties': False,
                'required': ['fonte', 'id', 'conferir'], 'properties': {
                    'fonte': {'type': 'string', 'enum': kinds}, 'id': {'type': 'integer', 'minimum': 1, 'maximum': 2147483647},
                    'conferir': {'type': 'boolean'}}}})
    return result


def search_period(user, plan):
    if not isinstance(plan, dict) or set(plan) != {'fonte', 'q', 'status', 'inicio', 'fim'}:
        raise QueryError('Informe fonte, busca, status e datas inicial/final.')
    bounds = []
    for key in ('inicio', 'fim'):
        value = plan[key]
        if not isinstance(value, str):
            raise QueryError('Use datas no formato AAAA-MM-DD.')
        try:
            if value and (len(value) != 10 or date.fromisoformat(value).isoformat() != value):
                raise ValueError()
            bounds.append(date.fromisoformat(value) if value else None)
        except ValueError:
            raise QueryError('Use datas válidas no formato AAAA-MM-DD.') from None
    if all(bounds) and bounds[0] > bounds[1]:
        raise QueryError('A data inicial deve ser anterior ou igual à final.')
    return agro.execute(user, {k: plan[k] for k in ('fonte', 'q', 'status')}, period=bounds)


def apply_period(query, user, source, model, bounds):
    field = 'data_aplicacao' if source == 'os' else (
        'data_relatorio' if source == 'mapeamentos' and agro.is_pilot(user) else 'criado_em')
    column = getattr(model, field)
    # SQL date() is portable across SQLite tests and PostgreSQL production.
    from app.extensions import db
    column = db.func.date(column)
    for value, lower in zip(bounds, (True, False)):
        if value:
            query = query.filter(column >= value.isoformat() if lower else column <= value.isoformat())
    label = {'data_aplicacao': 'data de aplicação', 'data_relatorio': 'data do relatório', 'criado_em': 'data de criação'}[field]
    return query, f'Período por {label}: {bounds[0] or "sem início"} até {bounds[1] or "sem fim"} (inclusive). Registros sem essa data não entram no período.'


def detail(user, plan):
    if (not isinstance(plan, dict) or set(plan) != {'fonte', 'id', 'conferir'}
            or type(plan['id']) is not int or not 1 <= plan['id'] <= 2147483647 or type(plan['conferir']) is not bool):
        raise QueryError('Informe o tipo de registro, ID positivo e se deseja conferir o preenchimento.')
    source = plan['fonte']
    if source not in ('os', 'mapeamentos') or source not in agro.allowed_sources(user):
        abort(403)
    agro.timeout()
    if source == 'os':
        record = agro.query_for(user, source).filter(OrdemServicoAgro.id == plan['id']).first()
    elif agro.is_pilot(user):
        record = agro.query_for(user, source).filter(RdMapeamentoAgro.id == plan['id']).first()
    else:
        # Authorize through the same scoped mapping budgets as the screen.
        budget = agro.query_for(user, source).filter(agro.OrcamentoAgro.rd_mapeamento.has(id=plan['id'])).first()
        record = budget.rd_mapeamento if budget else None
    if record is None:
        return 'Registro não encontrado no seu acesso.', []
    lines = [f'{"OS" if source == "os" else "RD"} #{record.id} · {record.status}',
             f'Propriedade: {record.propriedade_nome or "não informada"}.',
             f'Equipe: {record.equipe.nome if record.equipe else "não informada"}.',
             f'Piloto: {record.piloto.nome if record.piloto else "não informado"}.']
    if source == 'os':
        lines += [f'Identificador: {record.identificador_os}.',
                  f'Data de aplicação: {record.data_aplicacao or "não informada"}.',
                  f'Serviço: {record.servico or "não informado"}. Cultura: {record.cultura or "não informada"}.',
                  f'Área registrada: {record.area_total_ha if record.area_total_ha is not None else "não informada"} ha.',
                  f'Drone de pulverização: {record.drone_pulverizacao_identificacao or "não informado"}.',
                  f'Drone de mapeamento: {record.drone_mapeamento_identificacao or "não informado"}.']
    else:
        lines += [f'Data do relatório: {record.data_relatorio or "não informada"}.',
                  f'Equipamento: {record.equipamento or "não informado"}.']
    if plan['conferir']:
        from app.modules.agro import routes
        if source == 'os':
            equipes, _, equipamentos = routes._build_os_agro_form_options(
                piloto_logado=user.piloto_agro if agro.is_pilot(user) else None)
            errors = routes._validate_os_agro_form(routes._serialize_os_agro_form(record), equipes, equipamentos, ordem_atual=record)[0]
            if record.equipe_agro_id and record.contrato.equipe_agro_id and record.contrato.equipe_agro_id != record.equipe_agro_id:
                errors['equipe'] = 'A equipe da OS precisa seguir a equipe do contrato aprovado.'
            lines.append('Anexos opcionais: relatório ' + ('presente' if record.relatorio_pdf_path else 'ausente')
                         + '; mapa ' + ('presente' if record.mapa_aplicacao_path else 'ausente') + '.')
        else:
            errors = routes._validate_rd_mapeamento_form(
                agro.service.serialize_rd_mapeamento_agro_form(record),
                ([record.equipe] if record.equipe else []) if agro.is_pilot(user) else routes._build_agro_equipes_ativas(),
                require_full=True)[0]
        lines.append('Conferência dos dados salvos para conclusão:')
        lines.extend('• ' + message for message in errors.values())
        if not errors:
            lines.append('Nenhum erro de preenchimento encontrado pelas validações consultadas. Revise a tela antes de concluir.')
        lines.append('Alterações ainda não salvas não foram conferidas. Esta conferência não atesta segurança operacional.')
    lines.append('Nenhum registro foi alterado.')
    return '\n'.join(lines), [{'label': 'Abrir lista autorizada', 'url': url_for('main.' + agro.endpoint(user, source))}]
