"""Read existing requests/OS; no duplicate properties, visits or risk scores."""
from datetime import datetime
from math import isfinite
from zoneinfo import ZoneInfo
from flask import abort
from sqlalchemy.orm import selectinload
from app.models import Solicitacao
from app.shared.access import central_ti_team_ids
from .service import build_heatmap_query

MAX_RECORDS = 10000
MAX_HISTORY = 300


def scoped(user, **filters):
    query=build_heatmap_query(user,com_coordenadas=False,**filters)
    teams=central_ti_team_ids(user)
    if teams is not None:query=query.filter(Solicitacao.equipe_id.in_(teams))
    return query.options(selectinload(Solicitacao.ordem_servico),selectinload(Solicitacao.ordem_servico_equipe_uvis))


def state(row, today):
    status=(row.status or '').strip().upper()
    if 'CANCEL' in status or 'REPROV' in status or 'INDEFER' in status:
        return 'ENCERRADO'
    drone,uvis=row.ordem_servico,row.ordem_servico_equipe_uvis
    if ('CONCLU' in status or (drone and drone.respondido_em)
            or (uvis and (uvis.status or '').upper() in {'CONCLUIDO','CONCLUÍDO'})):
        return 'CONCLUIDO'
    if row.data_agendamento and row.data_agendamento<today:return 'ATRASADO'
    return 'PENDENTE'


def serialize(row,today):
    orders=[]
    for source,os in [('Piloto / equipe Oceano',row.ordem_servico),('Equipe UVIS',row.ordem_servico_equipe_uvis)]:
        if os:
            orders.append(dict(origem=source,identificador=os.identificador_os or str(os.id),
                respondido_em=os.respondido_em.isoformat() if os.respondido_em else None,
                situacao=os.situacao_aplicacao or 'Não informada',larvas=os.larva_visualizada or 'Não informado',
                criadouro=getattr(os,'criadouro_os_tipo_volume',None) or row.foco))
    return dict(id=row.id,foco=row.foco or 'Outros',status=row.status or 'Não informado',
        situacao=state(row,today),data=row.data_agendamento.isoformat() if row.data_agendamento else None,
        bairro=row.bairro or 'Não informado',endereco=' '.join(x for x in [row.logradouro,row.numero] if x),
        retorno=bool(row.origem_retorno_id),ordens=orders)


def points(user, **filters):
    today=datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    rows=scoped(user,**filters).order_by(Solicitacao.id).limit(MAX_RECORDS+1).all()
    if len(rows)>MAX_RECORDS:raise ValueError('Mais de 10.000 solicitações. Restrinja mês, ano ou unidade; nenhum resultado foi cortado.')
    if filters.get('visao')=='pendentes':rows=[r for r in rows if state(r,today) in {'PENDENTE','ATRASADO'}]
    result=[]
    for row in rows:
        item=serialize(row,today)
        try:
            lat,lng=float(row.latitude),float(row.longitude)
            valid=isfinite(lat) and isfinite(lng) and -90<=lat<=90 and -180<=lng<=180
        except (ValueError,TypeError):valid=False
        item.update(lat=lat if valid else None,lng=lng if valid else None)
        result.append(item)
    return dict(registros=result,gerado_em=datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(),
        criterio='Situação atual das solicitações do período agendado. OS respondida não comprova eliminação do foco. Cores operacionais, sem classificação de risco.')


def history(user, sid):
    """Follow explicit return links only; never guess identity from an address.

    Every hop is scoped independently, including corrupt cross-tenant links.
    The result deliberately covers the full visible chain, outside map dates.
    """
    query=scoped(user,visao='todos')
    row=query.filter(Solicitacao.id==sid).first()
    if row is None:abort(404)
    seen=set();root=row
    while root.origem_retorno_id:
        if root.id in seen:raise ValueError('Vínculos de retorno inconsistentes. Solicite revisão do cadastro.')
        seen.add(root.id)
        if len(seen)>=MAX_HISTORY:raise ValueError('Histórico extenso. Consulte o relatório de retornos.')
        parent=query.filter(Solicitacao.id==root.origem_retorno_id).first()
        if parent is None:break
        root=parent
    family={root.id:root};frontier=[root.id]
    while frontier:
        children=query.filter(Solicitacao.origem_retorno_id.in_(frontier)).limit(MAX_HISTORY+1).all()
        frontier=[]
        for child in children:
            if child.id in family:raise ValueError('Vínculos de retorno inconsistentes. Solicite revisão do cadastro.')
            family[child.id]=child;frontier.append(child.id)
        if len(family)>MAX_HISTORY:raise ValueError('Histórico extenso. Consulte o relatório de retornos.')
    today=datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    return dict(solicitacao_id=sid,registros=[serialize(r,today) for r in sorted(family.values(),key=lambda r:(r.data_agendamento or today,r.id))],
        criterio='Solicitação e retornos explicitamente vinculados, dentro do seu acesso, inclusive fora do período do mapa. Não é um histórico de todas as edições; alterações cadastrais permanecem na auditoria existente.')
