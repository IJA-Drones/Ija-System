# Supervisor Operacional de Veículos

**IJA System — Apresentação da função e guia de uso**

**Atualizado em:** 24 de setembro de 2026

**Público:** administradores, gestores de frota e supervisores operacionais.

## 1. Apresentação da nova função

O **Supervisor Operacional de Veículos** é o perfil destinado a quem acompanha a frota e participa da rotina de campo. Com sua própria conta, o supervisor pode visualizar os veículos disponíveis para seu acesso, iniciar e encerrar turnos, registrar abastecimentos e limpezas e preencher checklists.

A administração pode atribuir um veículo ao supervisor **diretamente na listagem da frota**, selecionando o responsável e salvando a alteração. O veículo atribuído aparece identificado como **“Seu veículo”** na tela operacional e recebe prioridade na seleção do checklist.

**Texto para apresentar à equipe:**

> O IJA System passa a contar com o perfil Supervisor Operacional de Veículos. A função reúne o acompanhamento da frota e os registros da rotina de campo em uma conta própria. A atribuição do veículo pode ser feita diretamente na listagem, e o supervisor consegue registrar turnos, abastecimentos, limpezas e checklists com identificação de quem realizou cada atividade.

## 2. O que o supervisor consegue fazer

| Recurso | Como é utilizado |
| --- | --- |
| Visualização da frota | Consulta veículos, equipes responsáveis, quilometragem, status e informações de revisão. |
| Veículo sob sua responsabilidade | Visualiza seu veículo em destaque na tela operacional. Quando há outros veículos, eles aparecem em um grupo separado. |
| Organização da frota | Altera equipe e supervisor responsável pela listagem, dentro das permissões de acesso. |
| Turnos | Inicia o turno, registra a operação e encerra os turnos abertos com sua própria conta. |
| Abastecimentos | Registra tipo, KM, litros, valor e fotos do painel e da nota fiscal. |
| Limpezas | Registra realização, tipo, data, horário, valor e observações. |
| Checklist semanal | Preenche os checklists de veículos e drones disponíveis para seu acesso. |
| Histórico da frota | Consulta logs diários, abastecimentos, limpezas e mídias dos registros. |
| Rastreamento | Acessa a tela de localização e trajetos; a exibição de posições depende dos dados disponíveis na integração. |
| Operação de OS | Acessa os recursos operacionais de ordens de serviço e dosagem. Nos fluxos de execução por equipe, a referência é a equipe do veículo atribuído. |
| Alertas de limpeza | Acompanha as pendências conforme a configuração da operação Oceano Azul e as regras dos alertas. |

## 3. Como cadastrar a conta

Esta etapa deve ser feita por uma conta com permissão para gerenciar usuários administrativos.

1. Abra o cadastro de usuários e escolha a opção de novo usuário.
2. Preencha **Nome**, **Login**, **Senha** e a confirmação da senha.
3. Em **Tipo de Usuário**, selecione **Supervisor Operacional de Veículos**.
4. Selecione a **Prefeitura** da operação.
5. Configure os indicadores de atuação, como **Oceano Azul**, quando se aplicarem à pessoa e estiverem disponíveis para quem está cadastrando.
6. Salve e oriente o supervisor a acessar o sistema com a própria conta.
7. Faça a atribuição do veículo conforme a próxima seção.

**Atenção à prefeitura:** o formulário atual permite cadastrar um supervisor sem esse preenchimento. Nesse caso, algumas consultas da frota podem ter alcance mais amplo. Para uma conta que deve operar somente em um município, preencha a prefeitura e confira a associação das equipes e dos veículos.

O supervisor é atribuído **ao veículo**. Essa atribuição é feita na frota; não existe uma etapa de selecionar supervisores dentro do formulário da equipe.

## 4. Como delegar um veículo pela listagem

### Atribuição inicial

1. Acesse **Veículos → Central de Veículos → Veículos**.
2. Localize o veículo pela placa ou pelo modelo.
3. Confira a coluna **Equipe responsável**. O veículo precisa estar vinculado a uma equipe para receber um supervisor.
4. Na coluna **Supervisor responsável**, abra a lista e selecione o nome desejado.
5. Clique em **Salvar**, no final da tabela.
6. Confira a mensagem de confirmação e o nome apresentado na linha do veículo.

A escolha na lista só é gravada depois de clicar em **Salvar**. É possível ajustar várias linhas antes de salvar.

### Troca do veículo de um supervisor

Cada supervisor pode ser responsável por **um veículo por vez**.

1. No veículo atual, selecione **“-- Sem supervisor --”**.
2. No novo veículo, selecione o supervisor desejado.
3. Clique em **Salvar**.

Se os dois veículos estiverem visíveis na mesma listagem, as duas alterações podem ser salvas juntas. Se um deles estiver fora do filtro atual, remova e salve a atribuição antiga antes de fazer a nova.

A equipe do veículo é mantida quando apenas o supervisor é alterado. A atribuição exige compatibilidade entre a prefeitura do supervisor e a da equipe, quando ambas estão definidas.

### Remoção da responsabilidade

Selecione **“-- Sem supervisor --”** e clique em **Salvar**. Isso remove a atribuição direta. O supervisor ainda pode visualizar outros veículos permitidos pelo seu escopo de acesso.

Ao retirar a equipe de um veículo, a atribuição de supervisor também é removida.

## 5. Como usar no dia a dia

### 5.1. Encontrar o veículo

1. Entre no sistema com a conta do supervisor.
2. Use **Abrir Turno** para acessar a tela operacional de **Gestão de Frota**.
3. Localize a placa e a identificação **“Seu veículo”**.
4. Confira o status, a quilometragem e a situação do turno antes de iniciar a atividade.

O supervisor também pode visualizar veículos de outras equipes dentro da prefeitura configurada. A região da equipe não limita, por si só, essa visualização.

### 5.2. Iniciar o turno

1. Na linha do veículo, clique em **Iniciar Turno**.
2. Confira a quilometragem inicial, preenchida e travada pelo sistema.
3. Anexe uma **foto do painel**.
4. Faça a assinatura no campo indicado.
5. Clique em **Registrar Início**.

O KM inicial vem do último fechamento do veículo. Quando não há fechamento anterior, o sistema utiliza o KM atual cadastrado.

Se outro operador já tiver um turno aberto para o veículo, a tela informa quem está usando. Nesse caso, o supervisor acompanha a informação e deve aguardar o encerramento daquele turno para iniciar outro.

### 5.3. Registrar um abastecimento

Com um turno próprio aberto:

1. Clique em **Abastecimento**.
2. Selecione o tipo: **Veículo** ou **Gerador**.
3. Informe o **KM no Abastecimento**, a quantidade de **Litros** e o **Valor Total**.
4. Anexe a **Foto do Painel no Abastecimento**.
5. Anexe a **Foto da Nota Fiscal**.
6. Clique em **Salvar Abastecimento**.

Cada lançamento fica registrado separadamente dentro do turno.

#### Regra dos 500 km

Para o tipo **Veículo**, o KM informado pode ficar **até 500 km acima do último abastecimento do mesmo veículo**.

| Último abastecimento | Novo KM informado | Resultado quanto à trava |
| --- | --- | --- |
| 10.000 km | 10.300 km | Permitido. |
| 10.000 km | 10.500 km | Permitido: diferença exata de 500 km. |
| 10.000 km | 10.500,01 km | Bloqueado: diferença acima de 500 km. |

A referência considera o histórico do veículo, inclusive abastecimentos de turnos anteriores. Abrir outro turno não reinicia esse limite.

Quando o veículo ainda não possui abastecimento do tipo Veículo, a referência é o **KM inicial do turno**. Abastecimentos do tipo **Gerador** não recebem essa trava e não alteram a referência usada para os abastecimentos do veículo.

O limite aparece no formulário. Se o sistema bloquear o lançamento, confira o painel e o histórico. Caso exista um registro anterior incorreto, solicite a conferência do responsável pela gestão; registre sempre o tipo e o KM reais.

### 5.4. Registrar uma limpeza

1. No turno próprio aberto, clique em **Limpeza**.
2. Informe a data e o horário em que a limpeza ocorreu.
3. Marque se ela foi **Realizada** ou **Não realizada**.
4. Selecione **Completa** ou **Apenas ducha**.
5. Informe o valor e, se necessário, as observações.
6. Clique em **Salvar Limpeza**.

A data e a hora de inclusão do registro são geradas automaticamente pelo sistema. Elas são separadas da data e da hora da limpeza informadas pelo usuário.

Para a operação Oceano Azul, os alertas dependem dos indicadores configurados para usuários e equipes. O fluxo de alertas está detalhado no [manual de alertas de limpeza](manuais-operacionais/alertas-limpeza-veiculos-oceano-azul-notion.md).

### 5.5. Preencher o checklist semanal

1. Acesse **Checklist Semanal** no menu operacional.
2. Confira o veículo selecionado. O sistema prioriza o veículo atribuído ao supervisor.
3. Selecione o drone quando aplicável ao formulário.
4. Preencha os itens de inspeção, observações e assinatura solicitados.
5. Salve o checklist.

Os registros identificam o supervisor que realizou a atividade. A atribuição do veículo não substitui a inspeção nem o preenchimento dos campos.

### 5.6. Encerrar o turno

1. Clique em **Finalizar Turno**.
2. Informe a **Quilometragem Final** exibida no painel.
3. Preencha a quantidade de **Fazendas/Endereços Atendidos**.
4. Registre as observações do dia, se houver.
5. Anexe a **Foto do Painel no Fechamento**.
6. Clique em **Encerrar Turno**.

O KM final deve ser igual ou maior que o KM inicial e que os KMs dos abastecimentos registrados no turno. A trava de 500 km descrita acima pertence ao cadastro de abastecimento; o encerramento do turno não tem esse limite de distância.

### 5.7. Consultar os registros

Na **Central de Veículos**, use **Logs Diários** para acompanhar os turnos e seus abastecimentos e **Logs de Limpezas** para consultar as limpezas. Confira placa, período, operador, quilometragem e anexos para localizar a atividade desejada.

## 6. Relação entre supervisor, veículo e equipe

| Elemento | Papel no funcionamento |
| --- | --- |
| Conta do supervisor | Identifica a pessoa responsável pelos registros. |
| Veículo atribuído | Define a responsabilidade direta e o destaque na tela operacional. |
| Equipe do veículo | Fornece o contexto de equipe utilizado pelos fluxos operacionais de OS do supervisor. |
| Prefeitura | Delimita as consultas que usam o escopo municipal, quando configurada na conta. |

O supervisor não precisa ser incluído manualmente como piloto titular da equipe para receber um veículo. O sistema prepara sua identificação operacional para registrar a autoria das atividades.

A equipe pode existir sem piloto titular. Para os fluxos operacionais de OS do supervisor, é necessário que seu veículo esteja atribuído e vinculado à equipe correspondente. A visualização da frota, por outro lado, pode incluir outras equipes permitidas pelo acesso.

## 7. Dúvidas frequentes

**Posso delegar sem abrir a edição do veículo?**

Sim. Selecione o responsável na coluna **Supervisor responsável** da listagem e clique em **Salvar**.

**O supervisor pode ter dois veículos atribuídos ao mesmo tempo?**

Não. Remova a atribuição anterior para transferi-lo para outro veículo.

**Ele visualiza somente o próprio veículo?**

Não. O próprio veículo aparece identificado, e os demais veículos permitidos pelo acesso continuam disponíveis para acompanhamento.

**A retirada do supervisor apaga os registros anteriores?**

Não. A alteração da responsabilidade não exclui turnos, abastecimentos, limpezas ou checklists já registrados.

**Por que aparece “Turno em andamento por…”?**

O veículo está com um turno aberto por outro operador. O supervisor visualiza essa situação; as ações de abastecer, limpar e encerrar pelo fluxo operacional se aplicam aos turnos da própria conta.

**O nome do supervisor não aparece para seleção. O que conferir?**

Confira o tipo da conta, a prefeitura configurada e as permissões de quem está fazendo a atribuição.

**O sistema pede equipe antes de atribuir o supervisor. O que fazer?**

Selecione a **Equipe responsável** do veículo e depois o supervisor. As duas escolhas podem ser salvas pela listagem.

**A tela de rastreamento garante que o GPS está conectado?**

Não. A tela depende da integração e das posições disponíveis. Consulte o estado apresentado pelo sistema antes de considerar a localização atualizada.

## 8. Roteiro curto para demonstrar à equipe

1. Apresente o perfil **Supervisor Operacional de Veículos** no cadastro de usuários.
2. Na listagem da frota, selecione uma equipe e um supervisor para um veículo e clique em **Salvar**.
3. Acesse a conta do supervisor e mostre a identificação **“Seu veículo”**.
4. Demonstre a abertura de turno com foto do painel e assinatura.
5. Apresente os formulários de abastecimento e limpeza e explique a trava dos 500 km.
6. Mostre o checklist semanal, o fechamento do turno e a consulta dos registros.

Faça lançamentos de demonstração em um ambiente de testes, usando dados de exemplo.

## 9. Verificação desta versão

Este manual foi revisado com base no código atual do projeto. Em 24/09/2026, foram executados os testes de supervisor de veículos, escopo operacional de veículos e rastreamento: **60 testes e 2 subtestes passaram**.

Os testes incluem atribuição e transferência pela listagem, bloqueio de atribuição duplicada, visualização do veículo responsável, identificação do supervisor nos registros, rotinas da frota e a regra dos 500 km.

Essa validação foi feita localmente, com dados de teste. Ela não confirma a publicação da versão em produção nem o funcionamento das integrações externas com fotos e GPS no ambiente em uso.
