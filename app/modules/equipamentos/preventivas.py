"""Agenda preventiva: dias locais, alocação existente e histórico próprio."""
from datetime import date, datetime, timedelta, timezone

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Drones, Veiculos, PreventivaPlano, PreventivaRegistro, ManutencaoEquipamento
from app.modules.gestao_ti.permissions import can_access_endpoint
from app.shared.access import apply_prefeitura_scope
from app.modules.equipamentos.preventivas_access import can_use_preventivas
from app.shared.maintenance_time import to_sao_paulo
from app.modules.equipamentos.controles import drone_prefeitura
from app.modules.equipamentos.service import (
    can_open_maintenance_os, equipment_team_assignments, maintenance_equipment_key, maintenance_legacy_access,
    scope_maintenance_records,
)

LABELS = {'atrasada':'Atrasada', 'hoje':'Vence hoje', 'proxima':'Próxima do vencimento', 'em_dia':'Em dia', 'sem_configuracao':'Sem configuração'}


def today_local():
    return to_sao_paulo(datetime.now(timezone.utc)).date()


def situation(plan, today=None):
    if not plan or not plan.ultima_realizada_em:
        return dict(status='sem_configuracao', vencimento=None, dias=None)
    due = plan.ultima_realizada_em + timedelta(days=plan.intervalo_dias)
    days = (due-(today or today_local())).days
    status = 'atrasada' if days<0 else 'hoje' if days==0 else 'proxima' if days<=7 else 'em_dia'
    return dict(status=status, vencimento=due, dias=days)


def allowed(user, model, edit=False):
    if not can_use_preventivas(user):
        return False
    endpoint = ('main.editar_drone' if edit else 'main.listar_drones') if model is Drones else ('main.editar_veiculo' if edit else 'main.listar_veiculos')
    return can_access_endpoint(user, endpoint, legacy=True)


def visible_equipment(user):
    rows = []
    for model in (Drones, Veiculos):
        if allowed(user, model):
            rows.extend(apply_prefeitura_scope(model.query,user,model.prefeitura_id).all())
    return rows


def scoped_equipment(equipment_id, user):
    # Apply type-specific capability as well as the tenant/team scope.
    for model in (Drones, Veiculos):
        if allowed(user, model):
            equipment = apply_prefeitura_scope(model.query,user,model.prefeitura_id).filter(model.id==equipment_id).first()
            if equipment:
                return equipment
    abort(404)


def plan_matches_equipment(plan, equipment):
    """Do not reveal a previous tenant's plan after a fleet reassignment."""
    if not plan:
        return True
    try:
        return plan.prefeitura_id == drone_prefeitura(equipment)
    except ValueError:
        return False


def completed_equipment_orders(equipment, user):
    query = scope_maintenance_records(ManutencaoEquipamento.query, ManutencaoEquipamento, user)
    if not can_access_endpoint(user, "main.equipamentos_manutencoes_historico", legacy=maintenance_legacy_access(user)):
        return query.filter(db.false())
    return query.filter_by(
        status="encerrada", **{maintenance_equipment_key(equipment): equipment.id},
    )


def save_plan(equipment, data, user):
    plan = PreventivaPlano.query.filter_by(equipamento_id=equipment.id).first()
    try:
        version = int(data.get('versao','0'))
    except (ValueError, TypeError):
        raise ValueError('Reabra a página para atualizar a versão do cadastro.')
    if version != (plan.versao if plan else 0):
        raise ValueError('Este cadastro foi alterado em outra aba. Reabra a página antes de salvar.')
    tenant = drone_prefeitura(equipment)
    if plan and plan.prefeitura_id != tenant:
        raise ValueError('O plano e o equipamento devem pertencer à mesma prefeitura. Revise a alocação.')
    action = data.get('acao')
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    before = dict(intervalo=plan.intervalo_dias, ultima=plan.ultima_realizada_em.isoformat() if plan.ultima_realizada_em else None) if plan else {}
    if action == 'configurar':
        if data.get('intervalo') not in ('60','90'):
            raise ValueError('Selecione um intervalo de 60 ou 90 dias.')
        interval = int(data['intervalo'])
        raw = (data.get('ultima_realizada_em') or '').strip()
        try:
            last = date.fromisoformat(raw) if raw else None
        except ValueError:
            raise ValueError('Informe uma data válida para a última preventiva.')
        if last and last > today_local():
            raise ValueError('A última preventiva não pode ter uma data futura.')
        if plan and PreventivaRegistro.query.filter_by(plano_id=plan.id,tipo='conclusao').first() and last != plan.ultima_realizada_em:
            raise ValueError('Após uma conclusão, registre novas preventivas pelo formulário de execução. A configuração altera apenas o intervalo.')
        description = 'Configuração da agenda preventiva.'
        maintenance_id = None
    elif action == 'concluir':
        if not plan:
            raise ValueError('Configure o intervalo antes de registrar a primeira conclusão.')
        interval = plan.intervalo_dias
        try:
            last = date.fromisoformat(data.get('realizada_em',''))
        except (ValueError, TypeError):
            raise ValueError('Informe a data de realização da preventiva.')
        if last > today_local() or (plan.ultima_realizada_em is not None and last < plan.ultima_realizada_em):
            raise ValueError('A realização deve ocorrer entre a última preventiva e hoje.')
        description = (data.get('descricao') or '').strip()
        if not description or len(description)>5000:
            raise ValueError('Descreva os serviços realizados, usando até 5.000 caracteres.')
        maintenance_id = None
        raw = (data.get('manutencao_id') or '').strip()
        if raw:
            try:
                maintenance_id = int(raw)
            except ValueError:
                raise ValueError('Selecione uma OS de manutenção válida.')
            order = completed_equipment_orders(equipment, user).filter_by(id=maintenance_id).first()
            if not order or order.prefeitura_id != tenant:
                raise ValueError('Selecione uma OS concluída deste equipamento e prefeitura.')
    else:
        raise ValueError('Ação inválida.')
    if plan:
        changed = db.session.execute(db.update(PreventivaPlano).where(PreventivaPlano.id==plan.id,PreventivaPlano.versao==version).values(
            intervalo_dias=interval,ultima_realizada_em=last,versao=version+1,atualizado_em=now),execution_options={'synchronize_session':False})
        if changed.rowcount != 1:
            raise ValueError('O cadastro mudou durante a gravação. Reabra a página.')
    else:
        plan = PreventivaPlano(equipamento_id=equipment.id,prefeitura_id=tenant,intervalo_dias=interval,
            ultima_realizada_em=last,versao=1,atualizado_em=now)
        db.session.add(plan)
        db.session.flush()
    db.session.add(PreventivaRegistro(plano_id=plan.id,usuario_id=user.id,usuario_nome=(user.nome_uvis or user.login)[:200],
        criado_em=now,tipo='conclusao' if action=='concluir' else 'configuracao',realizada_em=last,
        descricao=description,manutencao_id=maintenance_id,
        dados={'antes':before,'depois':{'intervalo':interval,'ultima':last.isoformat() if last else None}}))
    db.session.commit()
    db.session.expire_all()


def register_preventiva_routes(bp):
    @bp.app_context_processor
    def preventive_navigation():
        return {'can_view_preventivas': can_use_preventivas(current_user) and (
            allowed(current_user, Drones) or allowed(current_user, Veiculos))}

    @bp.route('/equipamentos/preventivas',endpoint='preventivas')
    @login_required
    def dashboard():
        if not can_use_preventivas(current_user):
            abort(403)
        equipment = visible_equipment(current_user)
        ids = [e.id for e in equipment]
        plans = {p.equipamento_id:p for p in PreventivaPlano.query.filter(PreventivaPlano.equipamento_id.in_(ids)).all()} if ids else {}
        plans = {e.id: plans[e.id] for e in equipment if e.id in plans and plan_matches_equipment(plans[e.id], e)}
        allocations = equipment_team_assignments(equipment,user=current_user)
        rows, counts = [], {key:0 for key in LABELS}
        q = request.args.get('q','').strip()
        status, kind = request.args.get('situacao',''),request.args.get('tipo','')
        for e in equipment:
            state = situation(plans.get(e.id))
            counts[state['status']] += 1
            if status and status != state['status'] or kind and kind != e.tipo_equipamento:
                continue
            if q and not any(q.casefold() in str(v or '').casefold() for v in (e.renomacao,e.modelo,e.numero_serie,getattr(e,'placa',None))):
                continue
            rows.append(dict(equipamento=e,plano=plans.get(e.id),**state))
        rows.sort(key=lambda r:(list(LABELS).index(r['status']),r['vencimento'] or date.max,r['equipamento'].renomacao))
        return render_template('preventivas.html',rows=rows,counts=counts,total=len(equipment),labels=LABELS,q=q,
            situacao=status,tipo=kind,responsabilidades=allocations)

    @bp.route('/equipamentos/preventivas/<int:equipamento_id>',methods=['GET','POST'],endpoint='preventiva_detalhe')
    @login_required
    def detail(equipamento_id):
        if not can_use_preventivas(current_user):
            abort(403)
        equipment = scoped_equipment(equipamento_id,current_user)
        model = Drones if isinstance(equipment,Drones) else Veiculos
        can_edit = allowed(current_user,model,True)
        error = None
        if request.method=='POST':
            if not can_edit:
                abort(403)
            try:
                save_plan(equipment,request.form,current_user)
                flash('Agenda preventiva atualizada.','success')
                return redirect(url_for('main.preventiva_detalhe',equipamento_id=equipment.id))
            except (ValueError, IntegrityError) as exc:
                db.session.rollback()
                error = str(exc) if isinstance(exc,ValueError) else 'O cadastro foi alterado em outra aba. Reabra a página.'
        plan = PreventivaPlano.query.filter_by(equipamento_id=equipment.id).first()
        if not plan_matches_equipment(plan, equipment):
            abort(404)
        history = PreventivaRegistro.query.filter_by(plano_id=plan.id).order_by(PreventivaRegistro.id.desc()).limit(50).all() if plan else []
        has_conclusion = bool(plan and PreventivaRegistro.query.filter_by(plano_id=plan.id, tipo='conclusao').first())
        orders = completed_equipment_orders(equipment, current_user).filter_by(prefeitura_id=drone_prefeitura(equipment)).order_by(
            ManutencaoEquipamento.encerrada_em.desc(), ManutencaoEquipamento.id.desc(),
        ).all() if plan and can_edit else []
        return render_template('preventiva_detalhe.html',equipment=equipment,plan=plan,state=situation(plan),labels=LABELS,
            can_edit=can_edit,error=error,history=history,today=today_local(),orders=orders,has_conclusion=has_conclusion,
            can_open_os=can_open_maintenance_os(current_user),
            responsabilidades=equipment_team_assignments([equipment],user=current_user))
