# Documentação da funcionalidade: visualização do retorno automático

## Objetivo

Melhorar a compreensão do fluxo de retornos automáticos nas ordens de serviço, permitindo que usuários administrativos, UVIS e pilotos visualizem de forma clara como uma OS inicial, um retorno automático e as etapas subsequentes se relacionam.

## O que foi melhorado

A funcionalidade passou a exibir uma visão mais completa e organizada do ciclo de retorno, incluindo:

- uma linha do tempo com as etapas relacionadas à OS;
- identificação visual de quando a OS é um retorno automático;
- destaque para OSs que geraram retorno;
- resumo rápido no histórico com contexto do ciclo;
- filtros para localizar rapidamente registros de retorno automático;
- detalhes operacionais, como status, agendamento, execução, situação, larva e mídias vinculadas.

## Como funciona

Quando uma OS participa de um ciclo de retorno, o sistema monta um contexto com:

1. a solicitação inicial;
2. os retornos gerados a partir dela;
3. os próximos registros vinculados ao mesmo ciclo;
4. os dados de execução, mídia e status de cada etapa.

Esse contexto é construído no backend e renderizado em uma interface visual para facilitar a leitura do fluxo operacional.

## Componentes principais

### Backend

O processamento da estrutura do ciclo está concentrado em:

- [app/shared/retorno_ciclo.py](../app/shared/retorno_ciclo.py)

Nesse módulo são definidos:

- o cálculo do ciclo de retorno;
- a identificação da raiz do ciclo;
- a serialização dos nós do fluxo;
- a geração do resumo exibido nas telas de histórico.

### Filtros de histórico

A filtragem de registros relacionados a retorno automático foi centralizada em:

- [app/shared/os_history_filters.py](../app/shared/os_history_filters.py)

Os filtros permitem localizar:

- somente retornos automáticos;
- OSs que geraram retorno;
- qualquer ciclo com retorno.

### Interface visual

A interface visual do ciclo está implementada em:

- [app/templates/_retorno_ciclo.html](../app/templates/_retorno_ciclo.html)
- [app/templates/_retorno_ciclo_resumo.html](../app/templates/_retorno_ciclo_resumo.html)

Esses templates exibem:

- timeline visual das etapas;
- badges com o tipo de status/relacionamento;
- métricas de retorno e mídia;
- cards com informações operacionais;
- links diretos para abrir a OS correspondente.

## Onde a funcionalidade aparece

A visualização do ciclo é utilizada nas telas de histórico e formulário de OS em diferentes perfis, como:

- dashboard operacional;
- histórico de OS do piloto;
- histórico de OS da UVIS;
- histórico administrativo;
- formulários de OS com contexto de retorno.

## Cenários cobertos

### 1. OS inicial que gerou retorno automático

A interface mostra que a OS inicial gerou uma nova etapa de retorno e indica quantos retornos foram criados.

### 2. OS que é um retorno automático

A OS recebe destaque como retorno automático, facilitando a identificação de que ela faz parte de um ciclo posterior.

### 3. Ciclo com múltiplas etapas

Quando há várias solicitações encadeadas, a tela exibe a sequência completa, incluindo status, datas, situação operacional e mídias.

## Regras de comportamento

- a visualização só é exibida quando existe um ciclo relevante para a OS;
- o acesso respeita as permissões do usuário e o escopo regional/UVIS;
- a exibição é limitada para evitar páginas excessivamente longas;
- a interface mostra mídias associadas quando disponíveis.

## Como validar manualmente

1. Abra uma OS que tenha sido marcada para retorno automático.
2. Acesse o histórico ou formulário correspondente.
3. Verifique se o bloco de ciclo de retorno aparece com:
   - o título do ciclo;
   - a quantidade de retornos;
   - os cards das etapas;
   - os badges de retorno automático e geração de retorno;
   - a lista de mídias, quando houver.

## Benefícios esperados

- melhora a rastreabilidade operacional;
- reduz a ambiguidade sobre o relacionamento entre as OSs;
- facilita a conferência de retorno automático em campo;
- torna o histórico mais legível para equipes administrativas e operacionais.
