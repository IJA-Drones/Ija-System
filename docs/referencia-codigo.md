# Referência do código

Arquivo gerado por `python scripts/build_docs_inventory.py`. Não editar as tabelas manualmente.

O inventário lê apenas o código-fonte com AST. Não importa a aplicação, não lê `.env` e não acessa serviços externos.
As rotas são declarações estáticas: não incluem a rota estática criada pelo Flask nem métodos HEAD/OPTIONS implícitos.
A presença de uma rota não comprova permissão de acesso, funcionamento em produção ou um contrato de API pública.

## Dimensão do código

| Item | Quantidade |
| --- | ---: |
| Módulos em `app/modules` | 36 |
| Arquivos Python em `app` | 156 |
| Declarações de rotas | 358 |
| Modelos com tabela em `app/models.py` | 60 |
| Templates HTML | 168 |
| Arquivos CSS, incluindo bundle | 177 |
| Arquivos JavaScript em `app/static`, incluindo service worker | 8 |
| Revisões Alembic | 125 |
| Arquivos Python de teste | 28 |
| Funções/métodos Python com prefixo `test_` | 330 |
| Arquivos Node de teste | 3 |

A contagem estática de testes não inclui subtestes e não substitui a execução da suíte.

## Módulos

| Módulo | Rotas declaradas | Fontes Python |
| --- | ---: | ---: |
| [admin_checklists](../app/modules/admin_checklists/) | 4 | 3 |
| [admin_dashboard](../app/modules/admin_dashboard/) | 12 | 3 |
| [admin_uvis](../app/modules/admin_uvis/) | 5 | 3 |
| [agenda_notificacoes](../app/modules/agenda_notificacoes/) | 7 | 3 |
| [agro](../app/modules/agro/) | 101 | 9 |
| [anexos](../app/modules/anexos/) | 3 | 3 |
| [auditoria](../app/modules/auditoria/) | 1 | 3 |
| [auth](../app/modules/auth/) | 4 | 3 |
| [backup](../app/modules/backup/) | 3 | 3 |
| [canceladas](../app/modules/canceladas/) | 2 | 3 |
| [cep](../app/modules/cep/) | 2 | 3 |
| [chatbot](../app/modules/chatbot/) | 4 | 3 |
| [clientes](../app/modules/clientes/) | 5 | 3 |
| [dashboard](../app/modules/dashboard/) | 4 | 3 |
| [denuncias](../app/modules/denuncias/) | 10 | 3 |
| [dev_dashboard](../app/modules/dev_dashboard/) | 5 | 3 |
| [dji_flight_logs](../app/modules/dji_flight_logs/) | 9 | 3 |
| [drones_import](../app/modules/drones_import/) | 3 | 3 |
| [equipamentos](../app/modules/equipamentos/) | 21 | 4 |
| [equipe_uvis_dashboard](../app/modules/equipe_uvis_dashboard/) | 4 | 3 |
| [equipes](../app/modules/equipes/) | 5 | 3 |
| [estoque](../app/modules/estoque/) | 5 | 4 |
| [feedback](../app/modules/feedback/) | 16 | 3 |
| [financeiro](../app/modules/financeiro/) | 6 | 3 |
| [mapas](../app/modules/mapas/) | 4 | 3 |
| [painel_operacional](../app/modules/painel_operacional/) | 2 | 3 |
| [piloto_checklists](../app/modules/piloto_checklists/) | 1 | 3 |
| [piloto_os](../app/modules/piloto_os/) | 25 | 5 |
| [pilotos](../app/modules/pilotos/) | 4 | 3 |
| [portal_cidadao](../app/modules/portal_cidadao/) | 5 | 5 |
| [relatorios](../app/modules/relatorios/) | 16 | 4 |
| [solicitacoes](../app/modules/solicitacoes/) | 4 | 3 |
| [usuarios](../app/modules/usuarios/) | 9 | 3 |
| [uvis_equipes](../app/modules/uvis_equipes/) | 12 | 3 |
| [veiculos](../app/modules/veiculos/) | 25 | 4 |
| [vigilancia](../app/modules/vigilancia/) | 3 | 5 |

## Modelos e vínculos

Os campos abaixo são declarações diretas da classe. Tipos, defaults, índices, relacionamentos ORM e campos herdados devem ser consultados em [models.py](../app/models.py).

| Modelo | Tabela | Campos declarados | Chaves estrangeiras declaradas |
| --- | --- | --- | --- |
| `Prefeitura` | `prefeituras` | `id`, `nome`, `slug`, `ativa`, `criada_em` | — |
| `Usuario` | `usuarios` | `id`, `prefeitura_id`, `nome_uvis`, `regiao`, `codigo_setor`, `login`, `senha_hash`, `tipo_usuario`, `trabalha_oceano_azul`, `trabalha_agro`, `suporte_operacional`, `suporte_tecnico`, `piloto_id`, `piloto_agro_id`, `equipe_uvis_uvis_usuario_id`, `equipe_uvis_nome` | `prefeitura_id → prefeituras.id`; `piloto_id → pilotos.id`; `piloto_agro_id → pilotos_agro.id`; `equipe_uvis_uvis_usuario_id → usuarios.id` |
| `FeedbackTopico` | `feedback_topicos` | `id`, `prefeitura_id`, `uvis_usuario_id`, `uvis_nome`, `regiao`, `criado_por_id`, `criado_por_nome`, `criado_por_tipo`, `titulo`, `descricao`, `categoria`, `setor_suporte`, `status`, `prioridade`, `responsavel_id`, `resolvido_em`, `criado_em`, `atualizado_em` | `prefeitura_id → prefeituras.id`; `uvis_usuario_id → usuarios.id`; `criado_por_id → usuarios.id`; `responsavel_id → usuarios.id` |
| `FeedbackComentario` | `feedback_comentarios` | `id`, `topico_id`, `usuario_id`, `usuario_nome`, `usuario_tipo`, `mensagem`, `interno`, `criado_em` | `topico_id → feedback_topicos.id`; `usuario_id → usuarios.id` |
| `FeedbackComentarioAnexo` | `feedback_comentario_anexos` | `id`, `comentario_id`, `arquivo_path`, `arquivo_nome`, `mime_type`, `tamanho_bytes`, `criado_em` | `comentario_id → feedback_comentarios.id` |
| `AuditoriaUsuario` | `auditoria_usuarios` | `id`, `usuario_id`, `usuario_nome`, `usuario_login`, `tipo_usuario`, `metodo`, `tipo_evento`, `endpoint`, `path`, `query_string`, `status_code`, `ip`, `user_agent`, `referrer`, `criado_em` | — |
| `WatchdogDeployEvent` | `watchdog_deploy_events` | `id`, `event_id`, `status`, `source`, `health_url`, `failures`, `attempts`, `started_at`, `recovered_at`, `criado_em` | — |
| `UsuarioPresenca` | `usuario_presencas` | `id`, `usuario_id`, `primeiro_acesso_em`, `ultimo_acesso_em`, `login_em`, `logout_em`, `ultimo_metodo`, `ultimo_endpoint`, `ultimo_path`, `ultimo_query_string`, `ip`, `user_agent`, `referrer` | `usuario_id → usuarios.id` |
| `EquipeUvis` | `equipe_uvis` | `id`, `uvis_usuario_id`, `nome_equipe`, `ordem`, `nome`, `funcao`, `contato`, `criado_em` | `uvis_usuario_id → usuarios.id` |
| `Pilotos` | `pilotos` | `id`, `prefeitura_id`, `nome_piloto`, `regiao`, `regiao_alternativa`, `telefone` | `prefeitura_id → prefeituras.id` |
| `PilotoUvis` | `piloto_uvis` | `id`, `piloto_id`, `uvis_usuario_id`, `criado_em` | `piloto_id → pilotos.id`; `uvis_usuario_id → usuarios.id` |
| `Solicitacao` | `solicitacoes` | `id`, `prefeitura_id`, `data_agendamento`, `hora_agendamento`, `foco`, `tipo_operacao`, `tipo_visita`, `tipo_imovel`, `altura_voo`, `distrito_administrativo`, `criadouro`, `apoio_cet`, `observacao`, `area_restrita`, `cep`, `logradouro`, `bairro`, `cidade`, `uf`, `numero`, `complemento`, `latitude`, `longitude`, `place_id`, `perimetro_planejado`, `perimetro_executado`, `endereco_bloqueado`, `anexo_path`, `anexo_nome`, `protocolo`, `justificativa`, `equipe_uvis_nome`, `quadra_confirmada_admin`, `quadra_visualizada_admin`, `quadra_visualizada_admin_em`, `data_criacao`, `status`, `usuario_id`, `piloto_id`, `equipe_id`, `origem_retorno_id`, `gerada_automaticamente` | `prefeitura_id → prefeituras.id`; `usuario_id → usuarios.id`; `piloto_id → pilotos.id`; `equipe_id → equipes.id`; `origem_retorno_id → solicitacoes.id` |
| `Denuncia` | `denuncias` | `id`, `protocolo`, `status`, `tipo_visita`, `tipo_imovel`, `foco`, `descricao`, `cep`, `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `uf`, `latitude`, `longitude`, `place_id`, `cidadao_nome`, `cidadao_cpf`, `cidadao_rg`, `cidadao_telefone`, `prefeitura_id`, `coordenadoria`, `uvis_usuario_id`, `solicitacao_id`, `triado_por_id`, `encaminhado_em`, `arquivado_em`, `arquivado_motivo`, `ip_origem`, `user_agent`, `consentimento`, `criado_em`, `atualizado_em` | `prefeitura_id → prefeituras.id`; `uvis_usuario_id → usuarios.id`; `solicitacao_id → solicitacoes.id`; `triado_por_id → usuarios.id` |
| `DenunciaAnexo` | `denuncia_anexos` | `id`, `denuncia_id`, `arquivo_path`, `arquivo_nome`, `mime_type`, `tamanho_bytes`, `tipo_midia`, `criado_em` | `denuncia_id → denuncias.id` |
| `OrdemServico` | `ordens_servico` | `id`, `solicitacao_id`, `equipe_id`, `identificador_os`, `respondido_por`, `respondido_em`, `situacao_aplicacao`, `larva_visualizada`, `retornar_proxima_semana_monitorar_larvas`, `distrito_administrativo`, `nome_rf_ace_responsavel_os`, `criadouro_os_tipo_volume`, `data_aplicacao`, `hora_inicio_aplicacao`, `hora_termino_aplicacao`, `tratamento_adicional_realizado`, `quantos_quais`, `descricao_produto`, `formulacao_produto`, `dosagem_g_10l`, `calculo_dosagem_planejado`, `calculo_dosagem_planejado_em`, `tipo_aplicacao`, `quantidade_produto_administrada_ml`, `pulverizacao_area_l_ha`, `prefixo_aeronave_pulverizacao`, `prefixo_aeronave_monitoramento`, `quantidade_videos_registradas`, `quantidade_imagens_registradas`, `imagem_principal`, `outras_imagens`, `video`, `uvis_visualizado`, `uvis_visualizado_em`, `uvis_visualizado_por_id`, `ponta_pulverizacao`, `temperatura_c`, `umidade_relativa_pct`, `velocidade_vento_kmh`, `motivo_nao_realizacao`, `observacoes`, `piloto`, `assinatura_piloto`, `auxiliar`, `proprietario_ou_preposto`, `assinatura_proprietario_ou_preposto`, `drone_id`, `drone_monitoramento_id`, `dji_kml_route_id`, `drone_denominacao`, `drone_modelo`, `drone_numero_serie`, `drone_registro_anatel`, `drone_registro_anac`, `drone_monitoramento_denominacao`, `drone_monitoramento_modelo`, `drone_monitoramento_numero_serie`, `drone_monitoramento_registro_anatel`, `drone_monitoramento_registro_anac` | `solicitacao_id → solicitacoes.id`; `equipe_id → equipes.id`; `uvis_visualizado_por_id → usuarios.id`; `drone_id → drones.id`; `drone_monitoramento_id → drones.id`; `dji_kml_route_id → dji_flight_kml_routes.id` |
| `OrdemServicoEquipeUvis` | `ordens_servico_equipe_uvis` | `id`, `solicitacao_id`, `equipe_uvis_nome`, `equipe_id`, `identificador_os`, `respondido_por`, `respondido_em`, `status`, `situacao_aplicacao`, `tratamento_adicional_realizado`, `quantos_quais`, `quantidade_produto_administrada_ml`, `motivo_nao_realizacao`, `larva_visualizada`, `retornar_proxima_semana_monitorar_larvas`, `retorno_monitoramento_em`, `observacoes`, `criado_em`, `atualizado_em` | `solicitacao_id → solicitacoes.id`; `equipe_id → equipes.id` |
| `Notificacao` | `notificacoes` | `id`, `usuario_id`, `titulo`, `mensagem`, `link`, `criada_em`, `lida_em`, `apagada_em` | `usuario_id → usuarios.id` |
| `Clientes` | `clientes` | `id`, `prefeitura_id`, `nome_cliente`, `documento`, `contato`, `telefone`, `email`, `endereco` | `prefeitura_id → prefeituras.id` |
| `ClienteAgro` | `clientes_agro` | `id`, `prefeitura_id`, `documento`, `nome`, `cep`, `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `uf`, `criado_em` | `prefeitura_id → prefeituras.id` |
| `FornecedorAgro` | `fornecedores_agro` | `id`, `prefeitura_id`, `documento`, `nome`, `cep`, `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `uf`, `criado_em` | `prefeitura_id → prefeituras.id` |
| `OrcamentoAgro` | `orcamentos_agro` | `id`, `prefeitura_id`, `cliente_agro_id`, `cliente_nome`, `cliente_documento`, `nome_fazenda`, `mapeamento`, `risco_operacional`, `cultura`, `cultura_alternativa`, `servico`, `area_ha`, `elaborado_por_nome`, `preco_base`, `preco_mapeamento`, `preco_pulverizacao`, `preco_pulverizacao_adicional`, `drone_agro_id`, `drone_mapeamento_agro_id`, `drone_tipo`, `drone_identificacao`, `drone_modelo`, `drone_funcao_operacional`, `drone_registro_anatel`, `drone_registro_anac`, `drone_capacidade_tanque_l`, `drone_mapeamento_identificacao`, `drone_mapeamento_modelo`, `drone_mapeamento_funcao_operacional`, `drone_mapeamento_registro_anatel`, `drone_mapeamento_registro_anac`, `possui_produto_aplicado`, `produto_aplicado_receituario`, `inicio_aplicacao_prevista`, `fim_aplicacao_prevista`, `cep`, `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `uf`, `anexo_path`, `anexo_nome`, `protocolo`, `data_criacao` | `prefeitura_id → prefeituras.id`; `cliente_agro_id → clientes_agro.id`; `drone_agro_id → equipamentos_agro.id`; `drone_mapeamento_agro_id → equipamentos_agro.id` |
| `ContratoAgro` | `contratos_agro` | `id`, `prefeitura_id`, `orcamento_agro_id`, `equipe_agro_id`, `status`, `contratante_nome`, `contratante_documento`, `contratante_rg`, `contratante_cep`, `contratante_logradouro`, `contratante_numero`, `contratante_complemento`, `contratante_bairro`, `contratante_cidade`, `contratante_uf`, `propriedade_nome`, `propriedade_cep`, `propriedade_logradouro`, `propriedade_numero`, `propriedade_complemento`, `propriedade_bairro`, `propriedade_cidade`, `propriedade_uf`, `descricao_servico`, `cultura`, `cultura_alternativa`, `area_contratada`, `valor_total`, `valor_mapeamento_ha`, `valor_pulverizacao_ha`, `valor_pulverizacao_adicional_ha`, `prazo_inicio_dias`, `prazo_pagamento_dias`, `cidade_assinatura`, `foro_cidade`, `data_assinatura`, `observacoes_adicionais`, `comprovante_pagamento_path`, `comprovante_pagamento_nome`, `comprovante_pagamento_enviado_em`, `criado_em`, `atualizado_em` | `prefeitura_id → prefeituras.id`; `orcamento_agro_id → orcamentos_agro.id`; `equipe_agro_id → equipes_agro.id` |
| `RdMapeamentoAgro` | `rds_mapeamento_agro` | `id`, `prefeitura_id`, `orcamento_agro_id`, `equipe_agro_id`, `piloto_agro_id`, `status`, `cliente_nome`, `numero_os`, `propriedade_nome`, `municipio`, `uf`, `proprietario_ou_preposto`, `tipo_servico`, `cultura`, `equipamento`, `altura_voo_m`, `area_ha`, `sobreposicao_frontal_pct`, `sobreposicao_lateral_pct`, `gsd`, `outros`, `data_relatorio`, `rede_energia_baixa`, `rede_energia_alta_media`, `poste`, `poste_com_tirante`, `acesso_area`, `arvores_secas`, `outros_area`, `observacoes`, `responsavel_nome`, `enviado_em`, `preenchido_em`, `criado_em`, `atualizado_em` | `prefeitura_id → prefeituras.id`; `orcamento_agro_id → orcamentos_agro.id`; `equipe_agro_id → equipes_agro.id`; `piloto_agro_id → pilotos_agro.id` |
| `OrdemServicoAgro` | `ordens_servico_agro` | `id`, `prefeitura_id`, `contrato_agro_id`, `orcamento_agro_id`, `equipe_agro_id`, `piloto_agro_id`, `drone_pulverizacao_id`, `drone_mapeamento_id`, `identificador_os`, `status`, `data_aplicacao`, `periodo_aplicacao`, `cliente_nome`, `propriedade_nome`, `cultura`, `servico`, `protocolo`, `cidade_operacao`, `uf_operacao`, `drone_pulverizacao_identificacao`, `drone_pulverizacao_modelo`, `drone_pulverizacao_tipo`, `drone_pulverizacao_registro_anatel`, `drone_pulverizacao_registro_anac`, `drone_mapeamento_identificacao`, `drone_mapeamento_modelo`, `drone_mapeamento_tipo`, `drone_mapeamento_registro_anatel`, `drone_mapeamento_registro_anac`, `altura_voo_m`, `largura_faixa_m`, `ponta_pulverizacao`, `mapeamento_descricao`, `temperatura_min_c`, `temperatura_max_c`, `umidade_min_pct`, `umidade_max_pct`, `vento_min_kmh`, `vento_max_kmh`, `area_total_ha`, `total_calda_l`, `media_aplicada_l_ha`, `taxa_aplicacao_l_ha`, `tipo_aplicacao`, `produto_aplicado`, `formulacao_produto`, `dosagem`, `classe_toxica`, `relatorio_pdf_path`, `relatorio_pdf_nome`, `mapa_aplicacao_path`, `mapa_aplicacao_nome`, `agro_kml_route_id`, `observacoes`, `criado_em`, `atualizado_em`, `finalizado_em` | `prefeitura_id → prefeituras.id`; `contrato_agro_id → contratos_agro.id`; `orcamento_agro_id → orcamentos_agro.id`; `equipe_agro_id → equipes_agro.id`; `piloto_agro_id → pilotos_agro.id`; `drone_pulverizacao_id → equipamentos_agro.id`; `drone_mapeamento_id → equipamentos_agro.id`; `agro_kml_route_id → agro_flight_kml_routes.id` |
| `FinanceiroAgro` | `financeiro_agro` | `id`, `prefeitura_id`, `cliente_agro_id`, `orcamento_agro_id`, `contrato_agro_id`, `ordem_servico_agro_id`, `banco_agro_id`, `cliente_nome`, `cultura`, `forma_recebimento`, `status`, `observacoes`, `competencia_mes`, `competencia_ano`, `data_elaboracao_contrato`, `data_servico_executado`, `data_vencimento`, `data_recebimento`, `area_mapeamento_ha`, `valor_mapeamento_ha`, `total_mapeamento`, `area_pulverizacao_ha`, `area_pulverizada_real_ha`, `valor_pulverizacao_ha`, `total_pulverizacao`, `valor_total_contrato`, `valor_recebido`, `comissao_por_ha`, `valor_comissao`, `comissao_cooperativa_por_ha`, `valor_comissao_cooperativa`, `criado_em`, `atualizado_em` | `prefeitura_id → prefeituras.id`; `cliente_agro_id → clientes_agro.id`; `orcamento_agro_id → orcamentos_agro.id`; `contrato_agro_id → contratos_agro.id`; `ordem_servico_agro_id → ordens_servico_agro.id`; `banco_agro_id → banco_agro.id` |
| `BancoAgro` | `banco_agro` | `id`, `prefeitura_id`, `nome`, `banco_nome`, `agencia`, `conta`, `tipo_conta`, `saldo_inicial`, `saldo_previsto`, `saldo_atual`, `ativo`, `observacoes`, `criado_em`, `atualizado_em` | `prefeitura_id → prefeituras.id` |
| `FinanceiroAgroCategoria` | `financeiro_agro_categorias` | `id`, `prefeitura_id`, `tipo_movimento`, `nome`, `ativo`, `criado_em`, `atualizado_em` | `prefeitura_id → prefeituras.id` |
| `FinanceiroAgroSubcategoria` | `financeiro_agro_subcategorias` | `id`, `categoria_id`, `nome`, `ativo`, `criado_em`, `atualizado_em` | `categoria_id → financeiro_agro_categorias.id` |
| `FinanceiroAgroSaida` | `financeiro_agro_saidas` | `id`, `prefeitura_id`, `cliente_agro_id`, `fornecedor_agro_id`, `banco_agro_id`, `tipo_saida`, `categoria`, `subcategoria`, `descricao`, `documento_referencia`, `detalhamento_imposto`, `favorecido`, `cep`, `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `uf`, `forma_pagamento`, `status`, `observacoes`, `competencia_mes`, `competencia_ano`, `data_lancamento`, `data_emissao`, `data_vencimento`, `data_pagamento`, `grupo_lancamento`, `parcela_numero`, `parcela_total`, `valor`, `criado_em`, `atualizado_em` | `prefeitura_id → prefeituras.id`; `cliente_agro_id → clientes_agro.id`; `fornecedor_agro_id → fornecedores_agro.id`; `banco_agro_id → banco_agro.id` |
| `FinanceiroAgroEntrada` | `financeiro_agro_entradas` | `id`, `prefeitura_id`, `cliente_agro_id`, `banco_agro_id`, `categoria`, `subcategoria`, `descricao`, `documento_referencia`, `cliente_nome`, `cep`, `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `uf`, `forma_recebimento`, `status`, `observacoes`, `competencia_mes`, `competencia_ano`, `data_lancamento`, `data_emissao`, `data_vencimento`, `data_recebimento`, `grupo_lancamento`, `parcela_numero`, `parcela_total`, `valor`, `criado_em`, `atualizado_em` | `prefeitura_id → prefeituras.id`; `cliente_agro_id → clientes_agro.id`; `banco_agro_id → banco_agro.id` |
| `FinanceiroAgroCaixaDiario` | `financeiro_agro_caixa_diario` | `id`, `prefeitura_id`, `data_caixa`, `status`, `saldo_anterior`, `saldo_abertura`, `total_entradas`, `total_saidas`, `saldo_fechamento`, `aberto_por_nome`, `fechado_por_nome`, `observacoes_abertura`, `observacoes_fechamento`, `aberto_em`, `fechado_em`, `criado_em`, `atualizado_em` | `prefeitura_id → prefeituras.id` |
| `FinanceiroAgroCompetenciaControle` | `financeiro_agro_competencia_controle` | `id`, `competencia_ano`, `competencia_mes`, `liberado`, `atualizado_por_nome`, `criado_em`, `atualizado_em` | — |
| `EquipeAgro` | `equipes_agro` | `id`, `prefeitura_id`, `nome`, `descricao`, `ativa`, `criado_em` | `prefeitura_id → prefeituras.id` |
| `PilotoAgro` | `pilotos_agro` | `id`, `prefeitura_id`, `equipe_agro_id`, `nome`, `telefone`, `ativo`, `criado_em` | `prefeitura_id → prefeituras.id`; `equipe_agro_id → equipes_agro.id` |
| `CurriculoAgro` | `curriculos_agro` | `id`, `prefeitura_id`, `criado_por_usuario_id`, `nome`, `email`, `telefone`, `cidade`, `uf`, `linkedin`, `titulo_profissional`, `area_principal`, `resumo_perfil`, `objetivo_profissional`, `habilidades_tecnicas`, `habilidades_comportamentais`, `areas_atuacao`, `areas_desenvolvimento`, `experiencias`, `formacoes`, `certificacoes`, `idiomas`, `status`, `observacoes`, `analise_status`, `analise_erro`, `gemini_modelo`, `analisado_em`, `arquivo_nome_original`, `arquivo_mime_type`, `arquivo_tamanho`, `arquivo_sha256`, `dropbox_path`, `dropbox_rev`, `criado_em`, `atualizado_em` | `prefeitura_id → prefeituras.id`; `criado_por_usuario_id → usuarios.id` |
| `EquipamentoAgro` | `equipamentos_agro` | `id`, `prefeitura_id`, `equipe_agro_id`, `tipo`, `modelo`, `identificacao`, `numero_serie`, `status`, `funcao_operacional`, `registro_anatel`, `registro_anac`, `capacidade_tanque_l`, `largura_faixa_m`, `altura_voo_padrao_m`, `ponta_pulverizacao`, `criado_em` | `prefeitura_id → prefeituras.id`; `equipe_agro_id → equipes_agro.id` |
| `Equipe` | `equipes` | `id`, `prefeitura_id`, `nome_equipe`, `descricao`, `regiao`, `ativa`, `trabalha_oceano_azul`, `criada_em` | `prefeitura_id → prefeituras.id` |
| `EquipePiloto` | `equipe_pilotos` | `id`, `equipe_id`, `piloto_id`, `papel`, `criado_em` | `equipe_id → equipes.id`; `piloto_id → pilotos.id` |
| `Equipamentos` | `equipamentos` | `id`, `tipo_equipamento`, `status`, `modelo`, `renomacao`, `categoria`, `ano_fabricacao`, `numero_serie`, `ultima_manutencao`, `criado_em`, `equipe_id`, `prefeitura_id` | `equipe_id → equipes.id`; `prefeitura_id → prefeituras.id` |
| `Drones` | `drones` | `id`, `registro_anatel`, `registro_anac`, `pmd_kg` | `id → equipamentos.id` |
| `EstoquePeca` | `estoque_pecas` | `id`, `prefeitura_id`, `drone_id`, `numero_serie`, `modelo_peca`, `quantidade`, `status`, `observacoes`, `criado_em`, `atualizado_em` | `prefeitura_id → prefeituras.id`; `drone_id → drones.id` |
| `ManutencaoPecaUso` | `manutencao_pecas_usadas` | `id`, `prefeitura_id`, `manutencao_id`, `drone_id`, `peca_id`, `usuario_id`, `quantidade_usada`, `observacoes`, `criado_em` | `prefeitura_id → prefeituras.id`; `manutencao_id → manutencoes_equipamentos.id`; `drone_id → drones.id`; `peca_id → estoque_pecas.id`; `usuario_id → usuarios.id` |
| `ManutencaoEquipamento` | `manutencoes_equipamentos` | `id`, `prefeitura_id`, `drone_id`, `aberta_por_id`, `encerrada_por_id`, `status`, `aberta_em`, `encerrada_em`, `observacoes` | `prefeitura_id → prefeituras.id`; `drone_id → drones.id`; `aberta_por_id → usuarios.id`; `encerrada_por_id → usuarios.id` |
| `Baterias` | `baterias` | `id`, `ciclo`, `drone_id` | `id → equipamentos.id`; `drone_id → drones.id` |
| `Veiculos` | `veiculos` | `id`, `frota`, `operacao`, `placa`, `responsavel`, `km_atual`, `km_prox_revisao`, `revisao_marcada_em`, `revisao_obs` | `id → equipamentos.id` |
| `RastreamentoPosicao` | `rastreamento_posicoes` | `id`, `veiculo_id`, `prefeitura_id`, `latitude`, `longitude`, `velocidade_kmh`, `ignicao`, `hodometro_km`, `endereco`, `reportado_em`, `provedor`, `is_demo`, `chave_fixture` | `veiculo_id → veiculos.id`; `prefeitura_id → prefeituras.id` |
| `RastreamentoHistorico` | `rastreamento_historicos` | `id`, `veiculo_id`, `prefeitura_id`, `latitude`, `longitude`, `velocidade_kmh`, `ignicao`, `hodometro_km`, `reportado_em`, `provedor`, `is_demo`, `chave_fixture` | `veiculo_id → veiculos.id`; `prefeitura_id → prefeituras.id` |
| `RastreamentoAlerta` | `rastreamento_alertas` | `id`, `veiculo_id`, `prefeitura_id`, `tipo`, `severidade`, `mensagem`, `reportado_em`, `resolvido`, `provedor`, `is_demo`, `chave_fixture` | `veiculo_id → veiculos.id`; `prefeitura_id → prefeituras.id` |
| `LogVeiculo` | `logs_veiculo` | `id`, `veiculo_id`, `piloto_id`, `equipe_id`, `data_registro`, `km_inicial`, `km_final`, `check_diario`, `qtd_fazendas_enderecos`, `foto_painel_path`, `foto_painel_final_path`, `assinatura_piloto`, `observacao` | `veiculo_id → veiculos.id`; `piloto_id → pilotos.id`; `equipe_id → equipes.id` |
| `Abastecimento` | `abastecimentos` | `id`, `log_veiculo_id`, `data_hora`, `km_registro`, `tipo_abastecimento`, `litros`, `valor_total`, `foto_nf_path`, `foto_painel_path` | `log_veiculo_id → logs_veiculo.id` |
| `LimpezaVeiculo` | `limpezas_veiculo` | `id`, `log_veiculo_id`, `veiculo_id`, `piloto_id`, `equipe_id`, `data_registro`, `data_hora`, `limpeza_realizada`, `tipo_limpeza`, `valor_total`, `observacao` | `log_veiculo_id → logs_veiculo.id`; `veiculo_id → veiculos.id`; `piloto_id → pilotos.id`; `equipe_id → equipes.id` |
| `LimpezaVeiculoAlertaCiencia` | `limpezas_veiculo_alertas_ciencia` | `id`, `veiculo_id`, `usuario_id`, `piloto_id`, `equipe_id`, `referencia_limpeza_em`, `prazo_dias`, `reconhecido_em`, `criado_em`, `atualizado_em` | `veiculo_id → veiculos.id`; `usuario_id → usuarios.id`; `piloto_id → pilotos.id`; `equipe_id → equipes.id` |
| `ChecklistSemanalVeiculo` | `checklists_semanais_veiculo` | `id`, `veiculo_id`, `piloto_id`, `equipe_id`, `data_registro`, `km_leitura`, `farois_funcionando`, `setas_funcionando`, `lanternas_funcionando`, `piscaalerta_funcionando`, `condicao_luzes_direcao`, `luz_painel`, `condicao_luz_painel`, `limpador_parabrisa`, `agua_radiador`, `fluido_freio`, `oleo_motor`, `condicao_itens_manutencao`, `embreagem`, `freio_mao`, `freio_pe`, `condicao_embreagem_freios`, `vidros`, `retrovisores`, `condicao_vidros_retrovisores`, `pneus`, `estepe`, `macaco`, `triangulo`, `chave_roda`, `condicao_pneus_estepe`, `extintor`, `cinto_seguranca`, `condicao_itens_seguranca`, `alarme`, `ar_condicionado`, `radio`, `condicao_itens_carro_interno`, `giroflex`, `isqueiro`, `carregador`, `condicao_giroflex_isqueiro_carregador`, `lataria_frontal`, `lataria_lateral`, `lataria_traseira`, `condicao_lataria`, `lataria_porta_frontal`, `lataria_porta_traseira`, `lataria_porta_lateral`, `condicao_lataria_portas`, `parachoque_frontal`, `parachoque_traseiro`, `condicao_itens_carro_externo`, `assinatura_piloto` | `veiculo_id → veiculos.id`; `piloto_id → pilotos.id`; `equipe_id → equipes.id` |
| `ChecklistSemanalDrone` | `checklists_semanais_drone` | `id`, `drone_id`, `piloto_id`, `equipe_id`, `data_registro`, `helices_status`, `condicao_helices`, `tanque`, `trem_pouso`, `cameras`, `condicao_estrutura`, `carregador_controle`, `baterias`, `condicao_carregador_bateria`, `cabos_carregador`, `correia_pescoco`, `condicao_cabos_correia`, `num_baterias`, `num_baterias_wb`, `observacoes_equipamento`, `assinatura_piloto`, `nome_responsavel`, `assinatura_piloto_responsavel` | `drone_id → drones.id`; `piloto_id → pilotos.id`; `equipe_id → equipes.id` |
| `DjiFlightLogImport` | `dji_flight_log_imports` | `id`, `uploaded_by_id`, `original_filename`, `stored_filename`, `stored_path`, `file_sha256`, `total_rows`, `imported_rows`, `skipped_rows`, `period_start`, `period_end`, `uploaded_at` | `uploaded_by_id → usuarios.id` |
| `DjiFlightRecord` | `dji_flight_records` | `id`, `import_id`, `source_row_number`, `fingerprint`, `flight_window`, `flight_start`, `flight_end`, `location`, `place_id`, `aircraft_name`, `task_type`, `sprayed_area_ha`, `total_amount_l_kg`, `flight_duration_seconds`, `flight_duration_label`, `crop`, `pilot_name`, `team_name`, `field_name`, `serial_number`, `starting_battery_level`, `ending_battery_level`, `battery_consumed_level`, `battery_sn`, `raw_payload`, `imported_at` | `import_id → dji_flight_log_imports.id` |
| `DjiFlightKmlRoute` | `dji_flight_kml_routes` | `id`, `flight_record_id`, `uploaded_by_id`, `route_code`, `original_filename`, `stored_filename`, `stored_path`, `file_sha256`, `aircraft_name`, `pilot_name`, `flight_controller_id`, `route_timestamp`, `place_id`, `mode_selection`, `flight_time_raw`, `task_area`, `spray_amount`, `route_color`, `route_width`, `point_count`, `points_json`, `imported_at` | `flight_record_id → dji_flight_records.id`; `uploaded_by_id → usuarios.id` |
| `AgroFlightLogImport` | `agro_flight_log_imports` | `id`, `uploaded_by_id`, `original_filename`, `stored_filename`, `stored_path`, `file_sha256`, `total_rows`, `imported_rows`, `skipped_rows`, `period_start`, `period_end`, `uploaded_at` | `uploaded_by_id → usuarios.id` |
| `AgroFlightRecord` | `agro_flight_records` | `id`, `import_id`, `source_row_number`, `fingerprint`, `flight_window`, `flight_start`, `flight_end`, `location`, `aircraft_name`, `task_type`, `sprayed_area_ha`, `total_amount_l_kg`, `flight_duration_seconds`, `flight_duration_label`, `crop`, `pilot_name`, `team_name`, `field_name`, `serial_number`, `starting_battery_level`, `ending_battery_level`, `battery_consumed_level`, `battery_sn`, `raw_payload`, `imported_at` | `import_id → agro_flight_log_imports.id` |
| `AgroFlightKmlRoute` | `agro_flight_kml_routes` | `id`, `flight_record_id`, `uploaded_by_id`, `route_code`, `original_filename`, `stored_filename`, `stored_path`, `file_sha256`, `aircraft_name`, `pilot_name`, `flight_controller_id`, `route_timestamp`, `mode_selection`, `flight_time_raw`, `task_area`, `spray_amount`, `route_color`, `route_width`, `point_count`, `points_json`, `imported_at` | `flight_record_id → agro_flight_records.id`; `uploaded_by_id → usuarios.id` |

## Migrações

Heads: `e15caed9908f`.

Bases: `1600d07df8f3`, `68a65e96dbfc`, `796a8641f68a`.

Um head único verifica a estrutura do grafo; não comprova instalação em banco vazio nem atualização de uma base existente. Veja o [guia de operação](operacao.md).

## Rotas por arquivo

O endpoint mostrado é o nome local declarado. Em geral recebe o prefixo `main.`; autenticação usa `auth.` e sessão usa `session_security.`. Health checks são registrados diretamente na aplicação.

### app/__init__.py

Fonte: [app/__init__.py](../app/__init__.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/healthz` | `healthz` | 181 |
| GET | `/healthz/full` | `healthz_full` | 185 |

### app/core/routes.py

Fonte: [app/core/routes.py](../app/core/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/sw.js` | `serve_sw` | 13 |
| GET | `/forcar_erro` | `forcar_erro` | 17 |
| GET | `/__test/erro/<int:code>` | `test_error_code` | 24 |

### app/modules/admin_checklists/routes.py

Fonte: [app/modules/admin_checklists/routes.py](../app/modules/admin_checklists/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/admin/checklists/semanais` | `admin_checklists_semanais` | 21 |
| GET | `/admin/checklists/semanais/<int:piloto_id>/<string:semana_inicio>` | `admin_checklist_semanal_detalhe` | 49 |
| GET | `/admin/checklists/semanais/<string:actor_type>/<int:actor_id>/<string:semana_inicio>` | `admin_checklist_semanal_detalhe_actor` | 58 |
| GET, POST | `/admin/checklists/<string:tipo>/<int:checklist_id>/editar` | `editar_checklist_semanal` | 67 |

### app/modules/admin_dashboard/routes.py

Fonte: [app/modules/admin_dashboard/routes.py](../app/modules/admin_dashboard/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/admin` | `admin_dashboard` | 260 |
| GET | `/admin/exportar_excel` | `exportar_excel` | 345 |
| POST | `/admin/atualizar/<int:id>` | `atualizar` | 398 |
| POST | `/admin/solicitacao/<int:id>/cancelar` | `cancelar_solicitacao_admin` | 443 |
| GET | `/admin/canceladas` | `admin_canceladas` | 461 |
| GET | `/admin/historico-os` | `admin_historico_os` | 512 |
| GET | `/admin/historico-os/exportar-excel` | `admin_historico_os_exportar_excel` | 560 |
| GET | `/admin/historico-os/exportar-excel-individuais` | `admin_historico_os_exportar_excel_individuais` | 594 |
| GET | `/admin/historico-os/exportar-pdf-individuais` | `admin_historico_os_exportar_pdf_individuais` | 624 |
| GET | `/admin/historico-os/exportar-pdf-individuais/jobs/<job_id>` | `admin_historico_os_pdf_job_status` | 640 |
| GET | `/admin/historico-os/exportar-pdf-individuais/jobs/<job_id>/download` | `admin_historico_os_pdf_job_download` | 656 |
| GET | `/admin/os/<int:os_id>/equipe-uvis-formulario` | `admin_equipe_uvis_os_formulario_view` | 683 |

### app/modules/admin_uvis/routes.py

Fonte: [app/modules/admin_uvis/routes.py](../app/modules/admin_uvis/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET, POST | `/admin/uvis/novo` | `admin_uvis_novo` | 39 |
| GET | `/admin/uvis` | `admin_uvis_listar` | 107 |
| GET, POST | `/admin/uvis/<int:id>/editar` | `admin_uvis_editar` | 151 |
| POST | `/admin/uvis/<int:id>/excluir` | `admin_uvis_excluir` | 239 |
| GET | `/admin/uvis/exportar` | `admin_uvis_exportar` | 272 |

### app/modules/agenda_notificacoes/routes.py

Fonte: [app/modules/agenda_notificacoes/routes.py](../app/modules/agenda_notificacoes/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/agenda` | `agenda` | 18 |
| GET | `/agenda/rotas-dia` | `agenda_rotas_dia` | 32 |
| GET | `/agenda/exportar_excel` | `agenda_exportar_excel` | 43 |
| GET | `/notificacoes/<int:notif_id>/ler` | `ler_notificacao` | 57 |
| GET | `/notificacoes` | `notificacoes` | 64 |
| POST | `/notificacoes/<int:notif_id>/excluir` | `excluir_notificacao` | 69 |
| POST | `/notificacoes/limpar` | `limpar_notificacoes` | 76 |

### app/modules/agro/routes.py

Fonte: [app/modules/agro/routes.py](../app/modules/agro/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/agro` | `agro_root` | 3705 |
| GET | `/agro/piloto` | `agro_piloto_dashboard` | 3714 |
| GET | `/agro/piloto/os` | `agro_piloto_os_listar` | 3778 |
| GET | `/agro/piloto/mapeamentos` | `agro_piloto_mapeamentos_listar` | 3816 |
| GET | `/agro/admin` | `admin_agro` | 3863 |
| GET | `/agro/financeiro` | `agro_financeiro_dashboard` | 3872 |
| GET | `/agro/financeiro/categorias` | `agro_financeiro_categorias_listar` | 3879 |
| GET, POST | `/agro/financeiro/categorias/cadastrar` | `agro_financeiro_categoria_nova` | 3933 |
| GET, POST | `/agro/financeiro/categorias/<int:subcategoria_id>/editar` | `agro_financeiro_categoria_editar` | 3971 |
| POST | `/agro/financeiro/categorias/<int:subcategoria_id>/alternar` | `agro_financeiro_categoria_alternar` | 4037 |
| GET | `/agro/bancos` | `agro_bancos_listar` | 4057 |
| GET | `/agro/bancos/conciliacao` | `agro_bancos_conciliacao` | 4075 |
| GET, POST | `/agro/bancos/cadastrar` | `agro_banco_novo` | 4188 |
| GET, POST | `/agro/bancos/<int:banco_id>/editar` | `agro_banco_editar` | 4235 |
| POST | `/agro/bancos/<int:banco_id>/deletar` | `agro_banco_deletar` | 4276 |
| GET | `/agro/relatorios/fluxo-caixa/excel` | `agro_fluxo_caixa_exportar_excel` | 4291 |
| GET | `/agro/relatorios/dre-gerencial/excel` | `agro_dre_gerencial_exportar_excel` | 4304 |
| GET | `/agro/clientes` | `agro_clientes_listar` | 4317 |
| GET | `/agro/clientes-fornecedores` | `agro_clientes_menu` | 4342 |
| GET, POST | `/agro/clientes/cadastrar` | `agro_cliente_novo` | 4358 |
| GET, POST | `/agro/clientes/<int:cliente_id>/editar` | `agro_cliente_editar` | 4392 |
| POST | `/agro/clientes/<int:cliente_id>/deletar` | `agro_cliente_deletar` | 4439 |
| GET | `/agro/fornecedores` | `agro_fornecedores_listar` | 4454 |
| GET, POST | `/agro/fornecedores/cadastrar` | `agro_fornecedor_novo` | 4479 |
| GET, POST | `/agro/fornecedores/<int:fornecedor_id>/editar` | `agro_fornecedor_editar` | 4514 |
| POST | `/agro/fornecedores/<int:fornecedor_id>/deletar` | `agro_fornecedor_deletar` | 4565 |
| GET | `/agro/orcamentos` | `agro_orcamentos_listar` | 4580 |
| GET, POST | `/agro/orcamentos/cadastrar` | `agro_orcamento_novo` | 4616 |
| GET, POST | `/agro/orcamentos/<int:orcamento_id>/editar` | `agro_orcamento_editar` | 4736 |
| GET, POST | `/agro/orcamentos/<int:orcamento_id>/rd-mapeamento` | `agro_rd_mapeamento_editar` | 4888 |
| GET | `/agro/orcamentos/template-mapeamento` | `agro_orcamentos_template_mapeamento` | 4950 |
| POST | `/agro/orcamentos/<int:orcamento_id>/template-mapeamento` | `agro_orcamento_template_mapeamento_salvar` | 4977 |
| GET, POST | `/agro/piloto/rd-mapeamento/<int:rd_id>` | `agro_piloto_rd_mapeamento` | 5023 |
| GET, POST | `/agro/orcamentos/<int:orcamento_id>/contrato` | `agro_contrato_editar` | 5099 |
| GET | `/agro/contratos` | `agro_contratos_listar` | 5220 |
| GET | `/agro/contratos/comprovantes` | `agro_contratos_comprovantes` | 5262 |
| GET | `/agro/financeiro/contas` | `agro_financeiro_contas` | 5293 |
| GET | `/agro/financeiro/relatorio-geral` | `agro_relatorio_contas_geral` | 5311 |
| GET | `/agro/financeiro/relatorio-geral/excel` | `agro_relatorio_contas_geral_excel` | 5335 |
| GET | `/agro/financeiro/relatorio-geral/pdf` | `agro_relatorio_contas_geral_pdf` | 5354 |
| GET | `/agro/financeiro/contas-receber` | `agro_contas_receber_listar` | 5373 |
| GET | `/agro/financeiro/contas-pagar` | `agro_contas_pagar_listar` | 5419 |
| GET | `/agro/financeiro` | `agro_financeiro_listar` | 5463 |
| GET | `/agro/financeiro/configuracoes` | `agro_financeiro_configuracoes` | 5506 |
| POST | `/agro/financeiro/configuracoes` | `agro_financeiro_configuracoes_salvar` | 5520 |
| GET, POST | `/agro/financeiro/cadastrar` | `agro_financeiro_novo` | 5553 |
| GET, POST | `/agro/financeiro/<int:lancamento_id>/editar` | `agro_financeiro_editar` | 5671 |
| POST | `/agro/financeiro/<int:lancamento_id>/receber` | `agro_financeiro_receber_os_concluida` | 5789 |
| POST | `/agro/financeiro/<int:lancamento_id>/deletar` | `agro_financeiro_deletar` | 5848 |
| GET | `/agro/financeiro/entradas` | `agro_financeiro_entrada_listar` | 5873 |
| GET, POST | `/agro/financeiro/entradas/cadastrar` | `agro_financeiro_entrada_novo` | 5900 |
| GET, POST | `/agro/financeiro/entradas/<int:lancamento_id>/editar` | `agro_financeiro_entrada_editar` | 6027 |
| POST | `/agro/financeiro/entradas/<int:lancamento_id>/deletar` | `agro_financeiro_entrada_deletar` | 6133 |
| GET | `/agro/financeiro/saidas` | `agro_financeiro_saida_listar` | 6161 |
| GET, POST | `/agro/financeiro/saidas/cadastrar` | `agro_financeiro_saida_novo` | 6191 |
| GET, POST | `/agro/financeiro/saidas/<int:lancamento_id>/editar` | `agro_financeiro_saida_editar` | 6329 |
| POST | `/agro/financeiro/saidas/<int:lancamento_id>/deletar` | `agro_financeiro_saida_deletar` | 6447 |
| GET | `/agro/caixa` | `agro_caixa_diario` | 6475 |
| POST | `/agro/caixa/abrir` | `agro_caixa_abrir` | 6490 |
| POST | `/agro/caixa/fechar` | `agro_caixa_fechar` | 6540 |
| GET | `/agro/contratos/template` | `agro_contratos_template` | 6570 |
| POST | `/agro/contratos/<int:contrato_id>/template` | `agro_contrato_template_salvar` | 6589 |
| POST | `/agro/contratos/<int:contrato_id>/deletar` | `agro_contrato_deletar` | 6611 |
| POST | `/agro/contratos/<int:contrato_id>/comprovante-pagamento` | `agro_contrato_comprovante_pagamento_upload` | 6626 |
| GET | `/agro/contratos/<int:contrato_id>/comprovante-pagamento` | `agro_contrato_comprovante_pagamento` | 6647 |
| POST | `/agro/contratos/<int:contrato_id>/comprovante-pagamento/remover` | `agro_contrato_comprovante_pagamento_remover` | 6664 |
| GET | `/agro/orcamentos/<int:orcamento_id>/anexo` | `agro_orcamento_anexo` | 6677 |
| GET | `/agro/orcamentos/<int:orcamento_id>/pdf` | `agro_orcamento_pdf` | 6688 |
| GET | `/agro/orcamentos/<int:orcamento_id>/contrato/pdf` | `agro_contrato_pdf` | 6704 |
| GET | `/agro/os/<int:os_id>/relatorio/pdf` | `agro_os_relatorio_pdf` | 6714 |
| POST | `/agro/os/<int:os_id>/deletar` | `agro_os_deletar` | 6728 |
| GET | `/agro/os` | `agro_os_listar` | 6739 |
| GET | `/agro/logs-voo` | `agro_logs_voo` | 6765 |
| GET | `/agro/logs-voo/exportar` | `agro_logs_voo_exportar` | 6793 |
| POST | `/agro/logs-voo/importar-excel` | `agro_logs_voo_importar_excel` | 6807 |
| POST | `/agro/logs-voo/importar-kml` | `agro_logs_voo_importar_kml` | 6833 |
| POST | `/agro/logs-voo/rota/<int:route_id>/vincular-os` | `agro_logs_voo_vincular_os` | 6862 |
| POST | `/agro/logs-voo/rota/<int:route_id>/desvincular-os` | `agro_logs_voo_desvincular_os` | 6881 |
| GET | `/api/agro/kml-route/<int:route_id>` | `api_agro_kml_route` | 6891 |
| GET | `/agro/logs-voo/rota/<int:route_id>/kml` | `agro_logs_voo_baixar_kml` | 6898 |
| GET, POST | `/agro/contratos/<int:contrato_id>/os/cadastrar` | `agro_os_nova` | 6920 |
| GET, POST | `/agro/os/<int:os_id>/editar` | `agro_os_editar` | 7094 |
| POST | `/agro/orcamentos/<int:orcamento_id>/deletar` | `agro_orcamento_deletar` | 7243 |
| GET | `/agro/equipes` | `agro_equipes_listar` | 7260 |
| GET, POST | `/agro/equipes/cadastrar` | `agro_equipe_nova` | 7282 |
| GET, POST | `/agro/equipes/<int:equipe_id>/editar` | `agro_equipe_editar` | 7307 |
| POST | `/agro/equipes/<int:equipe_id>/deletar` | `agro_equipe_deletar` | 7334 |
| GET | `/agro/pilotos` | `agro_pilotos_listar` | 7347 |
| GET, POST | `/agro/pilotos/cadastrar` | `agro_piloto_novo` | 7371 |
| GET, POST | `/agro/pilotos/<int:piloto_id>/editar` | `agro_piloto_editar` | 7409 |
| POST | `/agro/pilotos/<int:piloto_id>/deletar` | `agro_piloto_deletar` | 7460 |
| GET | `/agro/equipamentos` | `agro_equipamentos_listar` | 7472 |
| GET, POST | `/agro/equipamentos/cadastrar` | `agro_equipamento_novo` | 7500 |
| GET, POST | `/agro/equipamentos/<int:equipamento_id>/editar` | `agro_equipamento_editar` | 7536 |
| POST | `/agro/equipamentos/<int:equipamento_id>/deletar` | `agro_equipamento_deletar` | 7598 |

### app/modules/agro/talent_bank_routes.py

Fonte: [app/modules/agro/talent_bank_routes.py](../app/modules/agro/talent_bank_routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/agro/banco-de-talentos` | `agro_talentos_listar` | 84 |
| GET, POST | `/agro/banco-de-talentos/novo` | `agro_talento_novo` | 136 |
| GET, POST | `/agro/banco-de-talentos/<int:curriculo_id>` | `agro_talento_detalhe` | 198 |
| GET | `/agro/banco-de-talentos/<int:curriculo_id>/pdf` | `agro_talento_pdf` | 226 |
| POST | `/agro/banco-de-talentos/<int:curriculo_id>/reprocessar` | `agro_talento_reprocessar` | 247 |
| POST | `/agro/banco-de-talentos/<int:curriculo_id>/deletar` | `agro_talento_deletar` | 276 |

### app/modules/anexos/routes.py

Fonte: [app/modules/anexos/routes.py](../app/modules/anexos/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/solicitacao/<int:id>/anexo` | `baixar_anexo` | 15 |
| GET | `/admin/solicitacao/<int:id>/anexo` | `baixar_anexo_admin` | 16 |
| POST | `/admin/solicitacao/<int:id>/remover_anexo` | `remover_anexo` | 36 |

### app/modules/auditoria/routes.py

Fonte: [app/modules/auditoria/routes.py](../app/modules/auditoria/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/admin/logs-usuarios` | `admin_logs_usuarios` | 20 |

### app/modules/auth/routes.py

Fonte: [app/modules/auth/routes.py](../app/modules/auth/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET, POST | `/login` | `login` | 19 |
| GET, POST | `/uvis-operacional/login` | `login_uvis_operacional` | 50 |
| GET, POST | `/agro/login` | `login_piloto_agro` | 76 |
| GET | `/logout` | `logout` | 102 |

### app/modules/backup/routes.py

Fonte: [app/modules/backup/routes.py](../app/modules/backup/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/backup` | `backup_page` | 18 |
| GET | `/backup/status` | `backup_status` | 43 |
| GET | `/backups` | `backups_list_page` | 51 |

### app/modules/canceladas/routes.py

Fonte: [app/modules/canceladas/routes.py](../app/modules/canceladas/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| POST | `/solicitacao/<int:id>/cancelar` | `cancelar_solicitacao` | 11 |
| GET | `/canceladas` | `solicitacoes_canceladas` | 25 |

### app/modules/cep/routes.py

Fonte: [app/modules/cep/routes.py](../app/modules/cep/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/api/cep/<cep>` | `api_cep` | 8 |
| POST | `/api/cep/busca-endereco` | `api_cep_by_address` | 18 |

### app/modules/chatbot/routes.py

Fonte: [app/modules/chatbot/routes.py](../app/modules/chatbot/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| POST | `/api/uvis/chatbot` | `uvis_chatbot` | 16 |
| POST | `/api/admin/chatbot` | `admin_chatbot` | 23 |
| POST | `/api/agro/admin/chatbot` | `agro_admin_chatbot` | 33 |
| POST | `/api/agro/piloto/chatbot` | `agro_piloto_chatbot` | 43 |

### app/modules/clientes/routes.py

Fonte: [app/modules/clientes/routes.py](../app/modules/clientes/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/clientes` | `clientes_menu` | 39 |
| GET, POST | `/clientes/cadastrar` | `cadastrar_clientes` | 54 |
| GET | `/clientes/listar` | `listar_clientes` | 150 |
| GET, POST | `/clientes/<int:cliente_id>/editar` | `editar_cliente` | 212 |
| POST | `/clientes/<int:cliente_id>/deletar` | `deletar_cliente` | 292 |

### app/modules/dashboard/routes.py

Fonte: [app/modules/dashboard/routes.py](../app/modules/dashboard/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/` | `dashboard` | 21 |
| GET | `/uvis/historico-os` | `uvis_historico_os` | 45 |
| GET, POST | `/uvis/os/<int:os_id>/formulario` | `uvis_os_formulario_view` | 60 |
| GET | `/uvis/os/<int:os_id>/equipe-formulario` | `uvis_equipe_os_formulario_view` | 103 |

### app/modules/denuncias/routes.py

Fonte: [app/modules/denuncias/routes.py](../app/modules/denuncias/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/denuncias` | `denuncias_listar` | 37 |
| GET | `/denuncias/<int:denuncia_id>` | `denuncia_detalhe` | 69 |
| GET | `/coordenadoria/denuncias` | `coordenadoria_denuncias_listar` | 85 |
| GET | `/coordenadoria/denuncias/<int:denuncia_id>` | `coordenadoria_denuncia_detalhe` | 113 |
| POST | `/denuncias/<int:denuncia_id>/encaminhar-coordenadoria` | `denuncia_encaminhar_coordenadoria` | 129 |
| POST | `/coordenadoria/denuncias/<int:denuncia_id>/designar-uvis` | `coordenadoria_denuncia_designar_uvis` | 148 |
| GET | `/uvis/denuncias` | `uvis_denuncias_listar` | 163 |
| GET, POST | `/uvis/denuncias/<int:denuncia_id>` | `uvis_denuncia_detalhe` | 191 |
| POST | `/denuncias/<int:denuncia_id>/arquivar` | `denuncia_arquivar` | 229 |
| GET | `/denuncias/anexos/<int:anexo_id>` | `denuncia_anexo` | 244 |

### app/modules/dev_dashboard/routes.py

Fonte: [app/modules/dev_dashboard/routes.py](../app/modules/dev_dashboard/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| POST | `/api/watchdog/deploy-events` | `watchdog_deploy_event` | 33 |
| GET | `/dev` | `dev_dashboard` | 49 |
| GET | `/dev/data` | `dev_dashboard_data` | 55 |
| GET | `/dev/errors/<int:log_id>` | `dev_dashboard_error_detail` | 61 |
| POST | `/dev/checks/<slug>` | `dev_dashboard_manual_check` | 70 |

### app/modules/dji_flight_logs/routes.py

Fonte: [app/modules/dji_flight_logs/routes.py](../app/modules/dji_flight_logs/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/relatorios/dji-logs` | `relatorios_dji_logs` | 24 |
| GET | `/relatorios/dji-logs/exportar` | `exportar_dji_logs_excel` | 53 |
| POST | `/relatorios/dji-logs/importar` | `importar_dji_logs` | 68 |
| POST | `/relatorios/dji-logs/importar-kml` | `importar_dji_kml` | 96 |
| GET | `/api/dji-kml-route/<int:route_id>` | `api_dji_kml_route` | 126 |
| POST | `/relatorios/dji-logs/rota/<int:route_id>/vincular-os` | `vincular_dji_kml_route_os` | 134 |
| POST | `/relatorios/dji-logs/rota/<int:route_id>/excluir` | `excluir_dji_kml_route` | 162 |
| GET | `/relatorios/dji-logs/rota/<int:route_id>` | `visualizar_dji_kml_route` | 185 |
| GET | `/relatorios/dji-logs/rota/<int:route_id>/kml` | `baixar_dji_kml_route` | 203 |

### app/modules/drones_import/routes.py

Fonte: [app/modules/drones_import/routes.py](../app/modules/drones_import/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/drones/importar-planilha` | `importar_planilha_drones` | 49 |
| GET | `/agro/equipamentos/importar-planilha` | `agro_importar_planilha_drones` | 54 |
| POST | `/api/drones/importar-planilha` | `importar_planilha_drones_api` | 59 |

### app/modules/equipamentos/routes.py

Fonte: [app/modules/equipamentos/routes.py](../app/modules/equipamentos/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/equipamentos` | `listar_equipamentos` | 54 |
| GET | `/equipamentos/drones` | `listar_drones` | 59 |
| GET | `/equipamentos/baterias` | `listar_baterias` | 70 |
| GET, POST | `/drones/cadastrar` | `cadastrar_drone` | 81 |
| GET, POST | `/drones/<int:drone_id>/editar` | `editar_drone` | 109 |
| POST | `/drones/<int:drone_id>/deletar` | `deletar_drone` | 155 |
| GET, POST | `/baterias/cadastrar` | `cadastrar_bateria` | 171 |
| GET, POST | `/baterias/<int:bateria_id>/editar` | `editar_bateria` | 203 |
| POST | `/baterias/<int:bateria_id>/deletar` | `deletar_bateria` | 249 |
| GET | `/equipamentos/em-manutencao` | `equipamentos_manutencao` | 265 |
| GET | `/equipamentos/manutencoes/historico` | `equipamentos_manutencoes_historico` | 275 |
| GET | `/equipamentos/manutencoes/historico/excel` | `equipamentos_manutencoes_historico_excel` | 284 |
| GET | `/equipamentos/manutencoes/pecas/historico` | `equipamentos_manutencoes_pecas_historico` | 291 |
| GET | `/equipamentos/manutencoes/pecas/historico/excel` | `equipamentos_manutencoes_pecas_historico_excel` | 300 |
| GET | `/equipamentos/manutencoes/<int:manutencao_id>` | `equipamento_manutencao_detalhe` | 307 |
| GET, POST | `/equipamentos/<int:drone_id>/manutencao/pecas` | `equipamento_manutencao_pecas` | 318 |
| GET | `/equipamentos/<int:drone_id>/manutencao/pdf` | `equipamento_manutencao_pdf` | 350 |
| GET | `/equipamentos/manutencoes/<int:manutencao_id>/pdf` | `equipamento_manutencao_historico_pdf` | 365 |
| POST | `/equipamentos/<int:drone_id>/manutencao/encerrar` | `equipamento_manutencao_encerrar` | 379 |
| POST | `/equipamentos/baterias/update_ciclos/<int:id>` | `update_ciclos` | 395 |
| POST | `/drones/<int:drone_id>/manutencao` | `enviar_manutencao_drone` | 402 |

### app/modules/equipe_uvis_dashboard/routes.py

Fonte: [app/modules/equipe_uvis_dashboard/routes.py](../app/modules/equipe_uvis_dashboard/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/equipe-uvis` | `dashboard_equipe_uvis` | 20 |
| GET, POST | `/equipe-uvis/os/<int:os_id>/formulario` | `equipe_uvis_os_formulario_view` | 41 |
| GET | `/equipe-uvis/os/historico` | `equipe_uvis_os_historico` | 83 |
| POST | `/equipe-uvis/os/<int:os_id>/concluir` | `equipe_uvis_concluir_os` | 98 |

### app/modules/equipes/routes.py

Fonte: [app/modules/equipes/routes.py](../app/modules/equipes/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET, POST | `/equipes/cadastrar` | `cadastrar_equipes` | 31 |
| GET | `/equipes` | `listar_equipes` | 169 |
| POST | `/equipes/<int:equipe_id>/credenciais` | `atualizar_credenciais_equipe` | 246 |
| GET, POST | `/equipes/<int:equipe_id>/editar` | `editar_equipe` | 273 |
| POST | `/equipes/<int:equipe_id>/deletar` | `deletar_equipe` | 437 |

### app/modules/estoque/routes.py

Fonte: [app/modules/estoque/routes.py](../app/modules/estoque/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/estoque` | `estoque_listar` | 26 |
| GET | `/estoque/export/excel` | `estoque_export_excel` | 33 |
| GET, POST | `/estoque/novo` | `estoque_novo` | 40 |
| GET, POST | `/estoque/<int:peca_id>/editar` | `estoque_editar` | 64 |
| POST | `/estoque/<int:peca_id>/deletar` | `estoque_deletar` | 88 |

### app/modules/feedback/routes.py

Fonte: [app/modules/feedback/routes.py](../app/modules/feedback/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/feedback/notificacoes/status` | `feedback_notificacoes_status` | 209 |
| GET | `/feedback` | `feedback_listar` | 219 |
| GET | `/bugs` | `bugs_listar` | 297 |
| GET | `/bugs/ajuda` | `bugs_ajuda` | 352 |
| GET, POST | `/feedback/novo` | `feedback_novo` | 363 |
| GET, POST | `/bugs/novo` | `bug_report_novo` | 364 |
| GET | `/feedback/<int:topico_id>` | `feedback_detalhe` | 503 |
| GET | `/bugs/<int:topico_id>/acompanhar` | `bug_acompanhamento` | 531 |
| GET | `/feedback/<int:topico_id>/status` | `feedback_status` | 549 |
| POST | `/feedback/<int:topico_id>/comentar` | `feedback_comentar` | 568 |
| GET | `/feedback/anexos/<int:anexo_id>` | `feedback_anexo` | 595 |
| POST | `/feedback/<int:topico_id>/comentarios/<int:comment_id>/editar` | `feedback_comentario_editar` | 641 |
| POST | `/feedback/<int:topico_id>/comentarios/<int:comment_id>/apagar` | `feedback_comentario_apagar` | 662 |
| POST | `/feedback/<int:topico_id>/atualizar` | `feedback_atualizar` | 678 |
| POST | `/feedback/<int:topico_id>/assumir` | `feedback_assumir` | 719 |
| POST | `/feedback/<int:topico_id>/corrigir` | `feedback_corrigir` | 739 |

### app/modules/financeiro/routes.py

Fonte: [app/modules/financeiro/routes.py](../app/modules/financeiro/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/financeiro` | `financeiro_central` | 107 |
| GET | `/financeiro/empresas/<empresa_slug>` | `financeiro_empresa` | 118 |
| GET | `/financeiro/empresas/<empresa_slug>/clientes` | `financeiro_empresa_clientes` | 132 |
| GET | `/financeiro/empresas/<empresa_slug>/relacionamentos` | `financeiro_empresa_relacionamentos` | 137 |
| GET | `/financeiro/empresas/<empresa_slug>/fornecedores` | `financeiro_empresa_fornecedores` | 142 |
| GET | `/financeiro/empresas/<empresa_slug>/comercial` | `financeiro_empresa_comercial` | 147 |

### app/modules/mapas/routes.py

Fonte: [app/modules/mapas/routes.py](../app/modules/mapas/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| POST | `/api/geocode` | `api_geocode` | 14 |
| GET | `/api/heatmap-data` | `heatmap_data` | 47 |
| GET | `/mapa-relatorio` | `mapa_relatorio` | 58 |
| GET | `/consultar_endereco_geolocalizacao` | `consultar_endereco_geolocalizacao` | 73 |

### app/modules/painel_operacional/routes.py

Fonte: [app/modules/painel_operacional/routes.py](../app/modules/painel_operacional/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/diretor/painel-operacional` | `painel_operacional` | 12 |
| POST | `/api/painel-operacional/contexto-local` | `api_painel_operacional_contexto` | 28 |

### app/modules/piloto_checklists/routes.py

Fonte: [app/modules/piloto_checklists/routes.py](../app/modules/piloto_checklists/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET, POST | `/piloto/checklists/semanais` | `piloto_checklist_semanal` | 24 |

### app/modules/piloto_os/routes.py

Fonte: [app/modules/piloto_os/routes.py](../app/modules/piloto_os/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/piloto/os` | `piloto_os` | 1243 |
| GET | `/piloto/dosagem` | `piloto_dosagem` | 1281 |
| GET, POST | `/piloto/os/<int:os_id>/dosagem` | `piloto_os_dosagem` | 1287 |
| GET | `/piloto/os/historico` | `piloto_os_historico` | 1316 |
| POST | `/piloto/os/<int:os_id>/concluir` | `piloto_concluir_os` | 1332 |
| GET | `/piloto/os/formulario` | `piloto_os_formulario_redirect` | 1345 |
| GET, POST | `/piloto/os/<int:os_id>/formulario` | `piloto_os_formulario_view` | 1357 |
| GET | `/os/<int:os_id>/video` | `os_video` | 1412 |
| GET | `/os/<int:os_id>/imagem-principal` | `os_imagem_principal` | 1422 |
| GET | `/os/<int:os_id>/imagem-complementar/<int:image_index>` | `os_imagem_complementar` | 1432 |
| GET | `/piloto/api/drone/<int:drone_id>` | `piloto_api_drone` | 1442 |
| PUT | `/api/os/<int:os_id>/upload-stream` | `os_upload_stream` | 1452 |
| PUT | `/api/os/<int:os_id>/upload-video-stream` | `os_upload_video_stream` | 1497 |
| PUT | `/api/os/<int:os_id>/upload-video-background` | `os_upload_video_background` | 1542 |
| POST | `/api/os/<int:os_id>/upload-video-background/init` | `os_upload_video_background_init` | 1621 |
| PUT | `/api/video-upload-sessions/<session_id>/chunks/<int:chunk_index>` | `video_upload_session_chunk` | 1688 |
| POST | `/api/video-upload-sessions/<session_id>/complete` | `video_upload_session_complete` | 1747 |
| GET | `/api/video-upload-jobs/<job_id>` | `video_upload_job_status` | 1812 |
| PUT | `/api/os/<int:os_id>/upload-complementary-stream` | `os_upload_complementary_stream` | 1846 |
| DELETE | `/api/os/<int:os_id>/imagem-principal` | `os_delete_principal_image` | 1900 |
| DELETE | `/api/os/<int:os_id>/video` | `os_delete_video` | 1936 |
| DELETE | `/api/os/<int:os_id>/imagem-complementar/<int:image_index>` | `os_delete_complementary_image` | 1970 |
| GET, POST | `/admin/os/<int:os_id>/formulario` | `admin_os_formulario_view` | 2010 |
| GET | `/admin/os/<int:os_id>/export/pdf/v2` | `admin_export_os_pdf_v2` | 2051 |
| GET | `/admin/os/<int:os_id>/export/excel/v2` | `admin_export_os_excel_v2` | 2065 |

### app/modules/pilotos/routes.py

Fonte: [app/modules/pilotos/routes.py](../app/modules/pilotos/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET, POST | `/pilotos/cadastrar` | `cadastrar_pilotos` | 41 |
| GET | `/pilotos` | `listar_pilotos` | 128 |
| GET, POST | `/pilotos/<int:piloto_id>/editar` | `editar_piloto` | 189 |
| POST | `/pilotos/<int:piloto_id>/deletar` | `deletar_piloto` | 302 |

### app/modules/portal_cidadao/routes.py

Fonte: [app/modules/portal_cidadao/routes.py](../app/modules/portal_cidadao/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/portal-cidadao` | `portal_cidadao` | 19 |
| GET | `/portal-cidadao/boletim-dengue` | `portal_cidadao_boletim_dengue` | 29 |
| POST | `/portal-cidadao/denuncias` | `portal_cidadao_denuncias_criar` | 56 |
| GET | `/portal-cidadao/cep/<cep>` | `portal_cidadao_cep` | 78 |
| POST | `/portal-cidadao/reverse-geocode` | `portal_cidadao_reverse_geocode` | 101 |

### app/modules/relatorios/routes.py

Fonte: [app/modules/relatorios/routes.py](../app/modules/relatorios/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/relatorios/solicitacoes` | `relatorios_solicitacoes` | 297 |
| GET | `/relatorios` | `relatorios` | 317 |
| GET | `/relatorios-os` | `relatorios_os` | 325 |
| GET | `/relatorios/retornos-automaticos` | `relatorios_retornos_automaticos` | 345 |
| GET | `/relatorios/retornos-automaticos/equipe/<int:equipe_id>` | `relatorios_retornos_automaticos_equipe` | 365 |
| GET | `/relatorios/retornos-automaticos/sem-equipe` | `relatorios_retornos_automaticos_sem_equipe` | 397 |
| GET | `/relatorios-coleta-imagens` | `relatorios_coleta_imagens` | 421 |
| POST | `/relatorios-coleta-imagens/os/<int:os_id>/ok-uvis` | `relatorios_coleta_imagens_ok_uvis` | 441 |
| GET | `/admin/exportar_relatorio_pdf` | `exportar_relatorio_pdf` | 463 |
| GET | `/admin/exportar_relatorio_excel` | `exportar_relatorio_excel` | 482 |
| GET | `/relatorios-os/export/excel` | `relatorios_os_export_excel` | 497 |
| GET | `/relatorios-os/export/pdf` | `relatorios_os_export_pdf` | 512 |
| GET | `/relatorios-coleta-imagens/export/pdf` | `relatorios_coleta_imagens_export_pdf` | 531 |
| GET | `/relatorios-coleta-imagens/export/pdf-zip` | `relatorios_coleta_imagens_export_pdf_zip` | 547 |
| GET | `/relatorios-coleta-imagens/export/pdf/jobs/<job_id>` | `relatorios_coleta_imagens_pdf_job_status` | 567 |
| GET | `/relatorios-coleta-imagens/export/pdf/jobs/<job_id>/download` | `relatorios_coleta_imagens_pdf_job_download` | 583 |

### app/modules/solicitacoes/routes.py

Fonte: [app/modules/solicitacoes/routes.py](../app/modules/solicitacoes/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/api/solicitacao/checar-bloqueio` | `api_solicitacao_checar_bloqueio` | 21 |
| GET, POST | `/novo_cadastro` | `novo` | 45 |
| GET, POST | `/solicitacao/editar/<int:id>` | `editar_solicitacao` | 71 |
| POST | `/admin/deletar/<int:id>` | `deletar_registro` | 97 |

### app/modules/usuarios/routes.py

Fonte: [app/modules/usuarios/routes.py](../app/modules/usuarios/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET, POST | `/admin/prefeituras/nova` | `admin_prefeitura_nova` | 105 |
| GET | `/admin/prefeituras` | `admin_prefeituras` | 164 |
| GET, POST | `/admin/prefeituras/<int:id>/editar` | `admin_prefeitura_editar` | 198 |
| POST | `/admin/prefeituras/<int:id>/excluir` | `admin_prefeitura_excluir` | 259 |
| GET, POST | `/admin/usuarios/novo` | `admin_usuario_novo` | 294 |
| GET | `/admin/usuarios` | `admin_usuarios_listar` | 429 |
| GET, POST | `/admin/usuarios/<int:id>/editar` | `admin_usuario_editar` | 450 |
| POST | `/admin/usuarios/<int:id>/reset_senha` | `admin_usuario_reset_senha` | 607 |
| POST | `/admin/usuarios/<int:id>/excluir` | `admin_usuario_excluir` | 642 |

### app/modules/uvis_equipes/routes.py

Fonte: [app/modules/uvis_equipes/routes.py](../app/modules/uvis_equipes/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET, POST | `/uvis/acesso-operacional` | `uvis_acesso_operacional` | 44 |
| GET | `/uvis/equipes` | `listar_equipes_uvis` | 100 |
| POST | `/uvis/equipes/<string:nome_equipe>/credenciais` | `atualizar_credenciais_equipe_uvis` | 107 |
| GET | `/uvis/equipes/<string:nome_equipe>` | `listar_membros_equipe_uvis` | 144 |
| GET, POST | `/uvis/equipes/<string:nome_equipe>/adicionar` | `adicionar_membro_equipe_uvis` | 162 |
| GET, POST | `/uvis/equipes/nova` | `criar_equipe_uvis` | 217 |
| GET, POST | `/uvis/equipe-membro/<int:membro_id>/editar` | `editar_membro_equipe_uvis` | 269 |
| POST | `/uvis/equipe-membro/<int:membro_id>/deletar` | `deletar_membro_equipe_uvis` | 309 |
| POST | `/solicitacao/<int:id>/atribuir-equipe-uvis` | `atribuir_equipe_uvis_solicitacao` | 334 |
| GET | `/admin/uvis/equipes` | `admin_listar_equipes_uvis` | 360 |
| POST | `/admin/uvis/<int:uvis_id>/acesso-operacional` | `admin_atualizar_acesso_operacional_uvis` | 372 |
| GET | `/admin/uvis/<int:uvis_id>/equipes/<string:nome_equipe>` | `admin_listar_membros_equipe_uvis` | 417 |

### app/modules/veiculos/routes.py

Fonte: [app/modules/veiculos/routes.py](../app/modules/veiculos/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/veiculos/rastreamento` | `veiculos_rastreamento` | 126 |
| GET | `/veiculos/rastreamento/dados` | `veiculos_rastreamento_dados` | 137 |
| GET | `/veiculos/menu` | `veiculos_menu` | 147 |
| GET | `/veiculos` | `listar_veiculos` | 161 |
| POST | `/veiculos/equipes` | `atualizar_equipes_veiculos` | 174 |
| GET | `/veiculos/logs` | `veiculos_logs` | 198 |
| GET | `/veiculos/limpezas` | `veiculos_limpezas` | 207 |
| GET | `/veiculos/limpeza/alertas` | `veiculos_alertas_limpeza` | 216 |
| GET | `/veiculos/logs/veiculo/<int:veiculo_id>` | `veiculo_logs_detalhe` | 227 |
| GET | `/veiculos/logs/exportar` | `exportar_logs_veiculos_xlsx` | 239 |
| GET | `/admin/veiculos/logs-excluidos` | `veiculos_logs_excluidos` | 248 |
| POST | `/veiculos/logs/<int:log_id>/corrigir-km` | `corrigir_log_veiculo` | 263 |
| POST | `/veiculos/logs/<int:log_id>/deletar` | `deletar_log_veiculo` | 309 |
| GET | `/veiculos/logs/<int:log_id>/midia/<tipo>` | `veiculo_log_midia_skybox` | 356 |
| GET | `/veiculos/abastecimentos/<int:abastecimento_id>/midia/<tipo>` | `veiculo_abastecimento_midia_skybox` | 377 |
| GET, POST | `/veiculos/cadastrar` | `cadastrar_veiculo` | 403 |
| GET, POST | `/veiculos/<int:veiculo_id>/editar` | `editar_veiculo` | 454 |
| POST | `/veiculos/<int:veiculo_id>/deletar` | `deletar_veiculo` | 509 |
| GET | `/piloto/veiculos` | `piloto_veiculos` | 524 |
| GET | `/piloto/caixa-entrada` | `piloto_caixa_entrada` | 543 |
| POST | `/piloto/caixa-entrada/limpeza/<int:veiculo_id>/confirmar` | `piloto_confirmar_alerta_limpeza` | 556 |
| POST | `/piloto/veiculos/<int:veiculo_id>/km` | `piloto_atualizar_km_veiculo` | 579 |
| POST | `/piloto/veiculos/<int:veiculo_id>/abastecimento` | `piloto_registrar_abastecimento_turno` | 606 |
| POST | `/piloto/veiculos/<int:veiculo_id>/limpeza` | `piloto_registrar_limpeza_turno` | 637 |
| POST | `/piloto/veiculos/<int:veiculo_id>/encerrar` | `piloto_encerrar_turno` | 666 |

### app/modules/vigilancia/routes.py

Fonte: [app/modules/vigilancia/routes.py](../app/modules/vigilancia/routes.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET, POST | `/vigilancia/validacao` | `vigilancia_validacao` | 148 |
| POST | `/api/vigilancia/validacao` | `vigilancia_validacao_api` | 169 |
| GET | `/vigilancia/modelo.csv` | `vigilancia_modelo_csv` | 182 |

### app/shared/session_security.py

Fonte: [app/shared/session_security.py](../app/shared/session_security.py).

| Método | Caminho | Endpoint local | Linha |
| --- | --- | --- | ---: |
| GET | `/auth/session-status` | `status` | 138 |
| POST | `/auth/session-activity` | `activity` | 147 |

## Testes Python

| Arquivo | Casos declarados |
| --- | ---: |
| [test_agro_payment_receipt_skybox.py](../tests/test_agro_payment_receipt_skybox.py) | 1 |
| [test_agro_talent_bank.py](../tests/test_agro_talent_bank.py) | 4 |
| [test_checklist_embreagem_freios.py](../tests/test_checklist_embreagem_freios.py) | 4 |
| [test_csrf_security.py](../tests/test_csrf_security.py) | 8 |
| [test_css_bundle.py](../tests/test_css_bundle.py) | 3 |
| [test_denuncias_triagem.py](../tests/test_denuncias_triagem.py) | 8 |
| [test_dev_access.py](../tests/test_dev_access.py) | 12 |
| [test_dji_kml_auto_link.py](../tests/test_dji_kml_auto_link.py) | 10 |
| [test_financeiro_central.py](../tests/test_financeiro_central.py) | 34 |
| [test_historico_os_templates.py](../tests/test_historico_os_templates.py) | 1 |
| [test_operational_schedule_filters.py](../tests/test_operational_schedule_filters.py) | 13 |
| [test_painel_operacional_weather.py](../tests/test_painel_operacional_weather.py) | 3 |
| [test_portal_cidadao_denuncias.py](../tests/test_portal_cidadao_denuncias.py) | 12 |
| [test_portal_cidadao_health_data.py](../tests/test_portal_cidadao_health_data.py) | 9 |
| [test_redirects.py](../tests/test_redirects.py) | 4 |
| [test_relatorios_region_team_filters.py](../tests/test_relatorios_region_team_filters.py) | 5 |
| [test_relatorios_retornos_automaticos.py](../tests/test_relatorios_retornos_automaticos.py) | 11 |
| [test_retorno_ciclo.py](../tests/test_retorno_ciclo.py) | 1 |
| [test_retorno_ciclo_prefeitura_scope.py](../tests/test_retorno_ciclo_prefeitura_scope.py) | 2 |
| [test_security_controls.py](../tests/test_security_controls.py) | 34 |
| [test_skybox_upload.py](../tests/test_skybox_upload.py) | 3 |
| [test_solicitacao_place_id_block.py](../tests/test_solicitacao_place_id_block.py) | 14 |
| [test_supervisor_veiculos.py](../tests/test_supervisor_veiculos.py) | 23 |
| [test_uvis_os_media_access.py](../tests/test_uvis_os_media_access.py) | 8 |
| [test_veiculos_operational_scope.py](../tests/test_veiculos_operational_scope.py) | 39 |
| [test_veiculos_rastreamento.py](../tests/test_veiculos_rastreamento.py) | 9 |
| [test_vigilancia_preview.py](../tests/test_vigilancia_preview.py) | 32 |
| [test_vigilancia_routes.py](../tests/test_vigilancia_routes.py) | 23 |
