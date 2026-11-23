# Parceiros e oportunidades — IJA Fly

Na pesquisa de cooperativas e lojas, selecione as unidades ao final da resposta e use **Salvar selecionados no sistema**. Cada candidato entra como **A abordar**, com cidade, telefone, oportunidade, culturas, abordagem sugerida e fontes públicas. A pesquisa não salva cadastros automaticamente. Unidades já cadastradas pelo mesmo nome e cidade preservam seu acompanhamento.

Em **Agro → Clientes e Fornecedores → Parceiros e oportunidades**, abra **Acompanhar** para registrar responsável, situação, próximo contato e anotações. Marcar contato realizado ou mudar para Contatado registra a data. O histórico identifica o usuário e o horário; nenhum contato é enviado automaticamente. Retorno agendado exige uma data. Edições concorrentes são recusadas para evitar sobrescrita.

Use os filtros de texto, situação e retornos até hoje. **Exportar seleção para Excel** inclui todos os resultados filtrados, inclusive outras páginas, até 5.000 registros. A pesquisa também permite baixar apenas os candidatos selecionados sem cadastrá-los. Telefones ficam como texto e conteúdo externo não vira fórmula no Excel.

As rotas reutilizam as permissões de consultar, criar e editar clientes do Agro e o escopo de prefeitura existente. A seleção da pesquisa é assinada, vinculada ao usuário e sessão, e expira após 24 horas. Após esse prazo, faça outra pesquisa para salvar ou exportar candidatos ainda não cadastrados.

A trava de duplicidade compara nome/cidade e todos os números reconhecidos nos campos telefone e WhatsApp, inclusive entre campos diferentes, normalizando espaços, pontuação e prefixo +55. Um número compartilhado por filiais também bloqueia um novo cadastro no mesmo escopo, mesmo com outro nome ou cidade. Campos vazios ou “não confirmado” não são identificadores. Importação e cadastro manual preservam o cadastro existente; edições que reutilizam outro contato são recusadas. No PostgreSQL, uma trava transacional por escopo serializa gravações simultâneas. Cadastros antigos não são apagados ou mesclados automaticamente.

O botão **WhatsApp** na lista e na ficha abre o número comercial com uma apresentação da IJA Drones preenchida, para revisão e edição antes do envio manual. A ficha também mostra uma prévia do texto. O campo WhatsApp tem preferência; se estiver ausente, **Tentar WhatsApp** usa o telefone comercial e informa que a disponibilidade não foi confirmada. Números ausentes ou ambíguos não geram links. Abrir o link não registra contato realizado nem altera a situação. Implementação pelo [recurso oficial clique para conversa](https://faq.whatsapp.com/5913398998672934).

## Publicação

A migração `d8a7f519c203`, após `c9e4a7120b65`, cria somente `parceiros_agro` e `parceiros_agro_historico` e seus índices. Não altera cadastros existentes. Antes da publicação, houve backup completo em formato custom do PostgreSQL 18 e ensaio de upgrade/downgrade em schema isolado descartável no PostgreSQL 18. O código anterior aceita as novas tabelas; rollback de código não exige apagá-las. Não executar downgrade após cadastros reais, pois ele remove os parceiros e seu histórico.

Testes cobrem importação e duplicidades, fontes, contato e histórico, escopo de acesso, revogação de permissão, CSRF, seleção adulterada, edição concorrente e conteúdo do XLSX. Os testes de interface verificam que salvar exige clique e respeita as unidades selecionadas.
