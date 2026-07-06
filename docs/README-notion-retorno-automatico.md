# Funcionalidade: Visualização do retorno automático

## Resumo

Foi implementada uma melhoria na visualização do ciclo de retorno automático das Ordens de Serviço (OS), com o objetivo de deixar o fluxo mais claro para equipes operacionais, UVIS e administração.

A nova experiência exibe a relação entre a OS inicial, os retornos gerados automaticamente e as etapas subsequentes em uma interface visual mais organizada.

## Problema identificado

Antes dessa melhoria, era difícil acompanhar de forma intuitiva:

- quando uma OS era um retorno automático;
- se uma OS havia gerado um retorno posterior;
- como o ciclo completo estava conectado;
- quais informações operacionais estavam associadas a cada etapa.

## O que foi implementado

A funcionalidade agora apresenta:

- uma linha do tempo do ciclo de retorno;
- destaque visual para OSs que são retornos automáticos;
- indicação de quando uma OS gerou outro retorno;
- resumo do ciclo no histórico;
- filtros para localizar rapidamente registros relacionados a retorno automático;
- informações operacionais como status, agendamento, execução, situação, larva e mídias.

## Benefícios

- melhora a rastreabilidade das OSs;
- reduz a ambiguidade entre visita inicial e retorno;
- facilita a conferência operacional;
- torna o histórico mais legível para diferentes perfis de usuário;
- ajuda na análise do fluxo de execução em campo.

## Arquivos principais envolvidos

- [app/shared/retorno_ciclo.py](../app/shared/retorno_ciclo.py)
- [app/shared/os_history_filters.py](../app/shared/os_history_filters.py)
- [app/templates/_retorno_ciclo.html](../app/templates/_retorno_ciclo.html)
- [app/templates/_retorno_ciclo_resumo.html](../app/templates/_retorno_ciclo_resumo.html)

## Como funciona

Quando uma OS faz parte de um ciclo de retorno, o sistema monta um contexto com as solicitações relacionadas e renderiza uma visualização que mostra:

1. a solicitação inicial;
2. os retornos gerados a partir dela;
3. as etapas subsequentes;
4. os dados operacionais de cada etapa.

## Cenários cobertos

- OS inicial que gerou retorno automático;
- OS que representa um retorno automático;
- ciclo com múltiplas etapas conectadas;
- histórico com contexto completo para análise.

## Validação manual

Para validar a funcionalidade:

1. abrir uma OS que tenha retorno automático associado;
2. acessar o histórico ou formulário da OS;
3. verificar se o bloco do ciclo de retorno aparece corretamente;
4. conferir se as etapas, badges e mídias são exibidos corretamente.

## Status

Implementado e disponível nas telas que utilizam o contexto de retorno automático.
