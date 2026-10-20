# Ações realizadas

O módulo prepara divulgações de atividades municipais já realizadas e publica somente a versão expressamente revisada. O editor fica em **Vigilância → Ações realizadas** e no menu lateral. O Portal do Cidadão oferece a consulta pública em `/portal-cidadao/acoes`.

## Ativação controlada

O módulo vem desativado. A entrega do código não aplica migrações nem habilita a publicação no ambiente configurado.

1. Conferir a revisão Alembic do ambiente, o backup e a cadeia de migrações. A migração `a73e5c9b204f` sucede `f2a6d9c1074e` e adiciona somente `acoes_publicas`, `acoes_publicas_midias` e `acoes_publicas_eventos`.
2. Aplicar a migração pelo procedimento de release do ambiente.
3. Definir `ACOES_PUBLICAS_ENABLED=1` e reiniciar os processos.
4. Conferir os acessos na Central de TI. Perfis já configurados precisam receber as novas permissões explicitamente.
5. Testar uma publicação marcada como **Demonstração — dados fictícios**, incluindo consulta anônima e retirada.

Se a configuração estiver desligada ou faltar uma das tabelas, os links ficam ocultos e as rotas do módulo devolvem indisponibilidade controlada. Nenhuma tabela é criada por uma requisição.

## Preparação e revisão

Cadastre prefeitura, título, tipo, bairro ou área, período passado e descrição pública. A origem do conteúdo é escolhida na criação e permanece fixa: demonstração ou conteúdo autorizado da prefeitura. Demonstrações ficam em consulta separada (`?demo=true`) e recebem identificação também no detalhe.

Uma OS concluída oferece **Preparar divulgação**. A referência é interna; o editor aproveita município, bairro e data, sem copiar observações, endereço completo, responsável ou mídias automaticamente. As mídias da OS precisam ser escolhidas individualmente e recebem cópias próprias.

O fluxo é **Rascunho → Em revisão → Publicado → Retirado**. A revisão bloqueia edição; para corrigir, devolva ao rascunho. A publicação exige confirmação da autorização do texto e de todas as mídias selecionadas. O sistema registra conta, data, versão e retratos do conteúdo em cada alteração.

Uma publicação mantém um retrato aprovado independente do rascunho. Editar o texto, adicionar mídia ou removê-la do rascunho conserva a versão anterior no portal até nova revisão e publicação. Remover uma mídia do rascunho preserva a cópia para a versão anteriormente aprovada e para o histórico.

## Permissões e alcance

| Permissão | Efeito |
| --- | --- |
| `prefeitura.acoes_publicas.consultar` | Lista interna, editor, prévia e mídias privadas |
| `prefeitura.acoes_publicas.criar` | Criar divulgação manual ou a partir de OS acessível |
| `prefeitura.acoes_publicas.editar` | Alterar rascunho e mídias, enviar para revisão e devolver ao rascunho |
| `prefeitura.acoes_publicas.publicar` | Publicar e retirar a divulgação |

Sem configuração substitutiva da Central de TI, COVISA, administradores municipais e administradores globais têm acesso. Contas municipais exigem vínculo direto com prefeitura e só acessam seu município. A Central de TI pode separar quem prepara de quem publica; a consulta do módulo e a área Prefeitura continuam obrigatórias. Os perfis de agente de endemias e gestor de TI não operam este editor. Usar mídia de OS exige também consulta de OS e o alcance já existente sobre aquela ordem.

## Mídias e compartilhamento

Cada publicação seleciona até cinco arquivos e conserva até vinte cópias no histórico. Imagens PNG/JPG/WebP de até 10 MiB e 20 megapixels são convertidas em JPEG de até 1920 px, sem EXIF, GPS, comentários ou nomes originais. Vídeos MP4 de até 50 MiB são preparados pelo FFmpeg, conservando a primeira faixa de vídeo e a primeira de áudio, sem metadados, capítulos ou faixas de dados. O processamento tem limite de tempo e não permite protocolos de rede.

O servidor precisa do FFmpeg disponível no PATH ou em `FFMPEG_PATH`, como os demais fluxos de vídeo do sistema. Sem ele, o editor explica a indisponibilidade de vídeos e continua aceitando imagens. Não há dependência Python nova em produção.

As cópias usam o Skybox configurado ou o armazenamento local privado `upload-files/acoes-publicas`. A recuperação de arquivos existente acompanha `stored_path`. Mídias são entregues por rotas que verificam a publicação vigente, com suporte a Range para vídeos e `Cache-Control: no-store`. Não existem URLs estáticas dos originais na página pública. Falhas de armazenamento impedem a conclusão do envio; falhas posteriores na transação acionam limpeza da cópia não vinculada.

A lista pública filtra município e sobreposição do período aprovado. O detalhe oferece metadados sociais, copiar link, compartilhamento nativo quando disponível e links para WhatsApp/Facebook. O visitante inicia o compartilhamento; o sistema não envia mensagens nem publica em contas sociais.

Retirar uma publicação bloqueia imediatamente novas consultas à página e às mídias pelo sistema e mantém o histórico interno. Arquivos já baixados e prévias conservadas por plataformas externas não podem ser apagados por essa retirada.

## Verificação

Os testes `tests/test_acoes_publicas.py` cobrem o ciclo real HTTP, versões aprovadas, autorização, CSRF, concorrência por versão, isolamento municipal, cópias explícitas de OS, retirada, falha transacional, limites e remoção de EXIF. O teste de MP4 real usa `IJA_TEST_FFMPEG_PATH` e é ignorado quando esse executável de teste não é informado. `tests/test_acoes_publicas_migration.py` verifica ida e volta em SQLite descartável, igualdade com os modelos e geração offline do SQL PostgreSQL.

Validação visual deve conferir criação, editor, revisão, lista pública e detalhe em 320, 390, 430 e 1440 px, com claro/escuro, inclusive cortes internos de campos, botões, fotos, vídeo e histórico. O aceite em produção depende da ativação e da verificação do ambiente de destino.

### Validação local de 20/10/2026

- Suíte principal do módulo e regressões de permissões, contatos, auditoria, navegação e migrações: **143 testes e 524 subtestes passaram**. Os **26 testes de recuperação com PostgreSQL** foram ignorados por falta de banco local descartável; nenhum banco remoto foi usado.
- Regressões adicionais do portal e permissões de documentos: **81 testes e 14 subtestes passaram**.
- Chrome em 320, 390, 430 e 1440 px, claro/escuro: criação, editor, listagem interna, lista pública e detalhe sem transbordamento horizontal nos componentes inspecionados. Rolagem, acesso aos controles inferiores, copiar link e vídeo foram conferidos. O cabeçalho móvel e os textos de ajuda receberam ajustes locais de contraste e espaço.
- Ciclo pela interface móvel: criar, enviar MP4 sintético, revisar, autorizar, publicar, reproduzir e retirar. Após a retirada, página e vídeo retornaram 404 em sessão anônima. A demonstração usou exclusivamente SQLite e arquivos temporários fictícios.
- Migração conferida em SQLite e SQL PostgreSQL gerado offline; bundle CSS e inventário técnico verificados. Não houve migração, ativação ou deploy no ambiente real, nem teste em aparelhos físicos ou envio para redes sociais.
