from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import ControleRemotoAtualizacao
from app.modules.gestao_ti.permissions import can_access_endpoint, route_access
from app.modules.equipamentos.controles import (
    CONTROL_FIELDS, controle_form, controle_query, list_controles, save_controle, validate_controle_form,
)
from app.modules.equipamentos.service import equipment_team_assignments, list_drones_for_baterias
from app.shared.access import is_veiculos_supervisor, normalize_role


def _legacy():
    return normalize_role(current_user.tipo_usuario) in {
        'dev', 'diretor', 'admin', 'operario', 'operador', 'prefeitura_admin', 'manutencao',
    } or is_veiculos_supervisor(current_user)


def register_controle_routes(bp):
    @bp.route('/equipamentos/controles', endpoint='listar_controles')
    @login_required
    def listar():
        q = request.args.get('q', '').strip()
        controles = list_controles(current_user, q)
        return render_template('controles_listar.html', controles=controles, q=q,
            responsabilidades=equipment_team_assignments(controles, user=current_user),
            can_create=can_access_endpoint(current_user, 'main.cadastrar_controle', legacy=_legacy()),
            can_edit=can_access_endpoint(current_user, 'main.editar_controle', legacy=_legacy()))

    def form_page(controle=None):
        if not route_access(current_user, _legacy()):
            abort(403)
        drones = list_drones_for_baterias(user=current_user)
        form = controle_form(controle) if controle is not None else {'drone_id': request.args.get('drone_id', '')}
        errors = {}
        if request.method == 'POST':
            form, cleaned, errors = validate_controle_form(request.form, user=current_user, existing=controle)
            if not errors:
                try:
                    save_controle(cleaned, user=current_user, existing=controle)
                    flash('Controle remoto salvo com sucesso.', 'success')
                    return redirect(url_for('main.listar_controles'))
                except IntegrityError:
                    db.session.rollback()
                    errors['numero_serie'] = 'Não foi possível salvar. Confira se a série já foi cadastrada e se o drone ainda existe.'
                except Exception:
                    db.session.rollback()
                    current_app.logger.exception('Erro ao salvar controle remoto.')
                    flash('Não foi possível salvar o controle. Tente novamente.', 'danger')
            if errors:
                flash('Revise os campos destacados.', 'warning')
        return render_template('controle_form.html', controle=controle, form=form, errors=errors, drones=drones)

    @bp.route('/controles/cadastrar', methods=['GET', 'POST'], endpoint='cadastrar_controle')
    @login_required
    def cadastrar():
        return form_page()

    @bp.route('/controles/<int:controle_id>/editar', methods=['GET', 'POST'], endpoint='editar_controle')
    @login_required
    def editar(controle_id):
        controle = controle_query(current_user).filter_by(id=controle_id).first_or_404()
        return form_page(controle)

    @bp.route('/equipamentos/controles/<int:controle_id>/historico', endpoint='historico_controle')
    @login_required
    def historico(controle_id):
        if not route_access(current_user, True):
            abort(403)
        controle = controle_query(current_user).filter_by(id=controle_id).first_or_404()
        registros = ControleRemotoAtualizacao.query.filter_by(
            controle_id=controle.id, prefeitura_id=controle.prefeitura_id,
        ).order_by(ControleRemotoAtualizacao.id.desc()).paginate(per_page=25)
        return render_template('controle_historico.html', controle=controle, registros=registros, campos=CONTROL_FIELDS)
