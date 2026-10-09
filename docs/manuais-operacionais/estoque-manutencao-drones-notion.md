# Estoque e Manutencao de Drones

## Visao geral

Foi implementado um novo fluxo no IJA System para controlar **estoque de pecas**, **pecas usadas em manutencoes**, **historico de manutencoes** e **PDF de manutencao**.

A funcionalidade foi criada para resolver o fluxo operacional abaixo:

1. Cadastrar pecas no estoque.
2. Vincular uma peca a um drone, quando fizer sentido.
3. Enviar um drone para manutencao.
4. Registrar quais pecas foram usadas nessa manutencao.
5. Dar baixa automatica no estoque.
6. Encerrar a manutencao e devolver o drone para o status **Ativo**.
7. Consultar historico de manutencoes e historico de pecas usadas.
8. Gerar PDF da manutencao com logo, rodape e detalhamento das pecas utilizadas.

O objetivo e criar rastreabilidade do ciclo completo: **estoque -> manutencao -> baixa -> historico -> PDF**.

---

## Perfis de acesso

### Estoque

O menu **Estoque** fica disponivel apenas para:

- **dev**
- **diretor**

### Manutencao

As telas de manutencao seguem a permissao ja usada no modulo de equipamentos:

- **dev**
- **diretor**
- **admin**
- **operario**
- **operador**
- **prefeitura_admin**

Essa regra foi mantida para respeitar o comportamento existente do modulo de equipamentos.

---

## Onde acessar

### Estoque

Menu lateral:

**Estoque**

Rotas:

- `/estoque`
- `/estoque/novo`
- `/estoque/<id>/editar`
- `/estoque/<id>/deletar`

### Equipamentos em manutencao

Menu/tela:

**Equipamentos > Em Manutencao**

Rota:

- `/equipamentos/em-manutencao`

### Registro de pecas usadas

Na tela **Equipamentos em Manutencao**, cada drone em manutencao exibe o botao:

**Pecas usadas**

Rota:

- `/equipamentos/<drone_id>/manutencao/pecas`

### Historico de manutencoes

Na tela **Equipamentos em Manutencao**, existe o botao:

**Historico**

Rota:

- `/equipamentos/manutencoes/historico`

### Historico de pecas usadas

Na tela **Equipamentos em Manutencao**, existe o botao:

**Pecas**

Rota:

- `/equipamentos/manutencoes/pecas/historico`

### PDF da manutencao

O PDF pode ser gerado:

- na manutencao aberta;
- no historico de uma manutencao ja encerrada;
- no detalhe de uma manutencao.

Rotas:

- `/equipamentos/<drone_id>/manutencao/pdf`
- `/equipamentos/manutencoes/<manutencao_id>/pdf`

---

## Fluxo operacional completo

## 1. Cadastro de pecas no estoque

O usuario com perfil **dev** ou **diretor** acessa o menu **Estoque**.

Na tela de estoque, e possivel:

- visualizar pecas cadastradas;
- cadastrar nova peca;
- editar peca existente;
- remover peca;
- vincular peca a um drone;
- acompanhar quantidade disponivel;
- acompanhar status da peca.

Campos principais:

- **Modelo da peca**
- **Numero de serie**
- **Quantidade**
- **Drone do qual faz parte**
- **Status**
- **Observacoes**

### Status das pecas

Os status utilizados no estoque sao:

- **Disponivel para manutencao**
- **Reservada**
- **Baixada**
- **Indisponivel**

O status mais importante para o fluxo de manutencao e:

**Disponivel para manutencao**

Somente pecas com esse status e quantidade maior que zero aparecem no formulario de pecas usadas.

---

## 2. Enviar drone para manutencao

Na listagem de drones, o usuario pode enviar um drone para manutencao.

Quando isso acontece:

- o status do drone muda para **Em Manutencao**;
- a data de ultima manutencao e atualizada;
- o sistema cria um registro aberto na tabela de historico de manutencoes.

Esse registro aberto representa a manutencao atual do drone.

### Regra importante

Se o drone ja estiver em manutencao, o sistema nao cria uma nova manutencao duplicada.

---

## 3. Registrar pecas usadas na manutencao

Na tela:

**Equipamentos em Manutencao**

Cada drone em manutencao exibe o botao:

**Pecas usadas**

Ao clicar, o sistema abre um formulario com:

- dados do drone;
- pecas disponiveis vinculadas ao drone;
- quantidade disponivel;
- campo de quantidade usada;
- campo de observacoes da manutencao;
- historico das pecas ja registradas naquela manutencao.

### Regras para exibicao das pecas

Uma peca aparece no formulario somente quando:

- esta vinculada ao drone em manutencao;
- esta com status **Disponivel para manutencao**;
- possui quantidade maior que zero.

### Regras ao salvar

Ao registrar uma ou mais pecas usadas:

1. O sistema valida se a peca pertence ao drone.
2. O sistema valida se a peca esta disponivel para manutencao.
3. O sistema valida se a quantidade usada e maior que zero.
4. O sistema valida se a quantidade usada nao ultrapassa o estoque disponivel.
5. O sistema cria registros em **manutencao_pecas_usadas**.
6. O sistema vincula esses registros a manutencao aberta.
7. O sistema reduz a quantidade da peca no estoque.
8. Se a quantidade chegar a zero, a peca recebe status **Baixada**.

---

## 4. Encerrar manutencao

Na tela:

**Equipamentos em Manutencao**

Cada drone em manutencao exibe o botao:

**Encerrar**

Ao encerrar:

- o drone volta para o status **Ativo**;
- a data de ultima manutencao e atualizada;
- a manutencao aberta muda para status **Encerrada**;
- o sistema grava data/hora de encerramento;
- o sistema grava o usuario que encerrou.

Depois disso, o drone sai da tela de equipamentos em manutencao.

---

## 5. Historico de manutencoes

O historico lista todas as manutencoes registradas na nova tabela.

Campos exibidos:

- drone;
- modelo;
- status da manutencao;
- data de abertura;
- data de encerramento;
- total de pecas usadas;
- usuario que abriu;
- usuario que encerrou;
- botao de detalhe;
- botao de PDF.

### Status da manutencao

Uma manutencao pode estar como:

- **Aberta**
- **Encerrada**

### Manutencoes antigas

Como a tabela de historico foi criada agora, manutencoes muito antigas nao aparecem automaticamente se nao havia registro estruturado delas antes.

O sistema faz um backfill apenas para drones que estavam com status **Em Manutencao** no momento da migration. Para esses drones, e criado um registro aberto.

Manutencoes antigas que ja tinham sido encerradas antes da criacao da tabela nao possuem dados suficientes para reconstruir abertura, encerramento e pecas usadas.

---

## 6. Historico de pecas usadas

A tela de historico de pecas usadas lista todas as baixas feitas em manutencoes.

Campos exibidos:

- peca;
- numero de serie da peca;
- quantidade usada;
- drone;
- manutencao vinculada;
- status da manutencao;
- usuario que registrou;
- data do registro;
- observacoes.

Essa tela serve como controle geral de consumo de pecas.

Ela ajuda a responder perguntas como:

- quais pecas foram usadas;
- em qual drone foram usadas;
- em qual manutencao foram usadas;
- quem registrou a baixa;
- quando a baixa foi feita;
- qual quantidade saiu do estoque.

---

## 7. PDF da manutencao

O PDF da manutencao foi criado com o padrao visual dos relatorios do sistema.

Ele contem:

- logo da Oceano Azul;
- titulo **Relatorio de manutencao**;
- data/hora de emissao;
- dados do drone;
- modelo;
- numero de serie;
- equipe vinculada;
- status atual do drone;
- status da manutencao;
- data/hora de abertura;
- data/hora de encerramento;
- total de itens usados;
- tabela de pecas utilizadas;
- responsavel pelo registro de cada peca;
- observacoes;
- rodape com razao social e endereco;
- numero de pagina.

O PDF pode ser gerado tanto para manutencoes abertas quanto encerradas.

### Quando usar o PDF

O PDF serve para:

- anexar em processos internos;
- comprovar o consumo de pecas;
- prestar contas sobre uma manutencao;
- guardar historico tecnico do drone;
- enviar para diretoria ou responsaveis operacionais.

---

## Regras de negocio

### Estoque

- Uma peca pode ou nao estar vinculada a um drone.
- Para aparecer no formulario de manutencao, a peca precisa estar vinculada ao drone.
- A quantidade da peca nao pode ser negativa.
- O numero de serie da peca, quando informado, deve ser unico.
- Pecas com quantidade zero sao marcadas como **Baixada** quando usadas totalmente.

### Manutencao

- Um drone em manutencao possui uma manutencao aberta.
- Ao enviar o drone para manutencao, o sistema cria uma manutencao aberta.
- Se ja existir manutencao aberta para o drone, ela e reaproveitada.
- Ao encerrar, a manutencao aberta muda para encerrada.
- Ao encerrar, o drone volta para **Ativo**.

### Pecas usadas

- Pecas usadas ficam registradas em tabela propria.
- Cada registro de peca usada guarda:
  - manutencao;
  - drone;
  - peca;
  - quantidade usada;
  - usuario que registrou;
  - data/hora;
  - observacoes.
- A baixa do estoque acontece no momento do registro da peca usada.

---

## Estrutura de banco

## Tabela: estoque_pecas

Tabela responsavel por controlar as pecas cadastradas no estoque.

Campos principais:

- `id`
- `prefeitura_id`
- `drone_id`
- `numero_serie`
- `modelo_peca`
- `quantidade`
- `status`
- `observacoes`
- `criado_em`
- `atualizado_em`

Relacionamentos:

- `prefeitura_id` -> `prefeituras.id`
- `drone_id` -> `drones.id`

## Tabela: manutencoes_equipamentos

Tabela responsavel pelo historico de manutencoes.

Campos principais:

- `id`
- `prefeitura_id`
- `drone_id`
- `aberta_por_id`
- `encerrada_por_id`
- `status`
- `aberta_em`
- `encerrada_em`
- `observacoes`

Relacionamentos:

- `prefeitura_id` -> `prefeituras.id`
- `drone_id` -> `drones.id`
- `aberta_por_id` -> `usuarios.id`
- `encerrada_por_id` -> `usuarios.id`

## Tabela: manutencao_pecas_usadas

Tabela responsavel pelo registro das pecas consumidas em manutencoes.

Campos principais:

- `id`
- `prefeitura_id`
- `manutencao_id`
- `drone_id`
- `peca_id`
- `usuario_id`
- `quantidade_usada`
- `observacoes`
- `criado_em`

Relacionamentos:

- `prefeitura_id` -> `prefeituras.id`
- `manutencao_id` -> `manutencoes_equipamentos.id`
- `drone_id` -> `drones.id`
- `peca_id` -> `estoque_pecas.id`
- `usuario_id` -> `usuarios.id`

---

## Principais arquivos alterados

### Modelos

- `app/models.py`

Models criados/adicionados:

- `EstoquePeca`
- `ManutencaoEquipamento`
- `ManutencaoPecaUso`

### Modulo de estoque

- `app/modules/estoque/__init__.py`
- `app/modules/estoque/routes.py`
- `app/modules/estoque/service.py`

Templates:

- `app/templates/estoque_listar.html`
- `app/templates/estoque_form.html`

### Modulo de equipamentos/manutencao

- `app/modules/equipamentos/routes.py`
- `app/modules/equipamentos/service.py`
- `app/modules/equipamentos/exporters.py`

Templates:

- `app/templates/equipamentos_manutencao.html`
- `app/templates/equipamento_manutencao_pecas.html`
- `app/templates/equipamentos_manutencoes_historico.html`
- `app/templates/equipamentos_manutencoes_pecas_historico.html`
- `app/templates/equipamento_manutencao_detalhe.html`

### Registro das rotas

- `app/routes.py`

### Sidebar

- `app/templates/base.html`

### Migrations

- `migrations/versions/a3f2d8c9e1b4_add_estoque_pecas.py`
- `migrations/versions/b4e7c2a9d8f1_add_manutencao_pecas_usadas.py`
- `migrations/versions/c5d8e2f7a9b3_add_historico_manutencoes.py`

---

## Rotas implementadas

## Estoque

| Metodo | Rota | Descricao |
|---|---|---|
| GET | `/estoque` | Lista pecas em estoque |
| GET/POST | `/estoque/novo` | Cadastra nova peca |
| GET/POST | `/estoque/<peca_id>/editar` | Edita uma peca |
| POST | `/estoque/<peca_id>/deletar` | Remove uma peca |

## Manutencao

| Metodo | Rota | Descricao |
|---|---|---|
| GET | `/equipamentos/em-manutencao` | Lista equipamentos em manutencao |
| POST | `/drones/<drone_id>/manutencao` | Envia drone para manutencao |
| GET/POST | `/equipamentos/<drone_id>/manutencao/pecas` | Registra pecas usadas |
| POST | `/equipamentos/<drone_id>/manutencao/encerrar` | Encerra manutencao e volta drone para Ativo |
| GET | `/equipamentos/<drone_id>/manutencao/pdf` | Gera PDF da manutencao aberta |

## Historico

| Metodo | Rota | Descricao |
|---|---|---|
| GET | `/equipamentos/manutencoes/historico` | Historico de manutencoes |
| GET | `/equipamentos/manutencoes/pecas/historico` | Historico geral de pecas usadas |
| GET | `/equipamentos/manutencoes/<manutencao_id>` | Detalhe da manutencao |
| GET | `/equipamentos/manutencoes/<manutencao_id>/pdf` | PDF de manutencao historica |

---

## Exemplos de uso

## Cenario 1: registrar uma peca no estoque

1. Acessar **Estoque**.
2. Clicar em **Nova peca**.
3. Informar:
   - modelo da peca;
   - numero de serie, se houver;
   - quantidade;
   - drone vinculado;
   - status **Disponivel para manutencao**.
4. Salvar.

Resultado esperado:

- a peca aparece na listagem de estoque;
- se estiver vinculada a um drone, pode aparecer no formulario de manutencao desse drone.

## Cenario 2: usar uma peca em manutencao

1. Enviar o drone para manutencao.
2. Acessar **Equipamentos em Manutencao**.
3. Clicar em **Pecas usadas**.
4. Selecionar uma ou mais pecas.
5. Informar quantidade usada.
6. Adicionar observacoes, se necessario.
7. Clicar em **Registrar pecas usadas**.

Resultado esperado:

- a peca aparece no historico da manutencao;
- a quantidade no estoque diminui;
- se zerar, a peca fica como **Baixada**.

## Cenario 3: encerrar manutencao

1. Acessar **Equipamentos em Manutencao**.
2. Clicar em **Encerrar**.
3. Confirmar a acao.

Resultado esperado:

- drone volta para **Ativo**;
- manutencao muda para **Encerrada**;
- historico guarda data/hora e usuario de encerramento.

## Cenario 4: gerar PDF

1. Acessar **Equipamentos em Manutencao** ou **Historico de manutencoes**.
2. Clicar em **PDF**.

Resultado esperado:

- abre um PDF com os dados da manutencao;
- o PDF contem logo, rodape e tabela de pecas usadas.

---

## Checklist de teste

## Teste de estoque

- [ ] Usuario dev visualiza o menu **Estoque**.
- [ ] Usuario diretor visualiza o menu **Estoque**.
- [ ] Usuario admin comum nao visualiza o menu **Estoque**.
- [ ] Cadastro de peca funciona.
- [ ] Edicao de peca funciona.
- [ ] Exclusao de peca funciona.
- [ ] Numero de serie duplicado e bloqueado.
- [ ] Quantidade negativa e bloqueada.

## Teste de manutencao

- [ ] Drone pode ser enviado para manutencao.
- [ ] Drone em manutencao aparece em **Equipamentos em Manutencao**.
- [ ] Botao **Pecas usadas** aparece para drones.
- [ ] Botao **PDF** aparece para drones.
- [ ] Botao **Encerrar** aparece para drones.
- [ ] Ao encerrar, drone volta para **Ativo**.
- [ ] Ao encerrar, drone sai da lista de manutencao.

## Teste de pecas usadas

- [ ] Formulario mostra somente pecas do drone.
- [ ] Formulario mostra somente pecas disponiveis.
- [ ] Quantidade usada maior que estoque e bloqueada.
- [ ] Registro de peca usada reduz estoque.
- [ ] Peca com estoque zerado vira **Baixada**.
- [ ] Registro aparece no historico da manutencao.
- [ ] Registro aparece no historico geral de pecas usadas.

## Teste de historico

- [ ] Manutencao aberta aparece no historico.
- [ ] Manutencao encerrada aparece no historico.
- [ ] Detalhe da manutencao abre corretamente.
- [ ] Total de pecas usadas aparece corretamente.
- [ ] Responsavel de abertura aparece quando disponivel.
- [ ] Responsavel de encerramento aparece quando disponivel.

## Teste de PDF

- [ ] PDF abre para manutencao aberta.
- [ ] PDF abre para manutencao encerrada.
- [ ] PDF contem logo da Oceano Azul.
- [ ] PDF contem rodape.
- [ ] PDF contem dados do drone.
- [ ] PDF contem tabela de pecas usadas.
- [ ] PDF mostra observacoes registradas.

---

## Observacoes tecnicas

### Backfill de dados

A migration `c5d8e2f7a9b3_add_historico_manutencoes.py` cria registros historicos apenas para drones que estavam em manutencao no momento da migration.

Isso significa:

- manutencoes antigas encerradas antes da criacao da tabela nao aparecem no historico;
- manutencoes novas passam a ser registradas normalmente;
- pecas usadas antigas sem manutencao vinculada podem ser associadas ao registro aberto do drone quando houver um.

### PDF

O PDF foi implementado em:

`app/modules/equipamentos/exporters.py`

Biblioteca utilizada:

`reportlab`

Padrao visual:

- logo da Oceano Azul;
- linha azul no cabecalho;
- tabela com cabecalho azul;
- rodape institucional;
- paginação.

### Escopo por prefeitura

As consultas seguem o padrao do projeto usando:

`apply_prefeitura_scope`

Isso limita os dados conforme o escopo do usuario logado quando aplicavel.

---

## Pontos futuros sugeridos

### 1. Motivo da manutencao

Adicionar campo estruturado para informar por que o drone entrou em manutencao.

Exemplos:

- queda;
- troca preventiva;
- falha de motor;
- falha de helice;
- revisao periodica;
- dano em campo;
- outro.

### 2. Custo da manutencao

Adicionar custo unitario da peca e custo total da manutencao.

### 3. Upload de anexos

Permitir anexar fotos, notas fiscais ou laudos tecnicos na manutencao.

### 4. Reabertura de manutencao

Permitir reabrir uma manutencao encerrada em caso de erro operacional.

### 5. Filtro no historico

Adicionar filtros por:

- drone;
- periodo;
- status;
- peca;
- usuario;
- equipe.

### 6. Exportacao Excel

Criar exportacao do historico de pecas usadas para conferencia de estoque.

---

## Resumo executivo

A funcionalidade cria controle completo de estoque e manutencao de drones.

Com ela, o sistema passa a registrar:

- quais pecas existem no estoque;
- quais pecas pertencem a cada drone;
- quando um drone entra em manutencao;
- quais pecas foram usadas;
- quem registrou o uso;
- quando a manutencao foi encerrada;
- qual historico de manutencoes cada drone possui;
- qual historico de consumo cada peca gerou;
- PDF final para documentacao e prestacao de contas.

Esse fluxo melhora a rastreabilidade operacional e reduz perda de informacao sobre manutencoes e baixas de estoque.
