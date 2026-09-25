# Testes e manutenção

Execute as verificações a partir da raiz, com o ambiente virtual ativado. A suíte usa objetos simulados e bancos SQLite temporários nos testes de persistência. Não precisa de dados de produção, migrações ou credenciais reais.

## Comandos

```bash
DATABASE_URL=sqlite:///:memory: python -m pytest -q
node --test tests/session_security_browser.test.cjs tests/csrf_security_browser.test.cjs
python scripts/build_css_bundle.py --check
python scripts/build_docs_inventory.py --check
git diff --check
```

No PowerShell, defina `$env:DATABASE_URL = "sqlite:///:memory:"` antes de executar `python -m pytest -q`. Usar `python -m pytest` garante o interpretador do ambiente ativo. `python -m unittest discover -s tests` também coleta os testes Python atuais, mas não executa os arquivos Node.

Os arquivos `*.test.cjs` usam `node:test` e uma simulação do DOM, não um navegador real. Não exigem instalação npm e não substituem o aceite em navegador.

## Linha de base da revisão

Execução em 25/09/2026 sobre o código-base `846b12f`, no ambiente virtual existente, Python 3.14.7 e Node 24.19.0:

| Verificação | Resultado |
| --- | --- |
| Python/pytest | 229 testes e 36 subtestes passaram; 8 avisos de APIs legadas do SQLAlchemy. |
| JavaScript/Node | 25 testes passaram, sem falhas. |
| Bundle CSS | Atualizado. |
| Grafo Alembic, sem conectar banco | 125 revisões; um head `e15caed9908f`; três bases históricas. |
| Inicialização isolada | Factory com SQLite em memória, dotenv desativado e scheduler simulado: 348 rotas, 60 tabelas nos modelos, login e health checks conferidos. |

Esses resultados não medem cobertura de linhas, carga, integração real, instalação limpa ou restauração. As contagens futuras devem ser obtidas pela execução, não copiadas desta tabela.

## O que a suíte verifica

| Área | Arquivos de referência |
| --- | --- |
| Sessões, senhas, CSRF e redirects | `test_security_controls.py`, `test_csrf_security.py`, `test_redirects.py`, testes Node. |
| Escopos e operação de veículos | `test_supervisor_veiculos.py`, `test_veiculos_operational_scope.py`, `test_veiculos_rastreamento.py`, `test_checklist_embreagem_freios.py`. |
| Solicitações, retorno e relatórios | `test_solicitacao_place_id_block.py`, `test_retorno_ciclo.py`, `test_retorno_ciclo_prefeitura_scope.py`, `test_relatorios_retornos_automaticos.py`, `test_relatorios_region_team_filters.py`. |
| Agenda e clima | `test_operational_schedule_filters.py`, `test_painel_operacional_weather.py`. |
| Portal, boletim e triagem | `test_portal_cidadao_denuncias.py`, `test_portal_cidadao_health_data.py`, `test_denuncias_triagem.py`. |
| Arquivos, agro e KML | `test_skybox_upload.py`, `test_uvis_os_media_access.py`, `test_agro_payment_receipt_skybox.py`, `test_agro_talent_bank.py`, `test_dji_kml_auto_link.py`. |
| Diagnóstico e apresentação | `test_dev_access.py`, `test_css_bundle.py`. |

Todos os arquivos e suas contagens estão vinculados na [referência do código](referencia-codigo.md). Um teste pode validar apenas uma parte do fluxo; ter um arquivo com o nome da funcionalidade não comprova sua cobertura completa.

## Aceite em homologação

Após mudanças que afetem a aplicação, selecione os fluxos alterados e execute com dados fictícios:

1. Entrar pelos logins necessários; verificar redirects, vínculos obrigatórios e acesso negado com outro perfil.
2. Repetir consultas, edição, download e exportação com usuários de duas prefeituras e equipes diferentes.
3. Criar solicitação, aprovar/agendar, preencher a OS, concluir e conferir histórico/retorno quando aplicável.
4. Em mídia, conferir envio, status, download, exclusão e falha do armazenamento; para vídeo, confirmar conversão e reinício durante processamento.
5. Em frota, conferir atribuição de supervisor, abertura/fechamento, fotos, abastecimento e limite de 500 km para tipo Veículo.
6. No portal, enviar denúncia, encaminhar para coordenadoria/UVIS e convertê-la uma vez em solicitação; conferir as permissões de anexos.
7. No agro, conferir o percurso orçamento–contrato–OS e o efeito financeiro, incluindo competência e permissões de edição.
8. Com segurança/CSRF ativos, validar formulários, fetch, uploads, expiração, múltiplas abas e rejeição de token ausente.
9. Renderizar PDFs com imagens e textos longos e abrir planilhas exportadas; testes unitários não validam toda a diagramação.

Integrações reais devem usar contas de homologação. Registre versão, cenário, resultado e evidência sanitizada. Para disponibilidade e recuperação, execute o roteiro de [operação](operacao.md).

## Convenções para alterações

Mantenha entrada HTTP nas rotas, regras nos serviços e helpers reutilizáveis em `app/shared`. Preserve nomes de endpoints usados pelos templates. Alterações de schema precisam de migração revisada, com avaliação de dados existentes e downgrade. Atualize documentação e inventário quando mudar o comportamento.

Não edite `style.bundle.css` manualmente. Gere o bundle e valide que ele está sincronizado. Não inclua `.env`, dumps, uploads reais ou credenciais em casos de teste.

O único workflow encontrado nesta revisão é o watchdog do Render. Ele monitora disponibilidade; não executa a suíte em pull requests. Automatizar os comandos acima e validar migrações em PostgreSQL são pendências registradas na [revisão](revisao-documentacao-2026-09-25.md).
