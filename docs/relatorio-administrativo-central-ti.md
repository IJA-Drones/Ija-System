# Relatório administrativo - Central de TI

**Sistema:** IJA-System  
**Data:** 09 de outubro de 2026  
**Destinatários:** Gestão da empresa e Gestor de TI  
**Assunto:** Gestão de acessos e responsabilidades por tipo de usuário  
**Status:** Implementação com validação funcional. A ativação em produção não foi verificada nesta revisão.

## 1. Objetivo da mudança

A Central de TI foi criada para permitir a administração das permissões do sistema em uma única interface. O Gestor de TI poderá definir quais áreas, telas e ações cada tipo de usuário pode acessar, utilizando as funcionalidades já integradas à central.

O acesso à administração da central é reservado aos perfis **Gestor de TI** e **Dev**.

As permissões são definidas por **tipo de usuário**, como Admin Prefeitura, Piloto ou Financeiro. Ao alterar um tipo, a configuração passa a valer para todas as contas pertencentes a ele.

> **Exemplo:** ao retirar a permissão de edição de um tipo de usuário, todas as contas desse tipo deixam de poder executar essa ação. A alteração não é individual por pessoa.

## 2. Melhorias administrativas

| Aspecto | Situação anterior | Com a Central de TI |
| --- | --- | --- |
| Administração dos acessos | Mudanças nas regras dependiam de ajustes internos no sistema. | O responsável pode alterar as permissões de funcionalidades já catalogadas pela própria central. |
| Organização das regras | As regras estavam distribuídas entre telas, menus e verificações de acesso. | Uma configuração por tipo orienta a exibição das telas e a autorização das ações integradas. |
| Delegação de responsabilidades | Era mais difícil liberar consulta sem conceder operações sensíveis. | Consultar pode ser liberado separadamente de cadastrar, editar, excluir, exportar e outras ações. |
| Padronização | A manutenção dos acessos dependia da revisão das regras internas. | Todas as contas do mesmo tipo seguem a configuração definida para ele. |
| Rastreabilidade | A mudança de acesso dependia do processo de manutenção adotado. | O salvamento registra o responsável e as configurações anterior e posterior. |

### Benefícios para a empresa

- **Mais autonomia:** reduz a dependência de desenvolvimento nas alterações rotineiras de acesso já previstas no catálogo.
- **Responsabilidades mais claras:** cada tipo recebe as funções necessárias para sua atividade.
- **Controle de operações críticas:** permite liberar uma tela sem autorizar edição, exclusão ou outras ações sensíveis.
- **Padronização:** aplica a mesma regra a todas as contas do tipo selecionado.
- **Rastreabilidade:** permite identificar tecnicamente quem modificou as permissões e o que foi alterado.

## 3. Organização do sistema preservada

As áreas **Prefeitura**, **Agro** e **Financeiro** continuam separadas.

O menu lateral mantém os nomes, ícones e grupos expansíveis originais. A Central de TI determina quais opções autorizadas aparecem em cada área, sem substituir a navegação habitual por uma nova tela de acessos para os usuários comuns.

As contas continuam utilizando suas telas de trabalho. Apenas Gestor de TI e Dev precisam acessar a central para administrar as permissões.

## 4. Como o Gestor de TI utilizará a central

### Passo 1 - Selecionar o tipo de usuário correto

Antes de editar, confirme qual tipo está atribuído à conta que deverá receber a alteração.

> **Atenção:** **Admin** e **Admin Prefeitura** são tipos diferentes. Alterar um deles não modifica automaticamente o outro.

### Passo 2 - Habilitar a área necessária

Permita o acesso à área de atuação correspondente: Prefeitura, Agro, Financeiro ou Sistema.

Sem a área habilitada, as funções vinculadas a ela ficam bloqueadas.

### Passo 3 - Liberar a consulta e as ações necessárias

A opção **Consultar** habilita o acesso à tela do módulo. As demais ações exigem autorização própria, conforme as opções disponíveis para aquela funcionalidade.

Exemplos de ações: cadastrar, editar, excluir, exportar, aprovar e concluir.

- Ao marcar uma ação, a central também inclui **Consultar** para aquele módulo.
- Ao retirar **Consultar**, as ações do módulo também são removidas.
- Liberar consulta não concede automaticamente todas as operações.

### Passo 4 - Revisar a configuração completa

Confira as opções marcadas e todos os tipos que ficaram com alterações pendentes.

O salvamento considera a **seleção completa** de cada tipo alterado. Não é apenas uma adição às permissões anteriores.

### Passo 5 - Salvar e confirmar

Clique em **Salvar alterações** e confirme no alerta apresentado pelo sistema.

Todos os tipos com alterações pendentes são gravados juntos. Se outra pessoa tiver modificado a mesma configuração durante a edição, o sistema impede a sobrescrita desatualizada. Nesse caso, recarregue a central e revise antes de salvar novamente.

### Passo 6 - Conferir o resultado

Teste uma conta pertencente ao tipo alterado, verificando as telas disponíveis e as ações permitidas.

As regras passam a valer nas **próximas requisições**, inclusive para pessoas que já estão conectadas. Recarregar a página atualiza os menus e botões. Não é necessário sair e entrar novamente.

## 5. Exemplos práticos

| Configuração | Comportamento esperado |
| --- | --- |
| Estoque com somente Consultar | Permite visualizar os itens, sem cadastrar, editar ou excluir. |
| Relatórios com Consultar, sem Exportar | Permite acessar os relatórios; a exportação continua bloqueada. |
| Relatórios sem Consultar | Retira a opção do menu e bloqueia o acesso direto à tela. |
| Área desabilitada | Bloqueia o acesso às funções vinculadas àquela área. |
| Mapas e agenda com Consultar | Libera as telas integradas desse conjunto. Mapas, Agenda e Geolocalização compartilham o mesmo módulo de permissão nesta etapa. |

> **Mapas e agenda:** atualmente, a central não oferece controle independente de consulta para cada uma dessas telas. A seleção é aplicada ao conjunto integrado.

## 6. Controles de segurança e governança

### Autorização no servidor

O sistema verifica as permissões das rotas e ações integradas, além de controlar a apresentação dos menus e botões.

Tentar abrir uma tela diretamente pela URL ou enviar uma chamada manual não substitui a autorização exigida.

### Administração restrita

Somente Gestor de TI e Dev administram a central. Para esses perfis, o acesso à própria central é preservado mesmo quando suas demais funções são retiradas.

### Salvamento protegido

A central valida os dados enviados e possui proteção contra **CSRF** no salvamento. Esse controle ajuda a impedir que outra página provoque uma alteração de permissões usando a sessão do administrador.

A gravação ocorre em conjunto: o lote não deve ser salvo parcialmente.

### Registro das alterações

O salvamento registra tecnicamente:

- Responsável pela alteração.
- Data e hora.
- Configuração anterior.
- Configuração posterior.
- Versão da configuração.
- Identificação do lote de alterações.

Esse registro dá suporte à rastreabilidade. A existência do registro técnico não implica a disponibilidade de uma tela própria para consultá-lo nesta etapa.

### Proteção contra edições simultâneas

Uma edição desatualizada é rejeitada para evitar que um administrador sobrescreva, sem perceber, alterações realizadas por outro.

## 7. Regras mantidas e pontos de atenção

### Vínculos e limites de acesso aos dados

Permanecem em vigor os vínculos e filtros existentes de prefeitura, região, equipe, empresa e propriedade dos registros.

Liberar uma função não altera o tipo da conta nem garante acesso a todos os dados do sistema. Uma tela autorizada pode continuar sem apresentar registros quando a conta não possui o vínculo necessário.

### Tipos ainda sem configuração própria

Tipos sem configuração própria mantêm as regras anteriores. Depois de salvar uma configuração na central, passa a valer o conjunto selecionado para aquele tipo.

> **Atenção:** salvar um tipo sem permissões bloqueia suas funções de negócio. Isso não equivale a deixá-lo sem configuração.

### Alcance das alterações

Uma mudança afeta todas as contas do mesmo tipo. Retirar permissões pode interromper atividades de várias pessoas, por isso o conjunto deve ser revisado antes da confirmação.

A revogação é verificada em novas requisições. Ela não cancela automaticamente um processamento já iniciado e não remove informações que o usuário já visualizou ou baixou.

### Limites desta etapa

- A central administra funcionalidades já integradas ao catálogo.
- Novas telas, rotas ou operações ainda precisam de desenvolvimento e associação às permissões.
- Não foi criado um sistema de exceções individuais por pessoa.
- Esta mudança não cria um novo isolamento de dados por CNPJ.
- Os controles de acesso devem integrar os demais cuidados e avaliações de segurança do sistema.

## 8. Validação realizada

A validação anterior incluiu testes automatizados de permissões e navegação.

Na conferência funcional, foi confirmado o comportamento de **Agenda habilitada** e **Relatórios desabilitado** para **Admin Prefeitura**, com a navegação original preservada.

Este relatório descreve a implementação e a validação funcional realizadas. **A ativação em produção não foi verificada nesta revisão.** A disponibilização no ambiente real e a configuração de cada tipo devem ser conferidas antes do uso pela equipe.

## 9. Checklist recomendado ao Gestor de TI

- [ ] Confirmar o tipo real das contas que serão afetadas.
- [ ] Verificar as responsabilidades desse tipo com a área responsável.
- [ ] Habilitar somente as áreas necessárias.
- [ ] Separar permissão de consulta das ações críticas.
- [ ] Revisar a seleção completa de cada tipo alterado.
- [ ] Conferir todos os tipos com alterações pendentes antes de salvar.
- [ ] Salvar e confirmar a alteração.
- [ ] Recarregar e testar uma conta representativa do tipo.
- [ ] Conferir o acesso às telas autorizadas.
- [ ] Conferir o bloqueio das ações não autorizadas.
- [ ] Comunicar mudanças relevantes aos responsáveis pela operação.
- [ ] Revisar periodicamente as permissões com as áreas da empresa.

## 10. Orientação administrativa

O Gestor de TI deve conceder somente as permissões necessárias para cada responsabilidade. Operações sensíveis, como exclusão, aprovação, exportação e edição, devem ser avaliadas separadamente do acesso de consulta.

A Central de TI oferece uma forma mais organizada de administrar os acessos existentes. Seu uso deve ser acompanhado da definição de responsabilidades pela empresa, da revisão das concessões e da validação do comportamento após mudanças relevantes.
