# Inventário de rotas para o mapa de permissões

As 361 declarações abaixo complementam o [mapa de funções por usuário](mapa-permissoes-usuarios.md). Referência: código local de 8 de outubro de 2026, commit `744c72c`.

O método mostrado é o declarado no código. HEAD e OPTIONS automáticos, a rota estática do Flask e configuração de infraestrutura não entram na contagem. Os endpoints são nomes locais, sem o prefixo do blueprint.

A coluna Verificações locais mostra decoradores adicionais, chamadas a helpers reconhecidas pelo nome e condições explícitas relacionadas ao ator. São referências para leitura do código, não uma avaliação automática de quem tem acesso. Guards em helpers, serviços chamados, hooks globais, propriedade do registro e flags de ambiente podem completar ou alterar a decisão. Um traço nessa coluna não significa acesso público.

Os templates listados são argumentos explícitos de render_template no controller. Alguns endpoints renderizam por outro controller ou devolvem JSON, arquivos, redirects ou streams; por isso não há uma correspondência de um template para cada rota.

## Hooks e serviços compartilhados

- [Acesso e escopos](../app/shared/access.py): conjuntos administrativos e financeiros, prefeitura e região.
- [Central Financeiro](../app/modules/financeiro/routes.py): autorização de endpoints financeiros legados, bloqueios para perfis financeiros e reutilização de controllers.
- [Agro](../app/modules/agro/service.py): habilitação Agro, edição, fornecedores, configurações e competências.
- [OS e mídias](../app/modules/piloto_os/service.py): autorização e estado do formulário; os endpoints de upload passam também por _build_upload_context.
- [Retorno e mídias](../app/shared/retorno_ciclo.py): escopo por UVIS, equipe, prefeitura e região.
- [Frota](../app/modules/veiculos/service.py): listas de perfis e vínculo operacional; leitura, correção e exclusão de log possuem regras diferentes.
- [Sessão](../app/shared/session_security.py): expiração e atividade da sessão; [CSRF](../app/shared/csrf_security.py): proteção dos requests que alteram estado.
- [Vigilância](../app/modules/vigilancia/routes.py): decorador próprio para feature flag, autenticação e perfil.

## Quantidade por módulo

| Módulo ou diretório | Declarações |
| --- | ---: |
| `admin_checklists` | 4 |
| `admin_dashboard` | 12 |
| `admin_uvis` | 5 |
| `agenda_notificacoes` | 7 |
| `agro` | 101 |
| `anexos` | 3 |
| `app` | 2 |
| `auditoria` | 1 |
| `auth` | 4 |
| `backup` | 3 |
| `canceladas` | 2 |
| `cep` | 2 |
| `chatbot` | 4 |
| `clientes` | 5 |
| `core` | 3 |
| `dashboard` | 4 |
| `denuncias` | 10 |
| `dev_dashboard` | 5 |
| `dji_flight_logs` | 9 |
| `drones_import` | 3 |
| `equipamentos` | 21 |
| `equipe_uvis_dashboard` | 4 |
| `equipes` | 5 |
| `estoque` | 5 |
| `feedback` | 16 |
| `financeiro` | 9 |
| `mapas` | 4 |
| `painel_operacional` | 2 |
| `piloto_checklists` | 1 |
| `piloto_os` | 25 |
| `pilotos` | 4 |
| `portal_cidadao` | 5 |
| `relatorios` | 16 |
| `shared` | 2 |
| `solicitacoes` | 4 |
| `usuarios` | 9 |
| `uvis_equipes` | 12 |
| `veiculos` | 25 |
| `vigilancia` | 3 |

## app __init__

Fonte: [app/__init__.py](../app/__init__.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/healthz` | `healthz` | 181 | — | — |
| GET | `/healthz/full` | `healthz_full` | 185 | — | — |

## app core routes

Fonte: [app/core/routes.py](../app/core/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/sw.js` | `serve_sw` | 13 | — | — |
| GET | `/forcar_erro` | `forcar_erro` | 17 | `login_required`; `_dev_only()` | — |
| GET | `/__test/erro/<int:code>` | `test_error_code` | 24 | `login_required`; `_dev_only()` | — |

## app modules admin_checklists routes

Fonte: [app/modules/admin_checklists/routes.py](../app/modules/admin_checklists/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/admin/checklists/semanais` | `admin_checklists_semanais` | 21 | `login_required`; `_admin_only()` | `'admin_checklists_semanais.html'` |
| GET | `/admin/checklists/semanais/<int:piloto_id>/<string:semana_inicio>` | `admin_checklist_semanal_detalhe` | 49 | `login_required` | — |
| GET | `/admin/checklists/semanais/<string:actor_type>/<int:actor_id>/<string:semana_inicio>` | `admin_checklist_semanal_detalhe_actor` | 58 | `login_required` | — |
| GET, POST | `/admin/checklists/<string:tipo>/<int:checklist_id>/editar` | `editar_checklist_semanal` | 67 | `login_required`; `_admin_only()` | `'admin_checklist_editar.html'` |

## app modules admin_dashboard routes

Fonte: [app/modules/admin_dashboard/routes.py](../app/modules/admin_dashboard/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/admin` | `admin_dashboard` | 260 | `login_required`; `if not can_access_admin_panel(current_user)`; `can_access_admin_panel()`; `can_edit_admin_panel()` | `'admin.html'` |
| GET | `/admin/exportar_excel` | `exportar_excel` | 345 | `login_required`; `if not can_access_admin_panel(current_user)`; `can_access_admin_panel()` | — |
| POST | `/admin/atualizar/<int:id>` | `atualizar` | 398 | `login_required`; `if not can_edit_admin_panel(current_user)`; `_get_scoped_solicitacao_or_404()`; `can_edit_admin_panel()` | — |
| POST | `/admin/solicitacao/<int:id>/cancelar` | `cancelar_solicitacao_admin` | 443 | `login_required`; `if not can_edit_admin_panel(current_user) and solicitacao.usuario_id != current_user.id`; `_get_scoped_solicitacao_or_404()`; `can_edit_admin_panel()` | — |
| GET | `/admin/canceladas` | `admin_canceladas` | 461 | `login_required`; `if not can_access_admin_panel(current_user)`; `can_access_admin_panel()` | `'admin_canceladas.html'` |
| GET | `/admin/historico-os` | `admin_historico_os` | 512 | `login_required`; `if not can_access_admin_panel(current_user)`; `can_access_admin_panel()` | `'admin_historico_os.html'` |
| GET | `/admin/historico-os/exportar-excel` | `admin_historico_os_exportar_excel` | 560 | `login_required`; `if not can_access_admin_panel(current_user)`; `can_access_admin_panel()` | — |
| GET | `/admin/historico-os/exportar-excel-individuais` | `admin_historico_os_exportar_excel_individuais` | 594 | `login_required`; `if not can_access_admin_panel(current_user)`; `can_access_admin_panel()` | — |
| GET | `/admin/historico-os/exportar-pdf-individuais` | `admin_historico_os_exportar_pdf_individuais` | 624 | `login_required`; `if not can_access_admin_panel(current_user)`; `can_access_admin_panel()` | — |
| GET | `/admin/historico-os/exportar-pdf-individuais/jobs/<job_id>` | `admin_historico_os_pdf_job_status` | 640 | `login_required`; `if not can_access_admin_panel(current_user)`; `if not job or int(job.get('user_id') or 0) != int(current_user.id)`; `can_access_admin_panel()` | — |
| GET | `/admin/historico-os/exportar-pdf-individuais/jobs/<job_id>/download` | `admin_historico_os_pdf_job_download` | 656 | `login_required`; `if not can_access_admin_panel(current_user)`; `if not job or int(job.get('user_id') or 0) != int(current_user.id)`; `can_access_admin_panel()` | — |
| GET | `/admin/os/<int:os_id>/equipe-uvis-formulario` | `admin_equipe_uvis_os_formulario_view` | 683 | `login_required`; `if not can_access_admin_panel(current_user)`; `apply_solicitacao_prefeitura_scope()`; `apply_regiao_scope()`; `can_access_admin_panel()` | `'equipe_uvis_os_formulario.html'` |

## app modules admin_uvis routes

Fonte: [app/modules/admin_uvis/routes.py](../app/modules/admin_uvis/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET, POST | `/admin/uvis/novo` | `admin_uvis_novo` | 39 | `login_required`; `if not is_admin_or_prefeitura_admin(current_user)`; `if is_admin_user(current_user) and (not prefeitura_id)`; `is_admin_user()` | `'admin_uvis_novo.html'`, `'admin_uvis_novo.html'`, `'admin_uvis_novo.html'`, `'admin_uvis_novo.html'`, `'admin_uvis_novo.html'` |
| GET | `/admin/uvis` | `admin_uvis_listar` | 107 | `login_required`; `if not can_access_admin_uvis(current_user)`; `can_access_admin_uvis()`; `is_admin_user()` | `'admin_uvis_listar.html'` |
| GET, POST | `/admin/uvis/<int:id>/editar` | `admin_uvis_editar` | 151 | `login_required`; `if not is_uvis_user(uvis)`; `if is_admin_user(current_user) and (not prefeitura_id)`; `is_uvis_user()`; `is_admin_user()` | `'admin_uvis_editar.html'`, `'admin_uvis_editar.html'`, `'admin_uvis_editar.html'`, `'admin_uvis_editar.html'`, `'admin_uvis_editar.html'` |
| POST | `/admin/uvis/<int:id>/excluir` | `admin_uvis_excluir` | 239 | `login_required`; `if not is_uvis_user(uvis)`; `is_uvis_user()`; `delete_uvis_user()` | — |
| GET | `/admin/uvis/exportar` | `admin_uvis_exportar` | 272 | `login_required`; `if not can_access_admin_uvis(current_user)`; `can_access_admin_uvis()` | — |

## app modules agenda_notificacoes routes

Fonte: [app/modules/agenda_notificacoes/routes.py](../app/modules/agenda_notificacoes/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/agenda` | `agenda` | 18 | `login_required` | `'agenda.html'`, `'erro.html'` |
| GET | `/agenda/rotas-dia` | `agenda_rotas_dia` | 32 | `login_required` | — |
| GET | `/agenda/exportar_excel` | `agenda_exportar_excel` | 43 | `login_required`; `if not can_export_agenda(current_user)`; `can_export_agenda()` | — |
| GET | `/notificacoes/<int:notif_id>/ler` | `ler_notificacao` | 57 | `login_required` | — |
| GET | `/notificacoes` | `notificacoes` | 64 | `login_required` | `'notificacoes.html'` |
| POST | `/notificacoes/<int:notif_id>/excluir` | `excluir_notificacao` | 69 | `login_required` | — |
| POST | `/notificacoes/limpar` | `limpar_notificacoes` | 76 | `login_required` | — |

## app modules agro routes

Fonte: [app/modules/agro/routes.py](../app/modules/agro/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/agro` | `agro_root` | 3705 | `login_required`; `if getattr(current_user, 'tipo_usuario', None) == 'piloto_agro'`; `_require_agro_access()` | — |
| GET | `/agro/piloto` | `agro_piloto_dashboard` | 3714 | `login_required`; `_require_piloto_agro()`; `apply_prefeitura_scope()` | `'piloto_agro_dashboard.html'` |
| GET | `/agro/piloto/os` | `agro_piloto_os_listar` | 3778 | `login_required`; `_require_piloto_agro()` | `'piloto_agro_os_listar.html'` |
| GET | `/agro/piloto/mapeamentos` | `agro_piloto_mapeamentos_listar` | 3816 | `login_required`; `_require_piloto_agro()` | `'piloto_agro_mapeamentos_listar.html'` |
| GET | `/agro/admin` | `admin_agro` | 3863 | `login_required`; `if is_financeiro_agro_only_user(current_user)`; `_require_agro_access()`; `is_financeiro_agro_only_user()` | `'admin_agro.html'` |
| GET | `/agro/financeiro` | `agro_financeiro_dashboard` | 3872 | `login_required`; `_require_agro_access()` | `'agro_financeiro_dashboard.html'` |
| GET | `/agro/financeiro/categorias` | `agro_financeiro_categorias_listar` | 3879 | `login_required`; `if not can_manage_agro_finance_settings(current_user)`; `_require_agro_access()`; `_agro_categoria_scope_filter()`; `can_manage_agro_finance_settings()` | `'agro_financeiro_categorias_listar.html'` |
| GET, POST | `/agro/financeiro/categorias/cadastrar` | `agro_financeiro_categoria_nova` | 3933 | `login_required`; `if not can_manage_agro_finance_settings(current_user)`; `_require_agro_access()`; `can_manage_agro_finance_settings()` | `'agro_financeiro_categoria_form.html'`, `'agro_financeiro_categoria_form.html'` |
| GET, POST | `/agro/financeiro/categorias/<int:subcategoria_id>/editar` | `agro_financeiro_categoria_editar` | 3971 | `login_required`; `if not can_manage_agro_finance_settings(current_user)`; `if subcategoria.categoria.prefeitura_id is None and (not is_admin_global_user(current_user))`; `_require_agro_access()`; `_agro_categoria_scope_filter()`; `can_manage_agro_finance_settings()`; `is_admin_global_user()` | `'agro_financeiro_categoria_form.html'`, `'agro_financeiro_categoria_form.html'` |
| POST | `/agro/financeiro/categorias/<int:subcategoria_id>/alternar` | `agro_financeiro_categoria_alternar` | 4037 | `login_required`; `if not can_manage_agro_finance_settings(current_user)`; `if subcategoria.categoria.prefeitura_id is None and (not is_admin_global_user(current_user))`; `_require_agro_access()`; `_agro_categoria_scope_filter()`; `can_manage_agro_finance_settings()`; `is_admin_global_user()` | — |
| GET | `/agro/bancos` | `agro_bancos_listar` | 4057 | `login_required`; `_require_agro_access()`; `can_edit_agro_finance_panel()` | `'agro_bancos_listar.html'` |
| GET | `/agro/bancos/conciliacao` | `agro_bancos_conciliacao` | 4075 | `login_required`; `_require_agro_access()`; `apply_prefeitura_scope()`; `can_edit_agro_finance_panel()` | `'agro_bancos_conciliacao.html'` |
| GET, POST | `/agro/bancos/cadastrar` | `agro_banco_novo` | 4188 | `login_required`; `_require_agro_finance_edit()` | `'agro_banco_agro_form.html'`, `'agro_banco_agro_form.html'` |
| GET, POST | `/agro/bancos/<int:banco_id>/editar` | `agro_banco_editar` | 4235 | `login_required`; `_require_agro_finance_edit()` | `'agro_banco_agro_form.html'`, `'agro_banco_agro_form.html'` |
| POST | `/agro/bancos/<int:banco_id>/deletar` | `agro_banco_deletar` | 4276 | `login_required`; `_require_agro_finance_edit()` | — |
| GET | `/agro/relatorios/fluxo-caixa/excel` | `agro_fluxo_caixa_exportar_excel` | 4291 | `login_required`; `_require_agro_access()` | — |
| GET | `/agro/relatorios/dre-gerencial/excel` | `agro_dre_gerencial_exportar_excel` | 4304 | `login_required`; `_require_agro_access()` | — |
| GET | `/agro/clientes` | `agro_clientes_listar` | 4317 | `login_required`; `_require_agro_access()`; `can_edit_agro_panel()` | `'agro_clientes_listar.html'` |
| GET | `/agro/clientes-fornecedores` | `agro_clientes_menu` | 4342 | `login_required`; `_require_agro_access()`; `apply_prefeitura_scope()`; `can_edit_agro_panel()`; `can_edit_agro_fornecedores()` | `'agro_clientes_menu.html'` |
| GET, POST | `/agro/clientes/cadastrar` | `agro_cliente_novo` | 4358 | `login_required`; `_require_agro_edit()` | `'agro_cliente_form.html'`, `'agro_cliente_form.html'` |
| GET, POST | `/agro/clientes/<int:cliente_id>/editar` | `agro_cliente_editar` | 4392 | `login_required`; `_require_agro_edit()` | `'agro_cliente_form.html'`, `'agro_cliente_form.html'` |
| POST | `/agro/clientes/<int:cliente_id>/deletar` | `agro_cliente_deletar` | 4439 | `login_required`; `_require_agro_edit()` | — |
| GET | `/agro/fornecedores` | `agro_fornecedores_listar` | 4454 | `login_required`; `_require_agro_access()`; `can_edit_agro_fornecedores()` | `'agro_fornecedores_listar.html'` |
| GET, POST | `/agro/fornecedores/cadastrar` | `agro_fornecedor_novo` | 4479 | `login_required`; `_require_agro_fornecedor_edit()` | `'agro_fornecedor_form.html'`, `'agro_fornecedor_form.html'` |
| GET, POST | `/agro/fornecedores/<int:fornecedor_id>/editar` | `agro_fornecedor_editar` | 4514 | `login_required`; `_require_agro_fornecedor_edit()` | `'agro_fornecedor_form.html'`, `'agro_fornecedor_form.html'` |
| POST | `/agro/fornecedores/<int:fornecedor_id>/deletar` | `agro_fornecedor_deletar` | 4565 | `login_required`; `_require_agro_fornecedor_edit()` | — |
| GET | `/agro/orcamentos` | `agro_orcamentos_listar` | 4580 | `login_required`; `_require_agro_access()`; `can_edit_agro_panel()`; `is_admin_global_user()`; `can_access_agro_panel()` | `'agro_orcamentos_listar.html'` |
| GET, POST | `/agro/orcamentos/cadastrar` | `agro_orcamento_novo` | 4616 | `login_required`; `_require_agro_edit()` | `'agro_orcamento_form.html'`, `'agro_orcamento_form.html'`, `'agro_orcamento_form.html'` |
| GET, POST | `/agro/orcamentos/<int:orcamento_id>/editar` | `agro_orcamento_editar` | 4736 | `login_required`; `_require_agro_edit()` | `'agro_orcamento_form.html'`, `'agro_orcamento_form.html'`, `'agro_orcamento_form.html'` |
| GET, POST | `/agro/orcamentos/<int:orcamento_id>/rd-mapeamento` | `agro_rd_mapeamento_editar` | 4888 | `login_required`; `_require_agro_edit()` | `'agro_rd_mapeamento_form.html'`, `'agro_rd_mapeamento_form.html'` |
| GET | `/agro/orcamentos/template-mapeamento` | `agro_orcamentos_template_mapeamento` | 4950 | `login_required`; `_require_agro_admin()`; `is_admin_global_user()`; `can_edit_agro_panel()` | `'agro_orcamentos_template_mapeamento.html'` |
| POST | `/agro/orcamentos/<int:orcamento_id>/template-mapeamento` | `agro_orcamento_template_mapeamento_salvar` | 4977 | `login_required`; `_require_agro_admin()` | — |
| GET, POST | `/agro/piloto/rd-mapeamento/<int:rd_id>` | `agro_piloto_rd_mapeamento` | 5023 | `login_required`; `_require_piloto_agro()` | `'agro_rd_mapeamento_form.html'`, `'agro_rd_mapeamento_form.html'` |
| GET, POST | `/agro/orcamentos/<int:orcamento_id>/contrato` | `agro_contrato_editar` | 5099 | `login_required`; `_require_agro_edit()`; `if is_admin_global_user(current_user)`; `is_admin_global_user()` | `'agro_contrato_form.html'`, `'agro_contrato_form.html'` |
| GET | `/agro/contratos` | `agro_contratos_listar` | 5220 | `login_required`; `_require_agro_access()`; `can_edit_agro_panel()`; `can_edit_agro_finance_panel()`; `is_admin_global_user()`; `can_access_agro_panel()` | `'agro_contratos_listar.html'` |
| GET | `/agro/contratos/comprovantes` | `agro_contratos_comprovantes` | 5262 | `login_required`; `_require_agro_access()`; `can_edit_agro_panel()`; `can_edit_agro_finance_panel()` | `'agro_contratos_comprovantes.html'` |
| GET | `/agro/financeiro/contas` | `agro_financeiro_contas` | 5293 | `login_required`; `_require_agro_access()`; `can_edit_agro_finance_panel()`; `can_manage_agro_finance_settings()` | `'agro_financeiro_contas.html'` |
| GET | `/agro/financeiro/relatorio-geral` | `agro_relatorio_contas_geral` | 5311 | `login_required`; `_require_agro_access()`; `can_edit_agro_finance_panel()` | `'agro_relatorio_contas_geral.html'` |
| GET | `/agro/financeiro/relatorio-geral/excel` | `agro_relatorio_contas_geral_excel` | 5335 | `login_required`; `_require_agro_access()` | — |
| GET | `/agro/financeiro/relatorio-geral/pdf` | `agro_relatorio_contas_geral_pdf` | 5354 | `login_required`; `_require_agro_access()` | — |
| GET | `/agro/financeiro/contas-receber` | `agro_contas_receber_listar` | 5373 | `login_required`; `_require_agro_access()`; `can_edit_agro_finance_panel()`; `can_manage_agro_finance_settings()` | `'agro_contas_receber_listar.html'` |
| GET | `/agro/financeiro/contas-pagar` | `agro_contas_pagar_listar` | 5419 | `login_required`; `_require_agro_access()`; `can_edit_agro_finance_panel()`; `can_manage_agro_finance_settings()` | `'agro_contas_pagar_listar.html'` |
| GET | `/agro/financeiro` | `agro_financeiro_listar` | 5463 | `login_required`; `_require_agro_access()`; `can_edit_agro_finance_panel()`; `can_manage_agro_finance_settings()` | `'agro_financeiro_listar.html'` |
| GET | `/agro/financeiro/configuracoes` | `agro_financeiro_configuracoes` | 5506 | `login_required`; `if not can_manage_agro_finance_settings(current_user)`; `_require_agro_access()`; `can_manage_agro_finance_settings()` | `'agro_financeiro_configuracoes.html'` |
| POST | `/agro/financeiro/configuracoes` | `agro_financeiro_configuracoes_salvar` | 5524 | `login_required`; `if not can_manage_agro_finance_settings(current_user)`; `_require_agro_access()`; `can_manage_agro_finance_settings()` | — |
| GET, POST | `/agro/financeiro/cadastrar` | `agro_financeiro_novo` | 5557 | `login_required`; `_require_agro_finance_edit()`; `if not can_user_write_agro_finance_competencia(current_user, competencia_ano, competencia_mes)`; `can_user_write_agro_finance_competencia()` | `'agro_financeiro_form.html'`, `'agro_financeiro_form.html'` |
| GET, POST | `/agro/financeiro/<int:lancamento_id>/editar` | `agro_financeiro_editar` | 5675 | `login_required`; `_require_agro_finance_edit()`; `if not can_user_write_agro_finance_competencia(current_user, competencia_ano, competencia_mes)`; `can_user_write_agro_finance_competencia()` | `'agro_financeiro_form.html'`, `'agro_financeiro_form.html'` |
| POST | `/agro/financeiro/<int:lancamento_id>/receber` | `agro_financeiro_receber_os_concluida` | 5793 | `login_required`; `if not can_user_write_agro_finance_competencia(current_user, competencia_ano, competencia_mes)`; `_require_agro_finance_edit()`; `can_user_write_agro_finance_competencia()` | — |
| POST | `/agro/financeiro/<int:lancamento_id>/deletar` | `agro_financeiro_deletar` | 5852 | `login_required`; `_require_agro_finance_edit()` | — |
| GET | `/agro/financeiro/entradas` | `agro_financeiro_entrada_listar` | 5877 | `login_required`; `_require_agro_access()` | — |
| GET, POST | `/agro/financeiro/entradas/cadastrar` | `agro_financeiro_entrada_novo` | 5904 | `login_required`; `_require_agro_finance_edit()`; `if quantidade_parcelas == 1 and (not can_user_write_agro_finance_competencia(current_user, payload['competencia'].year, payload['competencia'].month))`; `if allowed_retroactive_dates and form.get('confirmar_lancamento_retroativo') != '1'`; `_split_agro_retroactive_dates_by_permission()`; `if allowed_retroactive_due_dates and form.get('confirmar_lancamento_retroativo') != '1'`; `_check_agro_installment_dates_permissions()`; `can_user_write_agro_finance_competencia()` | `'agro_financeiro_entrada_form.html'`, `'agro_financeiro_entrada_form.html'` |
| GET, POST | `/agro/financeiro/entradas/<int:lancamento_id>/editar` | `agro_financeiro_entrada_editar` | 6031 | `login_required`; `_require_agro_finance_edit()`; `if not can_user_write_agro_finance_competencia(current_user, payload['competencia'].year, payload['competencia'].month)`; `can_user_write_agro_finance_competencia()`; `_split_agro_retroactive_dates_by_permission()`; `apply_prefeitura_scope()` | `'agro_financeiro_entrada_form.html'`, `'agro_financeiro_entrada_form.html'` |
| POST | `/agro/financeiro/entradas/<int:lancamento_id>/deletar` | `agro_financeiro_entrada_deletar` | 6137 | `login_required`; `_require_agro_finance_edit()`; `apply_prefeitura_scope()` | — |
| GET | `/agro/financeiro/saidas` | `agro_financeiro_saida_listar` | 6165 | `login_required`; `_require_agro_access()` | — |
| GET, POST | `/agro/financeiro/saidas/cadastrar` | `agro_financeiro_saida_novo` | 6195 | `login_required`; `_require_agro_finance_edit()`; `if quantidade_parcelas == 1 and (not can_user_write_agro_finance_competencia(current_user, payload['competencia'].year, payload['competencia'].month))`; `if allowed_retroactive_dates and form.get('confirmar_lancamento_retroativo') != '1'`; `_split_agro_retroactive_dates_by_permission()`; `if allowed_retroactive_due_dates and form.get('confirmar_lancamento_retroativo') != '1'`; `_check_agro_installment_dates_permissions()`; `can_user_write_agro_finance_competencia()` | `'agro_financeiro_saida_form.html'`, `'agro_financeiro_saida_form.html'` |
| GET, POST | `/agro/financeiro/saidas/<int:lancamento_id>/editar` | `agro_financeiro_saida_editar` | 6333 | `login_required`; `_require_agro_finance_edit()`; `if not can_user_write_agro_finance_competencia(current_user, payload['competencia'].year, payload['competencia'].month)`; `can_user_write_agro_finance_competencia()`; `_split_agro_retroactive_dates_by_permission()`; `apply_prefeitura_scope()` | `'agro_financeiro_saida_form.html'`, `'agro_financeiro_saida_form.html'` |
| POST | `/agro/financeiro/saidas/<int:lancamento_id>/deletar` | `agro_financeiro_saida_deletar` | 6451 | `login_required`; `_require_agro_finance_edit()`; `apply_prefeitura_scope()` | — |
| GET | `/agro/caixa` | `agro_caixa_diario` | 6479 | `login_required`; `_require_agro_access()`; `can_edit_agro_finance_panel()` | `'agro_caixa_diario.html'` |
| POST | `/agro/caixa/abrir` | `agro_caixa_abrir` | 6494 | `login_required`; `_require_agro_finance_edit()` | — |
| POST | `/agro/caixa/fechar` | `agro_caixa_fechar` | 6544 | `login_required`; `_require_agro_finance_edit()` | — |
| GET | `/agro/contratos/template` | `agro_contratos_template` | 6574 | `login_required`; `_require_agro_admin()`; `can_edit_agro_panel()`; `can_edit_agro_finance_panel()` | `'agro_contratos_template.html'` |
| POST | `/agro/contratos/<int:contrato_id>/template` | `agro_contrato_template_salvar` | 6593 | `login_required`; `_require_agro_admin()` | — |
| POST | `/agro/contratos/<int:contrato_id>/deletar` | `agro_contrato_deletar` | 6615 | `login_required`; `_require_agro_admin()` | — |
| POST | `/agro/contratos/<int:contrato_id>/comprovante-pagamento` | `agro_contrato_comprovante_pagamento_upload` | 6630 | `login_required`; `_require_agro_payment_receipt_edit()` | — |
| GET | `/agro/contratos/<int:contrato_id>/comprovante-pagamento` | `agro_contrato_comprovante_pagamento` | 6651 | `login_required`; `_require_agro_access()` | — |
| POST | `/agro/contratos/<int:contrato_id>/comprovante-pagamento/remover` | `agro_contrato_comprovante_pagamento_remover` | 6668 | `login_required`; `_require_agro_payment_receipt_edit()` | — |
| GET | `/agro/orcamentos/<int:orcamento_id>/anexo` | `agro_orcamento_anexo` | 6681 | `login_required`; `_require_agro_access()` | — |
| GET | `/agro/orcamentos/<int:orcamento_id>/pdf` | `agro_orcamento_pdf` | 6692 | `login_required`; `_require_agro_access()` | — |
| GET | `/agro/orcamentos/<int:orcamento_id>/contrato/pdf` | `agro_contrato_pdf` | 6708 | `login_required`; `_require_agro_access()` | — |
| GET | `/agro/os/<int:os_id>/relatorio/pdf` | `agro_os_relatorio_pdf` | 6718 | `login_required`; `_require_agro_edit()` | — |
| POST | `/agro/os/<int:os_id>/deletar` | `agro_os_deletar` | 6732 | `login_required`; `_require_agro_admin()` | — |
| GET | `/agro/os` | `agro_os_listar` | 6743 | `login_required`; `_require_agro_access()`; `can_edit_agro_panel()`; `is_admin_global_user()`; `can_access_agro_panel()` | `'agro_os_listar.html'` |
| GET | `/agro/logs-voo` | `agro_logs_voo` | 6769 | `login_required`; `if not can_access_agro_flight_logs(current_user)`; `can_access_agro_flight_logs()`; `can_import_agro_flight_logs()` | `'agro_logs_voo.html'`, `'erro.html'` |
| GET | `/agro/logs-voo/exportar` | `agro_logs_voo_exportar` | 6797 | `login_required`; `if not can_access_agro_flight_logs(current_user)`; `can_access_agro_flight_logs()` | — |
| POST | `/agro/logs-voo/importar-excel` | `agro_logs_voo_importar_excel` | 6811 | `login_required`; `if not can_import_agro_flight_logs(current_user)`; `can_import_agro_flight_logs()` | — |
| POST | `/agro/logs-voo/importar-kml` | `agro_logs_voo_importar_kml` | 6837 | `login_required`; `if not can_import_agro_flight_logs(current_user)`; `can_import_agro_flight_logs()` | — |
| POST | `/agro/logs-voo/rota/<int:route_id>/vincular-os` | `agro_logs_voo_vincular_os` | 6866 | `login_required`; `if not can_import_agro_flight_logs(current_user)`; `can_import_agro_flight_logs()` | — |
| POST | `/agro/logs-voo/rota/<int:route_id>/desvincular-os` | `agro_logs_voo_desvincular_os` | 6885 | `login_required`; `if not can_import_agro_flight_logs(current_user)`; `can_import_agro_flight_logs()` | — |
| GET | `/api/agro/kml-route/<int:route_id>` | `api_agro_kml_route` | 6895 | `login_required`; `if not can_access_agro_kml_route(current_user, route_id)`; `can_access_agro_kml_route()` | — |
| GET | `/agro/logs-voo/rota/<int:route_id>/kml` | `agro_logs_voo_baixar_kml` | 6902 | `login_required`; `if not can_access_agro_kml_route(current_user, route_id)`; `can_access_agro_kml_route()` | — |
| GET, POST | `/agro/contratos/<int:contrato_id>/os/cadastrar` | `agro_os_nova` | 6924 | `login_required`; `_require_agro_access()`; `apply_prefeitura_scope()` | `'agro_os_form.html'`, `'agro_os_form.html'`, `'agro_os_form.html'`, `'agro_os_form.html'` |
| GET, POST | `/agro/os/<int:os_id>/editar` | `agro_os_editar` | 7098 | `login_required`; `_require_agro_edit()` | `'agro_os_form.html'`, `'agro_os_form.html'`, `'agro_os_form.html'`, `'agro_os_form.html'` |
| POST | `/agro/orcamentos/<int:orcamento_id>/deletar` | `agro_orcamento_deletar` | 7247 | `login_required`; `_require_agro_edit()` | — |
| GET | `/agro/equipes` | `agro_equipes_listar` | 7264 | `login_required`; `_require_agro_access()`; `apply_prefeitura_scope()`; `can_edit_agro_panel()` | `'agro_equipes_listar.html'` |
| GET, POST | `/agro/equipes/cadastrar` | `agro_equipe_nova` | 7286 | `login_required`; `_require_agro_edit()` | `'agro_equipe_form.html'`, `'agro_equipe_form.html'` |
| GET, POST | `/agro/equipes/<int:equipe_id>/editar` | `agro_equipe_editar` | 7311 | `login_required`; `_require_agro_edit()` | `'agro_equipe_form.html'`, `'agro_equipe_form.html'` |
| POST | `/agro/equipes/<int:equipe_id>/deletar` | `agro_equipe_deletar` | 7338 | `login_required`; `_require_agro_edit()` | — |
| GET | `/agro/pilotos` | `agro_pilotos_listar` | 7351 | `login_required`; `_require_agro_access()`; `apply_prefeitura_scope()`; `can_edit_agro_panel()` | `'agro_pilotos_listar.html'` |
| GET, POST | `/agro/pilotos/cadastrar` | `agro_piloto_novo` | 7375 | `login_required`; `_require_agro_edit()`; `apply_prefeitura_scope()` | `'agro_piloto_form.html'`, `'agro_piloto_form.html'` |
| GET, POST | `/agro/pilotos/<int:piloto_id>/editar` | `agro_piloto_editar` | 7413 | `login_required`; `_require_agro_edit()`; `apply_prefeitura_scope()` | `'agro_piloto_form.html'`, `'agro_piloto_form.html'` |
| POST | `/agro/pilotos/<int:piloto_id>/deletar` | `agro_piloto_deletar` | 7464 | `login_required`; `_require_agro_edit()` | — |
| GET | `/agro/equipamentos` | `agro_equipamentos_listar` | 7476 | `login_required`; `_require_agro_access()`; `apply_prefeitura_scope()`; `can_edit_agro_panel()` | `'agro_equipamentos_listar.html'` |
| GET, POST | `/agro/equipamentos/cadastrar` | `agro_equipamento_novo` | 7504 | `login_required`; `_require_agro_edit()`; `apply_prefeitura_scope()` | `'agro_equipamento_form.html'`, `'agro_equipamento_form.html'` |
| GET, POST | `/agro/equipamentos/<int:equipamento_id>/editar` | `agro_equipamento_editar` | 7540 | `login_required`; `_require_agro_edit()`; `apply_prefeitura_scope()` | `'agro_equipamento_form.html'`, `'agro_equipamento_form.html'` |
| POST | `/agro/equipamentos/<int:equipamento_id>/deletar` | `agro_equipamento_deletar` | 7602 | `login_required`; `_require_agro_edit()` | — |

## app modules agro talent_bank_routes

Fonte: [app/modules/agro/talent_bank_routes.py](../app/modules/agro/talent_bank_routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/agro/banco-de-talentos` | `agro_talentos_listar` | 84 | `login_required`; `_require_access()`; `apply_prefeitura_scope()`; `can_edit_agro_panel()` | `'agro_talentos_listar.html'` |
| GET, POST | `/agro/banco-de-talentos/novo` | `agro_talento_novo` | 136 | `login_required`; `_require_edit()` | `'agro_talento_upload.html'`, `'agro_talento_upload.html'`, `'agro_talento_upload.html'` |
| GET, POST | `/agro/banco-de-talentos/<int:curriculo_id>` | `agro_talento_detalhe` | 198 | `login_required`; `_require_access()`; `_require_edit()`; `can_edit_agro_panel()` | `'agro_talento_detalhe.html'` |
| GET | `/agro/banco-de-talentos/<int:curriculo_id>/pdf` | `agro_talento_pdf` | 226 | `login_required`; `_require_access()` | — |
| POST | `/agro/banco-de-talentos/<int:curriculo_id>/reprocessar` | `agro_talento_reprocessar` | 247 | `login_required`; `_require_edit()` | — |
| POST | `/agro/banco-de-talentos/<int:curriculo_id>/deletar` | `agro_talento_deletar` | 276 | `login_required`; `_require_edit()` | — |

## app modules anexos routes

Fonte: [app/modules/anexos/routes.py](../app/modules/anexos/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/solicitacao/<int:id>/anexo` | `baixar_anexo` | 15 | `login_required`; `if not can_view_attachment(current_user, pedido)`; `can_view_attachment()` | — |
| GET | `/admin/solicitacao/<int:id>/anexo` | `baixar_anexo_admin` | 16 | `login_required`; `if not can_view_attachment(current_user, pedido)`; `can_view_attachment()` | — |
| POST | `/admin/solicitacao/<int:id>/remover_anexo` | `remover_anexo` | 36 | `login_required`; `if not can_remove_attachment(current_user, pedido)`; `can_remove_attachment()` | — |

## app modules auditoria routes

Fonte: [app/modules/auditoria/routes.py](../app/modules/auditoria/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/admin/logs-usuarios` | `admin_logs_usuarios` | 20 | `login_required`; `_dev_only()` | `'admin_logs_usuarios.html'` |

## app modules auth routes

Fonte: [app/modules/auth/routes.py](../app/modules/auth/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET, POST | `/login` | `login` | 19 | `if current_user.is_authenticated` | `'login.html'` |
| GET, POST | `/uvis-operacional/login` | `login_uvis_operacional` | 50 | `if current_user.is_authenticated` | `'login_uvis_operacional.html'` |
| GET, POST | `/agro/login` | `login_piloto_agro` | 76 | `if current_user.is_authenticated` | `'login_piloto_agro.html'` |
| GET | `/logout` | `logout` | 102 | `login_required` | — |

## app modules backup routes

Fonte: [app/modules/backup/routes.py](../app/modules/backup/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/backup` | `backup_page` | 18 | `login_required`; `if not is_dev_user(current_user)`; `is_dev_user()` | `'backup_aguarde.html'`, `'backup_aguarde.html'` |
| GET | `/backup/status` | `backup_status` | 43 | `login_required`; `if not is_dev_user(current_user)`; `is_dev_user()` | — |
| GET | `/backups` | `backups_list_page` | 51 | `login_required`; `if not is_dev_user(current_user)`; `is_dev_user()` | `'backup_lista.html'`, `'backup_lista.html'` |

## app modules canceladas routes

Fonte: [app/modules/canceladas/routes.py](../app/modules/canceladas/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| POST | `/solicitacao/<int:id>/cancelar` | `cancelar_solicitacao` | 11 | `login_required`; `if not is_admin_global_user(current_user) and solicitacao.usuario_id != current_user.id`; `is_admin_global_user()` | — |
| GET | `/canceladas` | `solicitacoes_canceladas` | 25 | `login_required`; `if current_user.tipo_usuario in {'piloto', 'equipe_oceano'}` | `'dashboard_canceladas.html'` |

## app modules cep routes

Fonte: [app/modules/cep/routes.py](../app/modules/cep/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/api/cep/<cep>` | `api_cep` | 8 | `login_required` | — |
| POST | `/api/cep/busca-endereco` | `api_cep_by_address` | 18 | `login_required` | — |

## app modules chatbot routes

Fonte: [app/modules/chatbot/routes.py](../app/modules/chatbot/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| POST | `/api/uvis/chatbot` | `uvis_chatbot` | 16 | `login_required` | — |
| POST | `/api/admin/chatbot` | `admin_chatbot` | 23 | `login_required`; `if not can_access_admin_chatbot(current_user)`; `can_access_admin_chatbot()` | — |
| POST | `/api/agro/admin/chatbot` | `agro_admin_chatbot` | 33 | `login_required`; `if not can_access_agro_admin_chatbot(current_user)`; `can_access_agro_admin_chatbot()` | — |
| POST | `/api/agro/piloto/chatbot` | `agro_piloto_chatbot` | 43 | `login_required`; `if not can_access_agro_piloto_chatbot(current_user)`; `can_access_agro_piloto_chatbot()` | — |

## app modules clientes routes

Fonte: [app/modules/clientes/routes.py](../app/modules/clientes/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/clientes` | `clientes_menu` | 39 | `login_required`; `if not _can_manage_clientes(current_user)`; `_can_manage_clientes()` | `'clientes_menu.html'` |
| GET, POST | `/clientes/cadastrar` | `cadastrar_clientes` | 54 | `login_required`; `if not _can_manage_clientes(current_user)`; `_can_manage_clientes()` | `'cadastrar_clientes.html'`, `'cadastrar_clientes.html'` |
| GET | `/clientes/listar` | `listar_clientes` | 150 | `login_required`; `if not _can_manage_clientes(current_user)`; `_can_manage_clientes()` | `'listar_clientes.html'` |
| GET, POST | `/clientes/<int:cliente_id>/editar` | `editar_cliente` | 212 | `login_required`; `if not _can_manage_clientes(current_user)`; `_get_scoped_cliente_or_404()`; `_can_manage_clientes()` | `'editar_cliente.html'`, `'editar_cliente.html'` |
| POST | `/clientes/<int:cliente_id>/deletar` | `deletar_cliente` | 292 | `login_required`; `if not _can_manage_clientes(current_user)`; `_get_scoped_cliente_or_404()`; `_can_manage_clientes()` | — |

## app modules dashboard routes

Fonte: [app/modules/dashboard/routes.py](../app/modules/dashboard/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/` | `dashboard` | 21 | `login_required`; `if current_user.tipo_usuario in {'piloto', 'equipe_oceano'}`; `if current_user.tipo_usuario == 'piloto_agro'`; `if current_user.tipo_usuario == 'equipe_uvis'`; `if is_agro_finance_user(current_user)`; `if current_user.tipo_usuario in ADMIN_PANEL_VIEW_TYPES`; `is_agro_finance_user()` | `'dashboard.html'` |
| GET | `/uvis/historico-os` | `uvis_historico_os` | 45 | `login_required` | `'uvis_os_historico.html'` |
| GET, POST | `/uvis/os/<int:os_id>/formulario` | `uvis_os_formulario_view` | 60 | `login_required` | `'piloto_os_formulario.html'` |
| GET | `/uvis/os/<int:os_id>/equipe-formulario` | `uvis_equipe_os_formulario_view` | 103 | `login_required` | `'equipe_uvis_os_formulario.html'` |

## app modules denuncias routes

Fonte: [app/modules/denuncias/routes.py](../app/modules/denuncias/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/denuncias` | `denuncias_listar` | 37 | `login_required`; `if not can_access_denuncias(current_user)`; `if is_regional_user(current_user)`; `if getattr(current_user, 'tipo_usuario', None) == 'uvis'`; `is_regional_user()`; `can_access_denuncias()` | `'denuncias_listar.html'` |
| GET | `/denuncias/<int:denuncia_id>` | `denuncia_detalhe` | 69 | `login_required`; `if not can_access_denuncias(current_user)`; `get_denuncia_scoped_or_404()`; `can_access_denuncias()` | `'denuncia_detalhe.html'` |
| GET | `/coordenadoria/denuncias` | `coordenadoria_denuncias_listar` | 85 | `login_required`; `if not is_regional_user(current_user)`; `is_regional_user()` | `'denuncias_listar.html'` |
| GET | `/coordenadoria/denuncias/<int:denuncia_id>` | `coordenadoria_denuncia_detalhe` | 113 | `login_required`; `if not is_regional_user(current_user)`; `get_denuncia_scoped_or_404()`; `is_regional_user()` | `'denuncia_detalhe.html'` |
| POST | `/denuncias/<int:denuncia_id>/encaminhar-coordenadoria` | `denuncia_encaminhar_coordenadoria` | 129 | `login_required`; `if not can_access_denuncias(current_user)`; `can_access_denuncias()` | — |
| POST | `/coordenadoria/denuncias/<int:denuncia_id>/designar-uvis` | `coordenadoria_denuncia_designar_uvis` | 148 | `login_required`; `if not is_regional_user(current_user)`; `get_denuncia_scoped_or_404()`; `is_regional_user()` | — |
| GET | `/uvis/denuncias` | `uvis_denuncias_listar` | 163 | `login_required`; `if getattr(current_user, 'tipo_usuario', None) != 'uvis'` | `'denuncias_listar.html'` |
| GET, POST | `/uvis/denuncias/<int:denuncia_id>` | `uvis_denuncia_detalhe` | 191 | `login_required`; `if getattr(current_user, 'tipo_usuario', None) != 'uvis'`; `get_denuncia_scoped_or_404()`; `can_use_custom_visit_other()` | `'denuncia_uvis_detalhe.html'` |
| POST | `/denuncias/<int:denuncia_id>/arquivar` | `denuncia_arquivar` | 229 | `login_required`; `if not can_access_denuncias(current_user)`; `can_access_denuncias()` | — |
| GET | `/denuncias/anexos/<int:anexo_id>` | `denuncia_anexo` | 244 | `login_required`; `if not can_access_denuncias(current_user)`; `if not can_access_denuncia(current_user, anexo.denuncia)`; `can_access_denuncias()`; `can_access_denuncia()` | — |

## app modules dev_dashboard routes

Fonte: [app/modules/dev_dashboard/routes.py](../app/modules/dev_dashboard/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| POST | `/api/watchdog/deploy-events` | `watchdog_deploy_event` | 33 | `require_watchdog_token()` | — |
| GET | `/dev` | `dev_dashboard` | 49 | `login_required`; `require_dev_user()` | `'dev_dashboard.html'` |
| GET | `/dev/data` | `dev_dashboard_data` | 55 | `login_required`; `require_dev_user()` | — |
| GET | `/dev/errors/<int:log_id>` | `dev_dashboard_error_detail` | 61 | `login_required`; `require_dev_user()` | — |
| POST | `/dev/checks/<slug>` | `dev_dashboard_manual_check` | 70 | `login_required`; `require_dev_user()` | — |

## app modules dji_flight_logs routes

Fonte: [app/modules/dji_flight_logs/routes.py](../app/modules/dji_flight_logs/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/relatorios/dji-logs` | `relatorios_dji_logs` | 24 | `login_required`; `if not can_access_dji_logs(current_user)`; `can_access_dji_logs()`; `can_import_dji_logs()` | `'relatorios_dji_logs.html'`, `'erro.html'` |
| GET | `/relatorios/dji-logs/exportar` | `exportar_dji_logs_excel` | 53 | `login_required`; `if not can_access_dji_logs(current_user)`; `can_access_dji_logs()` | — |
| POST | `/relatorios/dji-logs/importar` | `importar_dji_logs` | 68 | `login_required`; `if not can_import_dji_logs(current_user)`; `can_import_dji_logs()` | — |
| POST | `/relatorios/dji-logs/importar-kml` | `importar_dji_kml` | 96 | `login_required`; `if not can_import_dji_logs(current_user)`; `can_import_dji_logs()` | — |
| GET | `/api/dji-kml-route/<int:route_id>` | `api_dji_kml_route` | 126 | `login_required`; `if not can_access_dji_kml_route(current_user, route_id)`; `can_access_dji_kml_route()` | — |
| POST | `/relatorios/dji-logs/rota/<int:route_id>/vincular-os` | `vincular_dji_kml_route_os` | 134 | `login_required`; `if not can_import_dji_logs(current_user)`; `can_import_dji_logs()` | — |
| POST | `/relatorios/dji-logs/rota/<int:route_id>/excluir` | `excluir_dji_kml_route` | 162 | `login_required`; `if not can_import_dji_logs(current_user)`; `can_import_dji_logs()` | — |
| GET | `/relatorios/dji-logs/rota/<int:route_id>` | `visualizar_dji_kml_route` | 185 | `login_required`; `if not can_access_dji_kml_route(current_user, route_id)`; `can_access_dji_kml_route()` | `'dji_kml_route_map.html'` |
| GET | `/relatorios/dji-logs/rota/<int:route_id>/kml` | `baixar_dji_kml_route` | 203 | `login_required`; `if not can_access_dji_kml_route(current_user, route_id)`; `can_access_dji_kml_route()` | — |

## app modules drones_import routes

Fonte: [app/modules/drones_import/routes.py](../app/modules/drones_import/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/drones/importar-planilha` | `importar_planilha_drones` | 49 | `login_required` | — |
| GET | `/agro/equipamentos/importar-planilha` | `agro_importar_planilha_drones` | 54 | `login_required` | — |
| POST | `/api/drones/importar-planilha` | `importar_planilha_drones_api` | 59 | `login_required`; `_require_import_permission()` | — |

## app modules equipamentos routes

Fonte: [app/modules/equipamentos/routes.py](../app/modules/equipamentos/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/equipamentos` | `listar_equipamentos` | 54 | `login_required` | `'equipamentos_listar.html'` |
| GET | `/equipamentos/drones` | `listar_drones` | 59 | `login_required` | `'drones_listar.html'` |
| GET | `/equipamentos/baterias` | `listar_baterias` | 70 | `login_required` | `'baterias_listar.html'` |
| GET, POST | `/drones/cadastrar` | `cadastrar_drone` | 81 | `login_required`; `_require_admin_or_operario()` | `'cadastrar_drone.html'`, `'cadastrar_drone.html'`, `'cadastrar_drone.html'` |
| GET, POST | `/drones/<int:drone_id>/editar` | `editar_drone` | 109 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_drone_or_404()` | `'editar_drone.html'`, `'editar_drone.html'`, `'editar_drone.html'` |
| POST | `/drones/<int:drone_id>/deletar` | `deletar_drone` | 155 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_drone_or_404()` | — |
| GET, POST | `/baterias/cadastrar` | `cadastrar_bateria` | 171 | `login_required`; `if drone_id_pre and apply_prefeitura_scope(Drones.query, current_user, Drones.prefeitura_id).filter(Drones.id == drone_id_pre).first()`; `_require_admin_or_operario()`; `apply_prefeitura_scope()` | `'cadastrar_bateria.html'`, `'cadastrar_bateria.html'`, `'cadastrar_bateria.html'` |
| GET, POST | `/baterias/<int:bateria_id>/editar` | `editar_bateria` | 203 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_bateria_or_404()` | `'editar_bateria.html'`, `'editar_bateria.html'`, `'editar_bateria.html'` |
| POST | `/baterias/<int:bateria_id>/deletar` | `deletar_bateria` | 249 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_bateria_or_404()` | — |
| GET | `/equipamentos/em-manutencao` | `equipamentos_manutencao` | 265 | `login_required` | `'equipamentos_manutencao.html'` |
| GET | `/equipamentos/manutencoes/historico` | `equipamentos_manutencoes_historico` | 275 | `login_required`; `_require_admin_or_operario()` | `'equipamentos_manutencoes_historico.html'` |
| GET | `/equipamentos/manutencoes/historico/excel` | `equipamentos_manutencoes_historico_excel` | 284 | `login_required`; `_require_admin_or_operario()` | — |
| GET | `/equipamentos/manutencoes/pecas/historico` | `equipamentos_manutencoes_pecas_historico` | 291 | `login_required`; `_require_admin_or_operario()` | `'equipamentos_manutencoes_pecas_historico.html'` |
| GET | `/equipamentos/manutencoes/pecas/historico/excel` | `equipamentos_manutencoes_pecas_historico_excel` | 300 | `login_required`; `_require_admin_or_operario()` | — |
| GET | `/equipamentos/manutencoes/<int:manutencao_id>` | `equipamento_manutencao_detalhe` | 307 | `login_required`; `_require_admin_or_operario()`; `get_manutencao_scoped_or_404()` | `'equipamento_manutencao_detalhe.html'` |
| GET, POST | `/equipamentos/<int:drone_id>/manutencao/pecas` | `equipamento_manutencao_pecas` | 318 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_drone_or_404()` | `'equipamento_manutencao_pecas.html'` |
| GET | `/equipamentos/<int:drone_id>/manutencao/pdf` | `equipamento_manutencao_pdf` | 350 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_drone_or_404()` | — |
| GET | `/equipamentos/manutencoes/<int:manutencao_id>/pdf` | `equipamento_manutencao_historico_pdf` | 365 | `login_required`; `_require_admin_or_operario()`; `get_manutencao_scoped_or_404()` | — |
| POST | `/equipamentos/<int:drone_id>/manutencao/encerrar` | `equipamento_manutencao_encerrar` | 379 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_drone_or_404()`; `if not encerrar_manutencao_drone(drone, user=current_user)` | — |
| POST | `/equipamentos/baterias/update_ciclos/<int:id>` | `update_ciclos` | 395 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_bateria_or_404()` | — |
| POST | `/drones/<int:drone_id>/manutencao` | `enviar_manutencao_drone` | 402 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_drone_or_404()`; `if not send_drone_to_manutencao(drone, user=current_user)` | — |

## app modules equipe_uvis_dashboard routes

Fonte: [app/modules/equipe_uvis_dashboard/routes.py](../app/modules/equipe_uvis_dashboard/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/equipe-uvis` | `dashboard_equipe_uvis` | 20 | `login_required`; `if not _can_access_equipe_uvis_panel(current_user)`; `_can_access_equipe_uvis_panel()` | `'dashboard_equipe_uvis.html'` |
| GET, POST | `/equipe-uvis/os/<int:os_id>/formulario` | `equipe_uvis_os_formulario_view` | 41 | `login_required`; `if not _can_access_equipe_uvis_panel(current_user)`; `_can_access_equipe_uvis_panel()` | `'piloto_os_formulario.html'` |
| GET | `/equipe-uvis/os/historico` | `equipe_uvis_os_historico` | 83 | `login_required`; `if not _can_access_equipe_uvis_panel(current_user)`; `_can_access_equipe_uvis_panel()` | `'equipe_uvis_os_historico.html'` |
| POST | `/equipe-uvis/os/<int:os_id>/concluir` | `equipe_uvis_concluir_os` | 98 | `login_required`; `if not _can_access_equipe_uvis_panel(current_user)`; `_can_access_equipe_uvis_panel()` | — |

## app modules equipes routes

Fonte: [app/modules/equipes/routes.py](../app/modules/equipes/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET, POST | `/equipes/cadastrar` | `cadastrar_equipes` | 31 | `login_required`; `_require_admin_or_operario()`; `apply_prefeitura_scope()` | `'cadastrar_equipes.html'`, `'cadastrar_equipes.html'`, `'cadastrar_equipes.html'` |
| GET | `/equipes` | `listar_equipes` | 169 | `login_required`; `if tipo not in ['dev', 'diretor', 'admin', 'visualizar', 'prefeitura_admin']` | `'listar_equipes.html'` |
| POST | `/equipes/<int:equipe_id>/credenciais` | `atualizar_credenciais_equipe` | 246 | `login_required`; `_require_admin_or_operario()`; `apply_prefeitura_scope()` | — |
| GET, POST | `/equipes/<int:equipe_id>/editar` | `editar_equipe` | 273 | `login_required`; `_require_admin_or_operario()`; `apply_prefeitura_scope()` | `'editar_equipe.html'`, `'editar_equipe.html'` |
| POST | `/equipes/<int:equipe_id>/deletar` | `deletar_equipe` | 437 | `login_required`; `_require_admin_or_operario()`; `apply_prefeitura_scope()` | — |

## app modules estoque routes

Fonte: [app/modules/estoque/routes.py](../app/modules/estoque/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/estoque` | `estoque_listar` | 26 | `login_required`; `_require_estoque_access()` | `'estoque_listar.html'` |
| GET | `/estoque/export/excel` | `estoque_export_excel` | 33 | `login_required`; `_require_estoque_access()` | — |
| GET, POST | `/estoque/novo` | `estoque_novo` | 40 | `login_required`; `_require_estoque_access()` | `'estoque_form.html'`, `'estoque_form.html'` |
| GET, POST | `/estoque/<int:peca_id>/editar` | `estoque_editar` | 64 | `login_required`; `_require_estoque_access()`; `get_peca_scoped_or_404()` | `'estoque_form.html'`, `'estoque_form.html'` |
| POST | `/estoque/<int:peca_id>/deletar` | `estoque_deletar` | 88 | `login_required`; `_require_estoque_access()`; `get_peca_scoped_or_404()` | — |

## app modules feedback routes

Fonte: [app/modules/feedback/routes.py](../app/modules/feedback/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/feedback/notificacoes/status` | `feedback_notificacoes_status` | 209 | `login_required`; `if not can_access_feedback(current_user)`; `can_access_feedback()` | — |
| GET | `/feedback` | `feedback_listar` | 219 | `login_required`; `_require_dev_bug_access()`; `get_accessible_uvis()`; `can_view_all_feedback()` | `'feedback_listar.html'` |
| GET | `/bugs` | `bugs_listar` | 297 | `login_required`; `_require_bug_report_access()` | `'bugs_listar.html'` |
| GET | `/bugs/ajuda` | `bugs_ajuda` | 352 | `login_required`; `_require_bug_report_access()` | `'bugs_ajuda.html'` |
| GET, POST | `/feedback/novo` | `feedback_novo` | 363 | `login_required`; `if not user_can_use_uvis(current_user, uvis_usuario)`; `_require_bug_report_access()`; `is_covisa_user()`; `can_moderate_feedback()`; `get_accessible_uvis()`; `if is_covisa_user(current_user) and form['uvis_id'] == getattr(current_user, 'id', None)`; `user_can_use_uvis()`; `if is_dev_user(current_user)`; `is_dev_user()` | `'feedback_form.html'`, `'feedback_form.html'` |
| GET, POST | `/bugs/novo` | `bug_report_novo` | 364 | `login_required`; `if not user_can_use_uvis(current_user, uvis_usuario)`; `_require_bug_report_access()`; `is_covisa_user()`; `can_moderate_feedback()`; `get_accessible_uvis()`; `if is_covisa_user(current_user) and form['uvis_id'] == getattr(current_user, 'id', None)`; `user_can_use_uvis()`; `if is_dev_user(current_user)`; `is_dev_user()` | `'feedback_form.html'`, `'feedback_form.html'` |
| GET | `/feedback/<int:topico_id>` | `feedback_detalhe` | 503 | `login_required`; `can_moderate_feedback_topic()`; `_require_dev_bug_access()`; `can_view_all_feedback()` | `'feedback_detalhe.html'` |
| GET | `/bugs/<int:topico_id>/acompanhar` | `bug_acompanhamento` | 531 | `login_required`; `_require_bug_report_access()` | `'bug_acompanhamento.html'` |
| GET | `/feedback/<int:topico_id>/status` | `feedback_status` | 549 | `login_required`; `if not is_dev_user(current_user)`; `is_dev_user()` | — |
| POST | `/feedback/<int:topico_id>/comentar` | `feedback_comentar` | 568 | `login_required`; `_require_dev_bug_access()` | — |
| GET | `/feedback/anexos/<int:anexo_id>` | `feedback_anexo` | 595 | `login_required`; `if not can_view_as_dev and (not can_view_as_coordination)`; `if is_regional_user(current_user)`; `is_dev_user()`; `can_view_feedback_attachment()`; `is_regional_user()`; `if is_covisa_user(current_user)`; `is_covisa_user()` | — |
| POST | `/feedback/<int:topico_id>/comentarios/<int:comment_id>/editar` | `feedback_comentario_editar` | 641 | `login_required`; `if not can_manage_feedback_comment(current_user, comentario)`; `_require_dev_bug_access()`; `can_manage_feedback_comment()` | — |
| POST | `/feedback/<int:topico_id>/comentarios/<int:comment_id>/apagar` | `feedback_comentario_apagar` | 662 | `login_required`; `if not can_manage_feedback_comment(current_user, comentario)`; `_require_dev_bug_access()`; `can_manage_feedback_comment()` | — |
| POST | `/feedback/<int:topico_id>/atualizar` | `feedback_atualizar` | 678 | `login_required`; `if not can_moderate_feedback_topic(current_user, topico)`; `_require_dev_bug_access()`; `can_moderate_feedback_topic()` | — |
| POST | `/feedback/<int:topico_id>/assumir` | `feedback_assumir` | 719 | `login_required`; `_require_dev_bug_access()` | — |
| POST | `/feedback/<int:topico_id>/corrigir` | `feedback_corrigir` | 739 | `login_required`; `_require_dev_bug_access()` | — |

## app modules financeiro routes

Fonte: [app/modules/financeiro/routes.py](../app/modules/financeiro/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/financeiro` | `financeiro_central` | 120 | `login_required`; `_require_financeiro_access()` | `'financeiro_central.html'` |
| GET | `/financeiro/empresas/<empresa_slug>` | `financeiro_empresa` | 131 | `login_required` | `'financeiro_empresa.html'` |
| GET | `/financeiro/empresas/<empresa_slug>/logo` | `financeiro_empresa_logo` | 139 | `login_required` | — |
| GET | `/financeiro/empresas/<empresa_slug>/configuracoes` | `financeiro_empresa_configuracoes` | 154 | `login_required`; `if not can_manage_financeiro_settings(current_user)`; `can_manage_financeiro_settings()` | `'agro_financeiro_configuracoes.html'` |
| POST | `/financeiro/empresas/<empresa_slug>/configuracoes` | `financeiro_empresa_configuracoes_salvar` | 167 | `login_required`; `if not can_manage_financeiro_settings(current_user)`; `can_manage_financeiro_settings()` | — |
| GET | `/financeiro/empresas/<empresa_slug>/clientes` | `financeiro_empresa_clientes` | 245 | `login_required` | — |
| GET | `/financeiro/empresas/<empresa_slug>/relacionamentos` | `financeiro_empresa_relacionamentos` | 250 | `login_required` | — |
| GET | `/financeiro/empresas/<empresa_slug>/fornecedores` | `financeiro_empresa_fornecedores` | 255 | `login_required` | — |
| GET | `/financeiro/empresas/<empresa_slug>/comercial` | `financeiro_empresa_comercial` | 260 | `login_required`; `if tipo not in {'orcamentos', 'mapeamentos', 'contratos'}` | — |

## app modules mapas routes

Fonte: [app/modules/mapas/routes.py](../app/modules/mapas/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| POST | `/api/geocode` | `api_geocode` | 14 | `login_required` | — |
| GET | `/api/heatmap-data` | `heatmap_data` | 47 | `login_required` | — |
| GET | `/mapa-relatorio` | `mapa_relatorio` | 58 | `login_required` | `'mapa_relatorio.html'` |
| GET | `/consultar_endereco_geolocalizacao` | `consultar_endereco_geolocalizacao` | 73 | `login_required` | `'consultar_endereco_geolocalizacao.html'` |

## app modules painel_operacional routes

Fonte: [app/modules/painel_operacional/routes.py](../app/modules/painel_operacional/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/diretor/painel-operacional` | `painel_operacional` | 12 | `login_required`; `if not can_access_operational_panel(current_user)`; `can_access_operational_panel()` | `'painel_operacional.html'`, `'erro.html'` |
| POST | `/api/painel-operacional/contexto-local` | `api_painel_operacional_contexto` | 28 | `login_required`; `if not can_access_operational_panel(current_user)`; `can_access_operational_panel()` | — |

## app modules piloto_checklists routes

Fonte: [app/modules/piloto_checklists/routes.py](../app/modules/piloto_checklists/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET, POST | `/piloto/checklists/semanais` | `piloto_checklist_semanal` | 24 | `login_required`; `_require_piloto()` | `'piloto_checklist_semanal.html'` |

## app modules piloto_os routes

Fonte: [app/modules/piloto_os/routes.py](../app/modules/piloto_os/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/piloto/os` | `piloto_os` | 1243 | `login_required`; `_require_piloto()` | `'piloto_os.html'` |
| GET | `/piloto/dosagem` | `piloto_dosagem` | 1281 | `login_required`; `_require_piloto()` | `'piloto_dosagem.html'` |
| GET, POST | `/piloto/os/<int:os_id>/dosagem` | `piloto_os_dosagem` | 1287 | `login_required`; `_require_piloto()` | `'piloto_dosagem.html'` |
| GET | `/piloto/os/historico` | `piloto_os_historico` | 1316 | `login_required`; `_require_piloto()` | `'piloto_os_historico.html'` |
| POST | `/piloto/os/<int:os_id>/concluir` | `piloto_concluir_os` | 1332 | `login_required`; `_require_piloto()` | — |
| GET | `/piloto/os/formulario` | `piloto_os_formulario_redirect` | 1345 | `login_required`; `_require_piloto()` | — |
| GET, POST | `/piloto/os/<int:os_id>/formulario` | `piloto_os_formulario_view` | 1357 | `login_required`; `_require_piloto()` | `'piloto_os_formulario.html'` |
| GET | `/os/<int:os_id>/video` | `os_video` | 1412 | `login_required` | — |
| GET | `/os/<int:os_id>/imagem-principal` | `os_imagem_principal` | 1422 | `login_required` | — |
| GET | `/os/<int:os_id>/imagem-complementar/<int:image_index>` | `os_imagem_complementar` | 1432 | `login_required` | — |
| GET | `/piloto/api/drone/<int:drone_id>` | `piloto_api_drone` | 1442 | `login_required`; `_require_piloto()` | — |
| PUT | `/api/os/<int:os_id>/upload-stream` | `os_upload_stream` | 1452 | `login_required`; `_build_upload_context()` | — |
| PUT | `/api/os/<int:os_id>/upload-video-stream` | `os_upload_video_stream` | 1497 | `login_required`; `_build_upload_context()` | — |
| PUT | `/api/os/<int:os_id>/upload-video-background` | `os_upload_video_background` | 1542 | `login_required`; `_build_upload_context()` | — |
| POST | `/api/os/<int:os_id>/upload-video-background/init` | `os_upload_video_background_init` | 1621 | `login_required`; `_build_upload_context()` | — |
| PUT | `/api/video-upload-sessions/<session_id>/chunks/<int:chunk_index>` | `video_upload_session_chunk` | 1688 | `login_required`; `if session.get('user_id') != current_user_id and getattr(current_user, 'tipo_usuario', None) not in ADMIN_PANEL_VIEW_TYPES` | — |
| POST | `/api/video-upload-sessions/<session_id>/complete` | `video_upload_session_complete` | 1747 | `login_required`; `if session.get('user_id') != current_user_id and getattr(current_user, 'tipo_usuario', None) not in ADMIN_PANEL_VIEW_TYPES` | — |
| GET | `/api/video-upload-jobs/<job_id>` | `video_upload_job_status` | 1812 | `login_required`; `if job.get('user_id') != current_user_id and getattr(current_user, 'tipo_usuario', None) not in ADMIN_PANEL_VIEW_TYPES` | — |
| PUT | `/api/os/<int:os_id>/upload-complementary-stream` | `os_upload_complementary_stream` | 1846 | `login_required`; `_build_upload_context()` | — |
| DELETE | `/api/os/<int:os_id>/imagem-principal` | `os_delete_principal_image` | 1900 | `login_required`; `_build_upload_context()` | — |
| DELETE | `/api/os/<int:os_id>/video` | `os_delete_video` | 1936 | `login_required`; `_build_upload_context()` | — |
| DELETE | `/api/os/<int:os_id>/imagem-complementar/<int:image_index>` | `os_delete_complementary_image` | 1970 | `login_required`; `_build_upload_context()` | — |
| GET, POST | `/admin/os/<int:os_id>/formulario` | `admin_os_formulario_view` | 2010 | `login_required`; `_require_admin_os_view()` | `'piloto_os_formulario.html'` |
| GET | `/admin/os/<int:os_id>/export/pdf/v2` | `admin_export_os_pdf_v2` | 2051 | `login_required`; `_require_admin_os_export()`; `_ensure_os_region_access()` | — |
| GET | `/admin/os/<int:os_id>/export/excel/v2` | `admin_export_os_excel_v2` | 2065 | `login_required`; `_require_admin_os_export()`; `_ensure_os_region_access()` | — |

## app modules pilotos routes

Fonte: [app/modules/pilotos/routes.py](../app/modules/pilotos/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET, POST | `/pilotos/cadastrar` | `cadastrar_pilotos` | 41 | `login_required`; `_require_admin_or_operario()` | `'cadastrar_pilotos.html'`, `'cadastrar_pilotos.html'`, `'cadastrar_pilotos.html'` |
| GET | `/pilotos` | `listar_pilotos` | 128 | `login_required`; `if user_tipo not in ('dev', 'diretor', 'admin', 'uvis', 'visualizar', 'regional', 'operario', 'operador', 'prefeitura_admin')`; `if user_tipo in {'uvis', 'regional'}`; `if user_tipo in {'uvis', 'regional'} and (not uvis_regiao)`; `if user_tipo not in ['dev', 'diretor', 'admin', 'visualizar', 'regional']` | `'listar_pilotos.html'`, `'listar_pilotos.html'` |
| GET, POST | `/pilotos/<int:piloto_id>/editar` | `editar_piloto` | 189 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_piloto_or_404()` | `'editar_piloto.html'`, `'editar_piloto.html'`, `'editar_piloto.html'` |
| POST | `/pilotos/<int:piloto_id>/deletar` | `deletar_piloto` | 302 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_piloto_or_404()` | — |

## app modules portal_cidadao routes

Fonte: [app/modules/portal_cidadao/routes.py](../app/modules/portal_cidadao/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/portal-cidadao` | `portal_cidadao` | 19 | — | `'portal_cidadao.html'` |
| GET | `/portal-cidadao/boletim-dengue` | `portal_cidadao_boletim_dengue` | 29 | — | `'portal_cidadao_boletim_dengue.html'` |
| POST | `/portal-cidadao/denuncias` | `portal_cidadao_denuncias_criar` | 56 | — | — |
| GET | `/portal-cidadao/cep/<cep>` | `portal_cidadao_cep` | 78 | — | — |
| POST | `/portal-cidadao/reverse-geocode` | `portal_cidadao_reverse_geocode` | 101 | — | — |

## app modules relatorios routes

Fonte: [app/modules/relatorios/routes.py](../app/modules/relatorios/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/relatorios/solicitacoes` | `relatorios_solicitacoes` | 297 | `login_required`; `if not can_access_relatorios_menu(current_user)`; `can_access_relatorios_menu()` | `'relatorios.html'`, `'erro.html'` |
| GET | `/relatorios` | `relatorios` | 317 | `login_required`; `if not can_access_relatorios_menu(current_user)`; `can_access_relatorios_menu()` | `'relatorios_menu.html'` |
| GET | `/relatorios-os` | `relatorios_os` | 325 | `login_required`; `if not can_access_relatorios_menu(current_user)`; `can_access_relatorios_menu()` | `'relatorios_os.html'`, `'erro.html'` |
| GET | `/relatorios/retornos-automaticos` | `relatorios_retornos_automaticos` | 345 | `login_required`; `if not can_access_relatorios_menu(current_user)`; `can_access_relatorios_menu()` | `'relatorios_retornos_automaticos.html'`, `'erro.html'` |
| GET | `/relatorios/retornos-automaticos/equipe/<int:equipe_id>` | `relatorios_retornos_automaticos_equipe` | 365 | `login_required`; `if not can_access_relatorios_menu(current_user)`; `can_access_relatorios_menu()` | `'relatorios_retornos_automaticos_equipe.html'`, `'erro.html'` |
| GET | `/relatorios/retornos-automaticos/sem-equipe` | `relatorios_retornos_automaticos_sem_equipe` | 397 | `login_required`; `if not can_access_relatorios_menu(current_user)`; `can_access_relatorios_menu()` | `'relatorios_retornos_automaticos_equipe.html'`, `'erro.html'` |
| GET | `/relatorios-coleta-imagens` | `relatorios_coleta_imagens` | 421 | `login_required`; `if not can_access_relatorio_coleta_imagens(current_user)`; `can_access_relatorio_coleta_imagens()` | `'relatorios_coleta_imagens.html'`, `'erro.html'` |
| POST | `/relatorios-coleta-imagens/os/<int:os_id>/ok-uvis` | `relatorios_coleta_imagens_ok_uvis` | 441 | `login_required` | — |
| GET | `/admin/exportar_relatorio_pdf` | `exportar_relatorio_pdf` | 463 | `login_required`; `if not can_access_relatorios_menu(current_user)`; `can_access_relatorios_menu()` | — |
| GET | `/admin/exportar_relatorio_excel` | `exportar_relatorio_excel` | 482 | `login_required`; `if not can_access_relatorios_menu(current_user)`; `can_access_relatorios_menu()` | — |
| GET | `/relatorios-os/export/excel` | `relatorios_os_export_excel` | 497 | `login_required`; `if not can_access_relatorios_menu(current_user)`; `can_access_relatorios_menu()` | — |
| GET | `/relatorios-os/export/pdf` | `relatorios_os_export_pdf` | 512 | `login_required`; `if not can_access_relatorios_menu(current_user)`; `can_access_relatorios_menu()` | — |
| GET | `/relatorios-coleta-imagens/export/pdf` | `relatorios_coleta_imagens_export_pdf` | 531 | `login_required`; `if not can_access_relatorio_coleta_imagens(current_user)`; `can_access_relatorio_coleta_imagens()` | — |
| GET | `/relatorios-coleta-imagens/export/pdf-zip` | `relatorios_coleta_imagens_export_pdf_zip` | 547 | `login_required`; `if not can_access_relatorio_coleta_imagens(current_user)`; `can_access_relatorio_coleta_imagens()` | — |
| GET | `/relatorios-coleta-imagens/export/pdf/jobs/<job_id>` | `relatorios_coleta_imagens_pdf_job_status` | 567 | `login_required`; `if not can_access_relatorio_coleta_imagens(current_user)`; `if not job or int(job.get('user_id') or 0) != int(current_user.id)`; `can_access_relatorio_coleta_imagens()` | — |
| GET | `/relatorios-coleta-imagens/export/pdf/jobs/<job_id>/download` | `relatorios_coleta_imagens_pdf_job_download` | 583 | `login_required`; `if not can_access_relatorio_coleta_imagens(current_user)`; `if not job or int(job.get('user_id') or 0) != int(current_user.id)`; `can_access_relatorio_coleta_imagens()` | — |

## app modules solicitacoes routes

Fonte: [app/modules/solicitacoes/routes.py](../app/modules/solicitacoes/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/api/solicitacao/checar-bloqueio` | `api_solicitacao_checar_bloqueio` | 21 | `login_required` | — |
| GET, POST | `/novo_cadastro` | `novo` | 45 | `login_required`; `if getattr(current_user, 'tipo_usuario', None) not in {'uvis', 'dev', 'diretor', 'admin', 'visualizar', 'prefeitura_admin', 'sup_veiculos', 'sup_veiculo'}` | `'cadastro.html'`, `'cadastro.html'` |
| GET, POST | `/solicitacao/editar/<int:id>` | `editar_solicitacao` | 71 | `login_required` | `'editar_solicitacao.html'` |
| POST | `/admin/deletar/<int:id>` | `deletar_registro` | 97 | `login_required` | — |

## app modules usuarios routes

Fonte: [app/modules/usuarios/routes.py](../app/modules/usuarios/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET, POST | `/admin/prefeituras/nova` | `admin_prefeitura_nova` | 105 | `login_required`; `_admin_only()` | — |
| GET | `/admin/prefeituras` | `admin_prefeituras` | 164 | `login_required`; `_admin_only()` | `'admin_prefeituras.html'` |
| GET, POST | `/admin/prefeituras/<int:id>/editar` | `admin_prefeitura_editar` | 198 | `login_required`; `_admin_only()` | — |
| POST | `/admin/prefeituras/<int:id>/excluir` | `admin_prefeitura_excluir` | 259 | `login_required`; `_admin_only()` | — |
| GET, POST | `/admin/usuarios/novo` | `admin_usuario_novo` | 294 | `login_required`; `if not is_admin_global_user(current_user)`; `if tipo_usuario_form == DEV_USER_TYPE and (not can_assign_dev_role(current_user))`; `if tipo_usuario_form == DIRECTOR_USER_TYPE and (not can_assign_director_role(current_user))`; `if tipo_usuario in VEICULOS_SUPERVISOR_USER_TYPES`; `is_admin_global_user()`; `can_manage_user_work_flags()`; `can_assign_dev_role()`; `can_assign_director_role()` | `'admin_usuario_novo.html'`, `'admin_usuario_novo.html'`, `'admin_usuario_novo.html'`, `'admin_usuario_novo.html'` |
| GET | `/admin/usuarios` | `admin_usuarios_listar` | 429 | `login_required`; `_admin_only()`; `is_dev_user()` | `'admin_usuarios_listar.html'` |
| GET, POST | `/admin/usuarios/<int:id>/editar` | `admin_usuario_editar` | 450 | `login_required`; `if not is_admin_global_user(current_user)`; `if not is_admin_managed_user(usuario)`; `if not can_manage_admin_user(current_user, usuario)`; `if usuario.id == current_user.id`; `if tipo_usuario in VEICULOS_SUPERVISOR_USER_TYPES`; `is_admin_global_user()`; `is_admin_managed_user()`; `can_manage_admin_user()`; `can_manage_user_work_flags()`; `if tipo_usuario_form == DEV_USER_TYPE and (not can_assign_dev_role(current_user))`; `if tipo_usuario_form == DIRECTOR_USER_TYPE and (not can_assign_director_role(current_user))`; `can_assign_dev_role()`; `can_assign_director_role()` | `'admin_usuario_editar.html'`, `'admin_usuario_editar.html'`, `'admin_usuario_editar.html'` |
| POST | `/admin/usuarios/<int:id>/reset_senha` | `admin_usuario_reset_senha` | 607 | `login_required`; `if not is_admin_managed_user(user)`; `if not can_manage_admin_user(current_user, user)`; `_admin_only()`; `is_admin_managed_user()`; `can_manage_admin_user()` | — |
| POST | `/admin/usuarios/<int:id>/excluir` | `admin_usuario_excluir` | 642 | `login_required`; `if not is_admin_managed_user(user)`; `if not can_manage_admin_user(current_user, user)`; `if user.id == current_user.id`; `_admin_only()`; `is_admin_managed_user()`; `can_manage_admin_user()` | — |

## app modules uvis_equipes routes

Fonte: [app/modules/uvis_equipes/routes.py](../app/modules/uvis_equipes/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET, POST | `/uvis/acesso-operacional` | `uvis_acesso_operacional` | 44 | `login_required`; `_uvis_only()` | `'uvis_acesso_operacional.html'`, `'uvis_acesso_operacional.html'` |
| GET | `/uvis/equipes` | `listar_equipes_uvis` | 100 | `login_required`; `_uvis_only()` | `'uvis_equipes_listar.html'` |
| POST | `/uvis/equipes/<string:nome_equipe>/credenciais` | `atualizar_credenciais_equipe_uvis` | 107 | `login_required`; `_uvis_only()` | — |
| GET | `/uvis/equipes/<string:nome_equipe>` | `listar_membros_equipe_uvis` | 144 | `login_required`; `_uvis_only()` | `'uvis_equipe_membros_listar.html'` |
| GET, POST | `/uvis/equipes/<string:nome_equipe>/adicionar` | `adicionar_membro_equipe_uvis` | 162 | `login_required`; `_uvis_only()` | `'uvis_equipe_membro_adicionar.html'`, `'uvis_equipe_membro_adicionar.html'` |
| GET, POST | `/uvis/equipes/nova` | `criar_equipe_uvis` | 217 | `login_required`; `_uvis_only()` | `'uvis_equipe_criar.html'`, `'uvis_equipe_criar.html'`, `'uvis_equipe_criar.html'` |
| GET, POST | `/uvis/equipe-membro/<int:membro_id>/editar` | `editar_membro_equipe_uvis` | 269 | `login_required`; `if membro.uvis_usuario_id != current_user.id`; `_uvis_only()` | `'uvis_equipe_membro_editar.html'`, `'uvis_equipe_membro_editar.html'` |
| POST | `/uvis/equipe-membro/<int:membro_id>/deletar` | `deletar_membro_equipe_uvis` | 309 | `login_required`; `if membro.uvis_usuario_id != current_user.id`; `_uvis_only()` | — |
| POST | `/solicitacao/<int:id>/atribuir-equipe-uvis` | `atribuir_equipe_uvis_solicitacao` | 334 | `login_required`; `if is_veiculos_supervisor(current_user)`; `if solicitacao.usuario_id != current_user.id and (not is_admin_global_user(current_user))`; `if not team_exists_for_user(current_user.id, nome_equipe)`; `is_admin_global_user()` | — |
| GET | `/admin/uvis/equipes` | `admin_listar_equipes_uvis` | 360 | `login_required`; `_admin_or_operario_view_only()` | `'admin_uvis_equipes_listar.html'` |
| POST | `/admin/uvis/<int:uvis_id>/acesso-operacional` | `admin_atualizar_acesso_operacional_uvis` | 372 | `login_required`; `_admin_or_operario_view_only()` | — |
| GET | `/admin/uvis/<int:uvis_id>/equipes/<string:nome_equipe>` | `admin_listar_membros_equipe_uvis` | 417 | `login_required`; `_admin_or_operario_view_only()` | — |

## app modules veiculos routes

Fonte: [app/modules/veiculos/routes.py](../app/modules/veiculos/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/veiculos/rastreamento` | `veiculos_rastreamento` | 126 | `login_required` | `'veiculos_rastreamento.html'` |
| GET | `/veiculos/rastreamento/dados` | `veiculos_rastreamento_dados` | 137 | `login_required` | — |
| GET | `/veiculos/menu` | `veiculos_menu` | 147 | `login_required`; `if tipo not in VEICULOS_ALLOWED_TYPES` | `'veiculos_menu.html'` |
| GET | `/veiculos` | `listar_veiculos` | 161 | `login_required` | `'veiculos_listar.html'` |
| POST | `/veiculos/equipes` | `atualizar_equipes_veiculos` | 174 | `login_required`; `_require_admin_or_operario()` | — |
| GET | `/veiculos/logs` | `veiculos_logs` | 198 | `login_required` | `'veiculos_logs.html'` |
| GET | `/veiculos/limpezas` | `veiculos_limpezas` | 207 | `login_required` | `'veiculos_limpezas.html'` |
| GET | `/veiculos/limpeza/alertas` | `veiculos_alertas_limpeza` | 216 | `login_required` | `'veiculos_alertas_limpeza.html'` |
| GET | `/veiculos/logs/veiculo/<int:veiculo_id>` | `veiculo_logs_detalhe` | 227 | `login_required` | `'veiculo_logs_detalhe.html'` |
| GET | `/veiculos/logs/exportar` | `exportar_logs_veiculos_xlsx` | 239 | `login_required` | — |
| GET | `/admin/veiculos/logs-excluidos` | `veiculos_logs_excluidos` | 248 | `login_required`; `_require_dev()` | `'veiculos_logs_excluidos.html'` |
| POST | `/veiculos/logs/<int:log_id>/corrigir-km` | `corrigir_log_veiculo` | 263 | `login_required`; `_require_admin_or_operario()` | — |
| POST | `/veiculos/logs/<int:log_id>/deletar` | `deletar_log_veiculo` | 309 | `login_required`; `_require_admin()` | — |
| GET | `/veiculos/logs/<int:log_id>/midia/<tipo>` | `veiculo_log_midia_skybox` | 356 | `login_required` | — |
| GET | `/veiculos/abastecimentos/<int:abastecimento_id>/midia/<tipo>` | `veiculo_abastecimento_midia_skybox` | 377 | `login_required` | — |
| GET, POST | `/veiculos/cadastrar` | `cadastrar_veiculo` | 403 | `login_required`; `_require_admin_or_operario()` | `'cadastrar_veiculo.html'`, `'cadastrar_veiculo.html'`, `'cadastrar_veiculo.html'` |
| GET, POST | `/veiculos/<int:veiculo_id>/editar` | `editar_veiculo` | 454 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_veiculo_or_404()` | `'cadastrar_veiculo.html'`, `'cadastrar_veiculo.html'`, `'cadastrar_veiculo.html'` |
| POST | `/veiculos/<int:veiculo_id>/deletar` | `deletar_veiculo` | 509 | `login_required`; `_require_admin_or_operario()`; `_get_scoped_veiculo_or_404()` | — |
| GET | `/piloto/veiculos` | `piloto_veiculos` | 524 | `login_required`; `_require_piloto()` | `'piloto_veiculos.html'` |
| GET | `/piloto/caixa-entrada` | `piloto_caixa_entrada` | 543 | `login_required`; `_require_piloto()` | `'piloto_caixa_entrada.html'` |
| POST | `/piloto/caixa-entrada/limpeza/<int:veiculo_id>/confirmar` | `piloto_confirmar_alerta_limpeza` | 556 | `login_required`; `_require_piloto()` | — |
| POST | `/piloto/veiculos/<int:veiculo_id>/km` | `piloto_atualizar_km_veiculo` | 579 | `login_required`; `_require_piloto()` | — |
| POST | `/piloto/veiculos/<int:veiculo_id>/abastecimento` | `piloto_registrar_abastecimento_turno` | 606 | `login_required`; `_require_piloto()` | — |
| POST | `/piloto/veiculos/<int:veiculo_id>/limpeza` | `piloto_registrar_limpeza_turno` | 637 | `login_required`; `_require_piloto()` | — |
| POST | `/piloto/veiculos/<int:veiculo_id>/encerrar` | `piloto_encerrar_turno` | 666 | `login_required`; `_require_piloto()` | — |

## app modules vigilancia routes

Fonte: [app/modules/vigilancia/routes.py](../app/modules/vigilancia/routes.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET, POST | `/vigilancia/validacao` | `vigilancia_validacao` | 148 | `_preview_access_required`; `_prefeitura_scope()`; `_access_failure()` | — |
| POST | `/api/vigilancia/validacao` | `vigilancia_validacao_api` | 169 | `_preview_access_required`; `_prefeitura_scope()` | — |
| GET | `/vigilancia/modelo.csv` | `vigilancia_modelo_csv` | 182 | `_preview_access_required`; `_prefeitura_scope()`; `_access_failure()` | — |

## app shared session_security

Fonte: [app/shared/session_security.py](../app/shared/session_security.py).

| Método | Caminho | Endpoint local | Linha | Verificações locais | Templates explícitos |
| --- | --- | --- | ---: | --- | --- |
| GET | `/auth/session-status` | `status` | 138 | `if not current_user.is_authenticated` | — |
| POST | `/auth/session-activity` | `activity` | 147 | `if not current_user.is_authenticated` | — |
