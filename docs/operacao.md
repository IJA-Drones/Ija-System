# Implantação, diagnóstico e recuperação

Guia baseado no código revisado em 25/09/2026. Descreve procedimentos e limitações observados no repositório; os recursos externos e o banco de produção não foram acessados nesta revisão.

## Publicação e migrações

O [Procfile](../Procfile) executa, nesta ordem:

1. Construção do bundle CSS.
2. `flask --app app:create_app db upgrade`.
3. Gunicorn com factory, logger próprio e parâmetros de workers, threads, timeout e reciclagem.

Uma falha na migração impede o início do Gunicorn. Não existe condição `IJA_AUTO_DB_MIGRATE` no Procfile atual. Não use `run.py` como servidor de produção. Configure HTTPS/proxy e bind do serviço conforme a infraestrutura; o Procfile não contém `--bind` explícito.

Antes de publicar uma alteração de schema:

1. Identifique o commit a publicar, a revisão Alembic aplicada e o banco de destino.
2. Confirme um backup recuperável do banco e dos arquivos referenciados.
3. Execute testes e ensaie a atualização em PostgreSQL de homologação representativo.
4. Revise operações que removem dados, bloqueiam tabelas ou exigem preenchimento de colunas.
5. Publique e confira logs de migração, `/healthz/full`, login e fluxos afetados.

Comandos de inspeção, apontados para o ambiente correto:

```bash
flask --app app:create_app db current
flask --app app:create_app db heads
flask --app app:create_app db history
```

Eles inicializam a aplicação e seu scheduler; `current` consulta o banco. Para inspecionar somente o grafo, sem carregar a factory:

```bash
python -c "from alembic.script import ScriptDirectory; s = ScriptDirectory('migrations'); print('heads:', s.get_heads()); print('bases:', s.get_bases())"
```

Na revisão: head `e15caed9908f`, 125 revisões, bases `1600d07df8f3`, `68a65e96dbfc` e `796a8641f68a`. Há bases de recuperação e merge sem operações. Um head único não comprova que o histórico completo cria uma base vazia ou que o schema existente corresponde aos modelos.

Se houver falha, preserve a mensagem, a revisão aplicada e o schema; restaure o cenário em homologação antes de corrigir. Não resolva diferenças de schema apenas com `db.create_all()` ou `db stamp head`. Um downgrade pode excluir dados e deve ser revisado; reverter somente o código não reverte o banco. Para rollback, defina previamente se o código anterior aceita o novo schema ou se será necessária restauração.

## Saúde e diagnóstico

| Sinal | O que comprova | O que não comprova |
| --- | --- | --- |
| `/healthz` → 200 e `ok` | O processo responde. | Banco, schema, integrações e execução das tarefas. |
| `/healthz/full` → JSON `status=ok` | `SELECT 1` executou. | Schema atualizado, regras e armazenamento. |
| `/healthz/full` → 503 | Erro SQL ao verificar o banco. | A causa exata; consultar o log. |
| Painel `/dev` | Diagnósticos internos para `dev`. | Monitoramento externo contínuo. |
| Evento do watchdog | Evento recebido com token válido. | Recuperação de todos os fluxos do produto. |

O logger em [gunicorn.conf.py](../gunicorn.conf.py) omite access logs de `/healthz` e `/healthz/full`; isso reduz ruído, mas também remove esses registros de acesso. O Talisman força HTTPS fora de debug, inclusive ao verificar endpoints por HTTP.

O [workflow Render Watchdog](../.github/workflows/render-watchdog.yml) está configurado para rodar a cada dez minutos e por disparo manual. O [script](../scripts/render_watchdog.py) verifica disponibilidade, pode chamar o deploy hook e tenta registrar o evento de recuperação. O destino padrão do workflow usa `/healthz`; uma falha apenas no banco pode não disparar recuperação. Variáveis, segredo e comportamento de tentativas estão em [configuração](configuracao.md).

## Backup implementado e suas limitações

[backup/service.py](../app/modules/backup/service.py) chama `pg_dump --format=plain --no-owner --no-privileges`, grava em `app/backup/`, comprime em `.sql.gz` e tenta enviar para `/backups` no Dropbox. Após envio bem-sucedido, apaga as cópias locais SQL e gzip.

O scheduler é iniciado no registro do blueprint e agenda às **05:00 em America/Sao_Paulo**. A proteção `_scheduler_started` existe apenas no processo. Com vários workers ou instâncias, não há trava distribuída que garanta uma execução única. A rota `GET /backup`, exclusiva de `dev`, já dispara um backup; não é uma consulta sem efeito.

Há uma falha de sinalização atual: se o dump for gerado mas `upload_to_dropbox()` retornar falso, `run_postgres_backup()` apenas escreve no log e retorna. `run_backup_async()` pode então informar “Enviado para Nuvem” mesmo sem confirmação do envio. Verifique a existência do arquivo no destino e sua recuperabilidade; o texto da interface não basta. O estado de progresso também é local ao worker.

Esse backup cobre **o banco**, não os arquivos de `upload-files/`, os objetos Skybox/WebDAV nem todos os arquivos de negócio guardados no Dropbox. A cópia desses armazenamentos precisa de processo próprio e de uma referência temporal compatível com o dump. A listagem Dropbox atual não percorre explicitamente todas as páginas; uma lista curta não comprova ausência de backups antigos.

## Ensaio de restauração

Este procedimento deve ser executado em um PostgreSQL **vazio, isolado e descartável**, com nome que deixe claro que é restauração de teste. Ainda não foi executado nesta revisão.

1. Selecione um `.sql.gz` confirmado no Dropbox e registre data, tamanho, hash e revisão esperada. Mantenha a cópia original.
2. Valide o gzip, extraia o SQL e examine seu início. Como o formato é SQL texto, a restauração usa `psql`, não `pg_restore`.
3. Crie um banco vazio de teste e uma conexão libpq chamada `ija_restore_test`, definida localmente para esse destino. Confira host/banco/usuário antes de executar a importação. Use arquivo de senha com acesso restrito ou prompt, sem incluir credenciais no histórico do terminal.
4. Restaure parando no primeiro erro:

```bash
gzip -t backup.sql.gz
gzip -dk backup.sql.gz
psql "service=ija_restore_test" -c 'SELECT current_database(), current_user;'
psql "service=ija_restore_test" -v ON_ERROR_STOP=1 -f backup.sql
psql "service=ija_restore_test" -c 'SELECT version_num FROM alembic_version;'
```

5. Confira tabelas, amostras de contagem e integridade de vínculos, incluindo solicitações/OS, agro e frota. Restaure ou disponibilize cópias de teste dos arquivos locais/remotos correspondentes.
6. Inicie o código compatível com a revisão restaurada, usando credenciais de homologação, e confira login, consulta, uma OS, uma exportação e anexos. Se for atualizar o código, ensaie as migrações depois de validar o restore original.
7. Registre duração total, ponto de recuperação obtido, falhas e evidências. Somente depois desse ensaio é possível definir RPO/RTO operacionais com evidência.

Não há rotina de restauração automatizada, política completa de retenção de backups nem metas de recuperação formalizadas no repositório. Esses itens permanecem no [backlog](revisao-documentacao-2026-09-25.md).

## Arquivos e trabalhos em segundo plano

Antes de reciclar workers, considere uploads e PDFs em andamento. O timeout HTTP de Gunicorn, os timeouts WebDAV, a conversão de vídeo e o limite do proxy são camadas distintas. Aumentar um deles não torna o job durável.

Jobs de vídeo usam executor e metadados locais; jobs de PDF de coleta usam dicionários/executor no processo. Há arquivos temporários e metadados em disco em partes do fluxo, mas não uma fila externa com recuperação comprovada. Reinício pode interromper trabalho e consultas em outro worker podem não encontrar o mesmo estado. Valide o arquivo remoto e a referência no banco antes de repetir uma ação interrompida. Confira também espaço em disco e permissões de escrita.

## Scripts de manutenção

Leia argumentos e destino antes de executar. Os scripts que usam `create_app()` herdam configuração e efeitos de inicialização.

| Script | Efeito e precaução operacional |
| --- | --- |
| [build_css_bundle.py](../scripts/build_css_bundle.py) | Gera bundle local; `--check` apenas verifica. |
| [build_docs_inventory.py](../scripts/build_docs_inventory.py) | Gera referência da documentação; `--check` apenas verifica, sem importar a aplicação. |
| [backfill_solicitacoes_place_id.py](../scripts/backfill_solicitacoes_place_id.py) | Simulação por padrão; `--commit` grava. Exige seleção por IDs/data; `--no-google` evita chamadas Google. Sem essa flag, até a simulação pode consultar o provedor. |
| [link_existing_kml_routes_to_os.py](../scripts/link_existing_kml_routes_to_os.py) | **Grava por padrão**. Use `--dry-run` para inspecionar; há limites/faixas e `--resolve-place-id`. |
| [report_unlinked_kml_reasons.py](../scripts/report_unlinked_kml_reasons.py) | Relatório de candidatos/motivos; consulta o banco. |
| [seed_demo_kml_os.py](../scripts/seed_demo_kml_os.py) | Cria dados de demonstração e pode ajustar schema; não usar na operação real. |
| [seed_os_for_existing_kml_routes.py](../scripts/seed_os_for_existing_kml_routes.py) | Cria/atualiza OS e cadastros a partir de rotas existentes; não é rotina comum de importação. |
| [seed_redgps_tracking_demo.py](../scripts/seed_redgps_tracking_demo.py) | Cria fixture GPS e remove linhas anteriores de demonstração; exige flag e URL de teste, além da conferência humana do destino. |
| [render_watchdog.py](../scripts/render_watchdog.py) | Consulta serviço externo e pode disparar deploy; não executar como simples teste unitário. |

## Solução de problemas

| Sintoma | Conferir primeiro |
| --- | --- |
| SQLAlchemy não inicializa | `DATABASE_URL` definida, driver instalado e destino correto. |
| Loop/redirecionamento HTTPS local | `FLASK_DEBUG` no ponto de entrada e configuração TLS/proxy. |
| Login cai entre requisições | Mesma `SECRET_KEY` em todos os workers, flags e timeout; chave aleatória muda por processo. |
| HTTP 403 após ativar CSRF | Recarregar a página, token da sessão, formulários e cabeçalhos de chamadas da mesma origem. |
| Agro não aparece | Perfil, `trabalha_agro` e vínculo ativo no caso de piloto agro. |
| Rastreamento vazio ou marcado como teste | Tabelas de posições, data da última leitura e `is_demo`; ausência de ingestão não se resolve apenas com a tela. |
| Mídia não encontrada | Escopo do usuário, referência no banco, arquivo local/remoto e credenciais do armazenamento. |
| Conversão falha | `ffmpeg`, espaço temporário, log do job, formato e timeout. |
| Exportação pesada falha | Limites de itens, imagem, concorrência por processo e disponibilidade de mídia. |
| Backup informa sucesso sem arquivo remoto | Conferir log e objeto Dropbox; considerar a falha de sinalização descrita acima. |
| Boletim sem informação | Configuração municipal, erro do provedor e fallback; não tratar indisponibilidade como zero casos. |

Para encaminhar um incidente, registre horário/fuso, versão, perfil, endpoint, status e passos para reproduzir. Remova senhas, tokens, documentos pessoais e conteúdo sensível das evidências.
