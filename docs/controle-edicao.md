# Controle de edição simultânea

Controle relacionado ao item 4.5.3 da auditoria CONDOMAR, com exceção operacional para pilotos e equipes. A reserva fica no banco e é compartilhada entre processos do sistema. A autorização municipal, regional, por equipe e por perfil continua obrigatória; possuir uma reserva não concede acesso a um registro.

## Edição direta para pilotos e equipes

Os perfis `piloto`, `equipe_oceano`, `equipe_uvis` e `piloto_agro` estão dispensados da reserva e da conferência do ticket da página. Os formulários abrem diretamente para edição, quando as permissões existentes permitem. Reservas antigas ou de outros usuários não bloqueiam suas gravações nem seus uploads. Fotos e vídeos seguem a mesma dispensa, incluindo o processamento de vídeo em segundo plano, que continua restrito aos campos de vídeo da OS.

Essa dispensa não concede acesso a outra prefeitura, equipe ou OS encerrada, nem remove o histórico de alterações. Os demais perfis continuam sujeitos à reserva. O versionamento do banco permanece: uma gravação realmente simultânea com um objeto já carregado pode ser recusada, mas não há exigência de clicar em “Iniciar edição” para esses perfis operacionais. Uma alteração feita pela equipe pode tornar desatualizada uma tela administrativa protegida.

A dispensa exige publicar o código e recarregar as páginas já abertas; não exige nova migração ou alteração de contas no banco. O guia PDF anterior descreve o fluxo original, anterior a essa exceção operacional. As regras de reserva e credenciais de mídia abaixo se aplicam aos demais perfis.

Para páginas antigas que ainda chamam `/api/edicao/reservar`, `/renovar` ou `/liberar`, os perfis dispensados recebem `required: false`, sem consultar o registro nem criar, renovar ou liberar reservas. Login e CSRF continuam exigidos; a edição real mantém as autorizações de prefeitura, equipe e estado da OS. O JavaScript atualizado restaura os campos originalmente editáveis, preserva o preenchimento e interrompe as renovações. A resposta mantém token e validade sintéticos para compatibilidade com JavaScript já carregado; esses valores não concedem acesso nem prolongam a sessão. A ação `liberar-dev` permanece vedada às equipes. Os registros históricos de conflito continuam na auditoria após a correção.

## Uso

Para os perfis que continuam protegidos, o formulário abre para consulta. **Iniciar edição** solicita uma reserva; o aviso permanece dentro do formulário. Quem consegue a reserva pode preencher e salvar. Outro usuário protegido, inclusive o mesmo login em outra aba, recebe o nome do editor responsável e continua podendo consultar.

Salvar confirma os dados e libera a reserva na mesma transação. **Cancelar edição e liberar** pede confirmação antes de descartar o preenchimento. Fechar a aba não libera imediatamente: a expiração recupera a reserva sem depender de uma chamada de saída que poderia disputar com o salvamento.

A confirmação usa uma janela do sistema com o número do registro e as ações **Continuar editando** e **Descartar alterações e liberar**. O foco inicial fica na opção de continuar. Recarregar também exige confirmação explícita; arquivos e alterações já salvos não são desfeitos. Durante a liberação, a janela mostra progresso. Uma falha de conexão ou autorização mantém os campos e mostra o erro, sem recarregar automaticamente. Reserva já encerrada permite recarregar após a confirmação. Os avisos de conflito e edição pausada permanecem no formulário. Essa melhoria de interface não exige migração de banco e preserva as exceções dos perfis operacionais.

A duração padrão é de cinco minutos (`EDIT_LEASE_SECONDS=300`, mínimo 60, máximo 1800). Enquanto a aba está visível e há interação recente no formulário, ela renova a reserva a cada 20 segundos. Uma aba abandonada deixa de renovar. Perda de conexão ou expiração pausa a edição e mantém os campos na tela para cópia; é necessário recarregar e revisar antes de salvar.

Uma versão assinada identifica os dados exibidos ao abrir a tela. A conferência no servidor impede sobrescrever uma versão mais recente mesmo depois da expiração da reserva. O banco também usa versões otimistas nas solicitações, denúncias e nas duas tabelas de OS para recusar gravações concorrentes com objetos antigos em memória.

## Fluxos cobertos

- Edição completa de solicitação e decisão rápida no painel administrativo, em desktop e celular.
- Formulário de execução de OS pela administração; pilotos e equipes usam edição direta.
- Retorno automático nas telas de OS da UVIS; equipe UVIS usa edição direta.
- Encaminhamento, designação, arquivamento e conversão de denúncias.

A solicitação e suas OS compartilham uma reserva, pois representam o mesmo atendimento. Denúncias possuem reserva própria. As demais gravações ORM nesses objetos respeitam uma reserva ativa, incluindo exclusão, exceto para os perfis de edição direta. A remoção de vínculo KML usa alterações individuais para respeitar o controle e a auditoria.

Uploads diretos carregam a identificação da aba e atualizam sua versão após a própria operação. O processamento de vídeo em segundo plano só pode concluir durante uma reserva ativa se ela pertencer ao editor que iniciou o envio. Essa autorização é restrita aos campos de vídeo; não autoriza alterações no formulário. O retorno do processamento só atualiza a versão da aba se o estado anterior e o posterior coincidirem exatamente com a transição do vídeo. Uma liberação pelo DEV seguida de nova reserva impede um trabalho antigo de sobrescrever a mídia do novo editor.

## Liberação pelo DEV e auditoria

Ao encontrar uma reserva ocupada, o DEV pode abrir **DEV: liberar a reserva de outro editor**, preencher um motivo de 10 a 300 caracteres e confirmar. A liberação invalida o token anterior; o DEV deve recarregar e reservar normalmente antes de editar.

A trilha registra `EDICAO_RESERVADA`, `EDICAO_LIBERADA`, `EDICAO_LIBERADA_DEV` e `CONFLITO_EDICAO`, além das alterações de negócio já auditadas. A liberação administrativa inclui responsável, motivo e identificador do editor anterior. Tokens não entram na trilha. Renovações periódicas não geram um evento por chamada. O arquivamento no Skybox segue a fila de auditoria existente.

## Implantação e limites

Aplicar a migração `b7f2c9d41e60`, após `a6e3f8129c40`, antes de iniciar a nova versão. Ela cria `edicao_reservas` e adiciona `versao_edicao`, com valor inicial 1, às quatro tabelas existentes. Não redistribui dados municipais nem altera conteúdos de negócio. Reiniciar todos os processos evita manter uma versão antiga do aplicativo gravando sem o controle novo.

A cobertura acima não significa que todos os cadastros do sistema, como financeiro, Agro e estoque, já tenham reserva de edição. Escritas SQL diretas e alterações em lote externas ao ORM não herdam a proteção: novas rotas precisam aplicar a mesma autorização, reserva e versionamento. Os caminhos existentes do escopo foram revisados; não se deve usar SQL direto para contorná-los.

O controle protege a gravação no banco. Não transforma banco e Skybox numa única transação distribuída nem substitui a etapa de compensação de arquivos externos sob falhas, apontada no item 4.5.6.

## Validação

Os testes de `tests/test_edit_control.py` usam bancos descartáveis e exercitam dois editores, duas abas, expiração, liberação DEV, falsificação/troca de ticket, mudança de permissão, isolamento municipal, acesso somente para consulta, versões antigas, concorrência entre sessões, rollback de validação, processamento de vídeo e migração reversível.

Para homologar visualmente: abrir a mesma OS com dois usuários autorizados; reservar com o primeiro; conferir o aviso persistente no segundo; salvar; tentar editar usando a tela antiga; recarregar; reservar e cancelar; repetir com liberação DEV. Testar também um usuário de outra prefeitura, que não deve receber acesso nem informações do editor do registro protegido.
