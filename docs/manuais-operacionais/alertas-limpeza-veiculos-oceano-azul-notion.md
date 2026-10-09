# Alertas de Limpeza de Veiculos - Oceano Azul

## Visao geral

Foi implementado um novo fluxo de alertas para acompanhar a limpeza dos veiculos da operacao Oceano Azul.

A funcionalidade monitora a ultima limpeza registrada de cada veiculo e emite alertas quando o prazo maximo sem nova limpeza e ultrapassado.

O objetivo e dar visibilidade antecipada para as equipes em campo e, depois, permitir que a administracao acompanhe os veiculos que continuam sem registro de limpeza.

---

## Objetivo da alteracao

A limpeza dos veiculos passa a funcionar como um controle periodico semelhante ao acompanhamento de revisao.

Com isso, o sistema ajuda a responder perguntas como:

- quais veiculos estao ha muitos dias sem limpeza;
- quais equipes ou pilotos ja foram avisados;
- quem confirmou ciencia do alerta;
- quais veiculos continuam pendentes para acompanhamento administrativo;
- quais registros pertencem somente a operacao Oceano Azul.

---

## Regras de negocio

### Alerta para piloto/equipe

O piloto ou equipe da Oceano Azul recebe alerta apos **14 dias** desde a ultima limpeza registrada.

Se o veiculo nunca teve uma limpeza registrada, o sistema usa a data de cadastro do veiculo como referencia.

O alerta aparece na **Caixa de Entrada** do usuario operacional.

### Confirmacao de ciencia

Na Caixa de Entrada, o piloto ou equipe pode confirmar que viu o alerta.

Essa confirmacao fica registrada no banco com:

- usuario que confirmou;
- veiculo relacionado;
- data de referencia da limpeza;
- prazo do alerta;
- data e hora da confirmacao.

A confirmacao nao registra uma nova limpeza. Ela apenas indica que o usuario esta ciente da pendencia.

Para resolver o alerta, e necessario registrar uma nova limpeza no fluxo normal de veiculos.

### Alerta para administracao

A administracao da Oceano Azul visualiza os alertas quando o veiculo chega a **21 dias** sem nova limpeza registrada.

Na tela administrativa, alem do veiculo pendente, tambem aparece se a equipe ou piloto ja confirmou ciencia no alerta operacional de 14 dias.

### Escopo Oceano Azul

Os alertas usam a tag:

**trabalha_oceano_azul**

Essa tag existe em usuarios e equipes, e limita a funcionalidade ao pessoal da Oceano Azul.

### Exclusao da operacao Agro

O painel **Alertas de Limpeza** da administracao nao exibe veiculos da operacao **AGRO**.

O acompanhamento administrativo de limpeza ficou restrito aos veiculos da Oceano Azul.

---

## Onde acessar

### Piloto ou equipe

Na sidebar do usuario operacional da Oceano Azul:

**Caixa de Entrada**

Nessa tela aparecem os alertas de limpeza com mais de 14 dias.

### Administracao

Na sidebar administrativa:

**Alertas Limpeza**

Tambem ha um atalho dentro de:

**Central de Veiculos > Alertas**

Nessa tela aparecem os veiculos com mais de 21 dias sem limpeza, exceto veiculos da operacao Agro.

---

## Como funciona para piloto/equipe

### 1. O sistema identifica o veiculo pendente

O sistema busca os veiculos sob responsabilidade do usuario operacional.

Para usuarios do tipo equipe Oceano, o vinculo e feito pela equipe configurada no usuario.

Para pilotos, o sistema considera os veiculos ligados ao piloto ou as equipes em que ele participa.

### 2. O alerta aparece na Caixa de Entrada

Quando passam 14 dias sem nova limpeza, o veiculo aparece na Caixa de Entrada com:

- modelo e placa;
- operacao;
- equipe vinculada;
- quantidade de dias sem limpeza;
- data em que o alerta venceu;
- data da ultima limpeza, quando existir;
- indicacao de que nao ha limpeza registrada, quando for o caso.

### 3. O usuario confirma ciencia

O usuario clica em:

**Confirmar ciencia**

O sistema salva a confirmacao e o alerta passa a mostrar a data/hora em que o usuario ficou ciente.

---

## Como funciona para administracao

### 1. O sistema lista os veiculos pendentes

O painel administrativo mostra veiculos ativos com mais de 21 dias sem limpeza.

Veiculos com operacao **AGRO** nao entram nessa listagem.

### 2. A administracao acompanha a ciencia

Para cada veiculo, o painel mostra os usuarios operacionais relacionados e o status da ciencia:

- **Ciente:** quando a equipe ou piloto confirmou o alerta;
- **Nao confirmado:** quando ainda nao houve confirmacao;
- **Nenhum usuario operacional OA vinculado:** quando o veiculo nao possui usuario operacional da Oceano Azul associado.

### 3. A pendencia continua ate nova limpeza

A ciencia do alerta nao encerra a pendencia de limpeza.

O alerta deixa de aparecer somente quando uma nova limpeza real e registrada no modulo de veiculos.

---

## Exemplo de uso operacional

### Cenario

Um veiculo da equipe teste esta ha 45 dias sem registro de limpeza.

### Fluxo esperado

1. O usuario da equipe acessa a **Caixa de Entrada**.
2. O sistema mostra o alerta do veiculo.
3. A equipe confirma ciencia.
4. A administracao acessa **Alertas Limpeza**.
5. O painel mostra que a equipe ja confirmou ciencia.
6. A pendencia permanece ate que uma nova limpeza seja registrada.

---

## Registro de teste criado

Foi criado um veiculo de teste no banco remoto para validar o fluxo.

Dados:

- Equipe: `teste`
- Usuario operacional: `ploa.teste`
- Veiculo: `VEICULO TESTE ALERTA LIMPEZA`
- Placa: `TST2D21`
- ID do veiculo: `112`
- Data de referencia: `15/06/2026 12:20`
- Limpezas registradas: `0`

Resultado esperado:

- Para o usuario `ploa.teste`, o veiculo aparece na Caixa de Entrada.
- Para o usuario `admin`, o veiculo aparece em Alertas Limpeza.
- O alerta indica aproximadamente 45 dias sem limpeza na data de criacao do teste.

---

## Principais arquivos alterados

### Modelo e banco

- `app/models.py`
- `migrations/versions/b2c3d4e5f6a7_add_limpeza_veiculo_alertas_ciencia.py`

Foi criada a tabela:

`limpezas_veiculo_alertas_ciencia`

Essa tabela guarda a confirmacao de ciencia do alerta.

### Servico e rotas

- `app/modules/veiculos/service.py`
- `app/modules/veiculos/routes.py`

Foram adicionadas as regras de:

- calcular alertas operacionais com 14 dias;
- calcular alertas administrativos com 21 dias;
- confirmar ciencia;
- listar atores operacionais vinculados;
- excluir veiculos da operacao Agro no painel administrativo.

### Telas

- `app/templates/piloto_caixa_entrada.html`
- `app/templates/veiculos_alertas_limpeza.html`
- `app/templates/base.html`
- `app/templates/veiculos_menu.html`

Foram adicionados:

- item **Caixa de Entrada** na sidebar operacional;
- item **Alertas Limpeza** na sidebar administrativa;
- badge com quantidade de alertas;
- card de acesso na Central de Veiculos.

### Testes

- `tests/test_veiculos_operational_scope.py`

Foram incluidos testes para:

- alerta operacional apos 14 dias;
- confirmacao de ciencia;
- painel administrativo aos 21 dias;
- exclusao de veiculos Agro dos alertas administrativos.

---

## Validacao realizada

Foram executadas validacoes de sintaxe e testes automatizados do modulo de veiculos.

Comando usado:

```powershell
$env:PYTHONPATH='.'; python tests\test_veiculos_operational_scope.py
```

Resultado:

```text
Ran 26 tests
OK
```

Tambem foi executada compilacao Python dos arquivos alterados.

---

## Resumo executivo

O sistema agora monitora a limpeza dos veiculos da Oceano Azul com dois niveis de alerta:

- **14 dias:** alerta para piloto ou equipe confirmar ciencia;
- **21 dias:** alerta para administracao acompanhar a pendencia.

A administracao consegue ver se o operacional esta ciente, e os veiculos da operacao Agro foram removidos desse painel para manter o foco somente na Oceano Azul.

O alerta e resolvido apenas com o registro de uma nova limpeza.
