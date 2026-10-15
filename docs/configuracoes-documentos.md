# Configurações de documentos por prefeitura

**Configurações → Documentos da prefeitura** aparece no contexto Prefeitura, conforme as permissões da Central de TI. Sem uma configuração explícita na central, o acesso mantém a regra anterior de COVISA e desenvolvedor. As preferências salvas são aplicadas nas novas exportações PDF, com imagem proporcional, intensidade configurável e identificação opcional do solicitante em todas as páginas.

## Acesso e utilização

- COVISA acessa somente a prefeitura vinculada ao cadastro do usuário. O vínculo é consultado no banco por `Usuario.prefeitura_id`; nomes de região não definem o município. Também é reconhecido o perfil legado `visualizar` com região `COVISA`.
- O desenvolvedor seleciona qualquer prefeitura, inclusive inativa. Outros perfis só acessam a funcionalidade mediante autorização e continuam limitados à prefeitura do vínculo persistido da conta.
- Na Central de TI, **Documentos da prefeitura** separa **Consultar** de **Configurar**. Consultar permite abrir a tela, a imagem e o histórico; Configurar permite salvar. Tipos já configurados na central não recebem essas permissões automaticamente: o Gestor de TI deve concedê-las quando necessário. Sem autorização, a página, a imagem e o salvamento permanecem bloqueados, inclusive por URL direta.
- COVISA sem prefeitura recebe orientação para corrigir o vínculo e não pode editar configurações.
- É possível enviar, substituir ou remover a imagem, ajustar intensidade (5–30%) e largura (25–80%), habilitar a marca e escolher a identificação do usuário emissor. A configuração é compartilhada por todos os usuários da mesma prefeitura.
- Para habilitar, é necessário ter imagem ou identificação do usuário. Desabilitar preserva a imagem e as demais preferências.
- A prévia usa o usuário conectado como exemplo. Nos PDFs, a identificação contém nome e ID de quem solicitou a exportação, prefeitura e data/hora de emissão (Brasília), inclusive em trabalhos em segundo plano.
- Cada salvamento registra responsável, data, preferências anteriores e novas. A página mostra as 20 alterações mais recentes da prefeitura selecionada. Uma edição desatualizada é rejeitada para não sobrescrever o trabalho de outra pessoa.

## Imagens e armazenamento

Aceita PNG, JPEG e WebP estáticos até 5 MB, 4096 pixels por lado e 16 megapixels. O servidor verifica o conteúdo e normaliza para PNG, preserva transparência, remove metadados e limita a maior dimensão a 1600 pixels. SVG, animações e arquivos inválidos são rejeitados.

Novos uploads são armazenados exclusivamente no Skybox em `prefeituras_logo/<id>/<identificador>.png`. Sem configuração ou em caso de falha do Skybox, o envio é rejeitado e a configuração anterior é preservada; não há salvamento local alternativo. O banco guarda somente a referência do arquivo. Referências antigas, inclusive arquivos locais em `instance/documentos_marca_dagua/`, continuam legíveis para permitir a migração sem interromper as exportações. Para migrar uma imagem existente, confirme a leitura e a integridade da cópia no Skybox antes de atualizar a referência no banco ou remover a origem.

A imagem é servida somente pela rota autenticada `/configuracoes/documentos/<id>/imagem`, com autorização municipal e cache desabilitado. Arquivos substituídos são excluídos após confirmar a transação; falha no salvamento preserva a configuração anterior. Falha na limpeza do arquivo antigo é registrada no log para manutenção. O histórico não arquiva versões antigas das imagens.

## Exportações abrangidas

- Formulário individual da OS, em retrato e paisagem, e PDFs individuais no ZIP do histórico.
- Relatórios de solicitações e de OS.
- Coleta de imagens e ZIP por UVIS: a prefeitura é resolvida por registro/página, inclusive quando um desenvolvedor reúne municípios diferentes.
- Manutenção de equipamentos.
- Orçamentos, contratos, OS e relatório de contas do agro, quando vinculados a uma prefeitura.

O município vem dos registros exportados. Nas solicitações legadas sem município próprio, utiliza-se o vínculo do usuário proprietário. A prefeitura do desenvolvedor não substitui a prefeitura do documento. Nos relatórios agregados que misturam municípios ou registros sem vínculo, não se aplica o brasão de uma prefeitura ao conjunto inteiro; filtre por UVIS ou equipe para gerar um documento de escopo único. A verificação considera também os dados dos gráficos anuais, não apenas as linhas visíveis.

Documentos sem prefeitura ou com marca desabilitada continuam sem marca municipal. PDFs enviados como anexos e arquivos já emitidos não são alterados. Para refletir uma mudança nas configurações, gere uma nova exportação.

A imagem é carregada uma vez por prefeitura/exportação, tanto do armazenamento local quanto do Skybox. Se estiver habilitada e indisponível, a geração falha com mensagem em vez de entregar silenciosamente um PDF sem a marca exigida. Não há alteração dos cabeçalhos, rodapés, assinaturas ou conteúdo do documento. As respostas PDF não são armazenadas em cache compartilhado.

## Implantação

A migração `a71d9c4e203b` sucede `f2c531cc9f71` e cria `prefeitura_documento_config` e `prefeitura_documento_historico`. O `Procfile` já executa `flask --app app:create_app db upgrade` antes de iniciar o servidor. Em ambientes iniciados de outra maneira, aplique a migração antes de disponibilizar a nova página. Nenhuma migração em banco real é executada pelos testes desta funcionalidade.

Enquanto a tabela de configuração ainda não existir, as exportações continuam com o comportamento anterior, sem a nova marca municipal. As rotas de configuração retornam indisponibilidade (503) se as tabelas necessárias estiverem ausentes. Essa compatibilidade não oculta falhas de leitura do banco nem falhas de uma marca já configurada e ativa.

O downgrade remove as duas tabelas e seus dados; não apaga arquivos do armazenamento. Não há alterações nos vínculos existentes de usuários ou prefeituras. A integração com os PDFs não requer uma migração adicional.

## Verificação

`tests/test_configuracoes_documentos.py` cobre acesso por perfil, isolamento municipal, imagens protegidas, CSRF, envio/troca/remoção, histórico, conflito de edição, falhas de persistência/armazenamento e upgrade/downgrade em SQLite isolado. `tests/configuracoes_documentos_browser.test.cjs` cobre os controles de prévia e seleção de prefeitura com DOM simulado.

`tests/test_pdf_watermark.py` abre PDFs reais e verifica todas as páginas, transparência, identidade do solicitante, retrato/paisagem, escopo municipal, ZIPs e falhas de imagem.

Antes da implantação, valide o armazenamento real de homologação e o fluxo com dois municípios e usuários COVISA distintos. Os testes de Skybox usam um armazenamento simulado.
