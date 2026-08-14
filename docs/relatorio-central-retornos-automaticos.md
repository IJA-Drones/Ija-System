# Relatório executivo e técnico: Central de Retornos Automáticos

**Data de referência:** 14 de agosto de 2026  
**Status da funcionalidade:** implementada  
**Área do sistema:** Central de Relatórios / Planejamento operacional

## 1. Resumo executivo

A Central de Retornos Automáticos foi criada para concentrar, em uma única visão gerencial, todas as solicitações que representam visitas de retorno geradas pelo sistema. A funcionalidade transforma registros que antes precisavam ser localizados individualmente em uma agenda operacional consolidada, com indicadores, filtros, agrupamento por equipe e acesso ao detalhamento de cada Ordem de Serviço (OS).

Na prática, a central permite responder rapidamente a perguntas de gestão como:

- quantos retornos automáticos existem no período analisado;
- quantas equipes possuem retornos em agenda;
- quantos retornos estão previstos para os próximos sete dias;
- quais registros estão sem fechamento no sistema;
- quais retornos estão com data vencida;
- quantos retornos já foram concluídos;
- quais PLOAs concentram maior volume de retornos;
- quais solicitações ainda não possuem equipe associada.

O principal ganho é a melhoria da capacidade de planejamento e cobrança operacional. A gestão passa a contar com uma visão única para priorizar pendências, acompanhar o cumprimento da agenda e identificar situações que exigem regularização.

## 2. Contexto e problema de negócio

O retorno automático faz parte do ciclo de atendimento das solicitações que demandam uma nova visita ou uma nova etapa de monitoramento. Embora cada retorno esteja registrado no sistema e vinculado à sua solicitação de origem, a consulta isolada das OSs não oferece, por si só, uma visão gerencial do volume e da distribuição dessas atividades.

Sem uma central dedicada, o acompanhamento depende de buscas manuais no histórico, conferência de datas e análise registro a registro. Esse processo dificulta:

- a identificação de retornos atrasados;
- a conferência de OSs que passaram da data prevista sem fechamento;
- a distribuição de demandas entre equipes;
- a visualização de retornos sem equipe;
- a análise mensal por PLOA;
- a localização de um retorno por endereço, protocolo ou identificação da OS.

A Central de Retornos Automáticos resolve esse problema ao organizar os dados em níveis complementares: visão consolidada, visão por equipe, resumo mensal e logs operacionais.

## 3. Objetivos da funcionalidade

### 3.1. Objetivo principal

Oferecer uma visão gerencial e operacional centralizada dos retornos automáticos, permitindo que os responsáveis acompanhem agenda, execução, pendências e distribuição por equipe.

### 3.2. Objetivos específicos

- consolidar todos os retornos automáticos dentro do escopo de acesso do usuário;
- evidenciar situações críticas por meio de indicadores objetivos;
- permitir análise por PLOA/equipe e por mês;
- facilitar a localização de registros com filtros combináveis;
- distinguir pendências futuras, retornos do dia, conclusões, cancelamentos e datas vencidas;
- manter acesso direto ao formulário e ao histórico da OS;
- respeitar a separação de dados entre prefeituras e regiões.

## 4. Localização e acesso no sistema

A funcionalidade é acessada pela seguinte navegação:

```text
Central de Relatórios
  -> Retornos Automáticos
  -> Central de Retornos Automáticos
```

Na Central de Relatórios existe um card específico de **Retornos Automáticos**, identificado como uma ferramenta de planejamento e com acesso à central por PLOA e à agenda geral.

A rota principal da funcionalidade é:

```text
/relatorios/retornos-automaticos
```

Também existem visões de detalhamento:

```text
/relatorios/retornos-automaticos/equipe/<equipe_id>
/relatorios/retornos-automaticos/sem-equipe
```

O acesso é autenticado e restrito aos perfis autorizados a visualizar a Central de Relatórios. A aplicação ainda impõe o escopo de prefeitura e, para usuários regionais, o escopo da região vinculada ao usuário.

## 5. Critério de entrada na central

Uma solicitação é considerada parte da Central de Retornos Automáticos quando atende a pelo menos um dos seguintes critérios:

1. foi marcada como gerada automaticamente; ou
2. possui vínculo com uma solicitação de origem por meio do campo de retorno.

Em termos de dados, a consulta considera as solicitações em que:

```text
gerada_automaticamente = verdadeiro
OU
origem_retorno_id está preenchido
```

Essa regra cobre tanto os registros explicitamente sinalizados como automáticos quanto os registros que participam do fluxo por possuírem uma OS de origem.

## 6. Visão consolidada e indicadores

A tela principal apresenta seis indicadores de acompanhamento:

| Indicador | Significado gerencial |
| --- | --- |
| Retornos | Total de retornos que atendem aos filtros aplicados. |
| Equipes com agenda | Quantidade de equipes com pelo menos um retorno no resultado atual. |
| Próximos 7 dias | Retornos agendados entre a data atual e os sete dias seguintes, incluindo o dia atual. |
| Sem fechamento | Retornos com data passada, OS existente e sem registro de fechamento. |
| Data vencida | Retornos com data passada que não foram classificados como concluídos nem como “sem fechamento”. |
| Concluídos | Retornos com status de conclusão ou com data/hora de resposta registrada na OS. |

Os indicadores são recalculados com base nos filtros ativos. Dessa forma, a gestão pode, por exemplo, analisar apenas uma região, uma PLOA, um tipo de operação ou um intervalo de datas e obter os totais específicos daquele recorte.

## 7. Classificação da situação operacional

Além do status administrativo da solicitação, a central calcula uma **situação operacional** para tornar a leitura da agenda mais objetiva.

| Situação | Regra aplicada |
| --- | --- |
| Cancelado | O status da solicitação contém indicação de cancelamento. |
| Concluído | O status indica conclusão ou a OS possui data/hora de resposta. |
| Sem data | Não existe data de agendamento. |
| Sem fechamento no sistema | A data de agendamento já passou, existe uma OS, mas ela não possui registro de resposta/fechamento. |
| Data vencida | A data de agendamento já passou e o registro não se enquadra nas classificações anteriores. |
| Hoje | O retorno está agendado para a data atual. |
| Pendente futuro | O retorno está agendado para uma data futura. |

A classificação segue uma ordem de prioridade. Um retorno cancelado, por exemplo, não é contado como vencido; da mesma forma, uma OS concluída não permanece como pendência, ainda que sua data de agendamento já tenha passado.

## 8. Filtros disponíveis

A central oferece filtros combináveis para apoiar análises específicas:

- status da solicitação;
- situação operacional;
- unidade/UVIS;
- PLOA ou equipe;
- região;
- necessidade de apoio da CET;
- tipo de visita;
- tipo de imóvel;
- tipo de operação;
- foco;
- ID, protocolo ou identificador da OS;
- endereço;
- data inicial de agendamento;
- data final de agendamento.

O campo de endereço pesquisa em logradouro, número, bairro, cidade, CEP e complemento. A busca por identificação considera o ID da solicitação atual, o ID de origem, protocolos e identificadores das OSs atual e de origem.

Quando as duas datas são informadas em ordem invertida, o sistema normaliza o intervalo antes de executar a consulta. Quando nenhuma data é informada, a central apresenta todos os retornos automáticos disponíveis no escopo do usuário, sem limitar automaticamente o resultado ao mês atual.

## 9. Agrupamento por PLOA/equipe

Os retornos são agrupados em cards por PLOA. Cada card informa o nome da equipe e o total de retornos encontrados.

A identificação da equipe utiliza uma regra de recuperação em cascata, importante para evitar que um retorno perca seu vínculo operacional quando algum campo estiver vazio. A ordem adotada é:

1. equipe registrada na OS do retorno;
2. equipe registrada diretamente na solicitação de retorno;
3. equipe registrada na OS de origem;
4. equipe registrada diretamente na solicitação de origem;
5. classificação como **Sem equipe**, caso nenhum vínculo seja encontrado.

As equipes ativas podem aparecer mesmo quando possuem total zero. Isso preserva uma visão estável das PLOAs disponíveis e facilita a conferência de quais equipes possuem ou não agenda no recorte selecionado.

O card **Sem equipe** tem tratamento próprio e direciona para uma tela de detalhe dedicada. Essa visão permite identificar demandas que ainda precisam de atribuição operacional.

## 10. Detalhamento por equipe

Ao abrir uma PLOA, o sistema apresenta uma visão exclusiva dos seus retornos, mantendo os filtros aplicados na central.

O detalhamento contém:

- total de retornos da equipe;
- quantidade prevista para os próximos sete dias;
- quantidade sem fechamento;
- quantidade com data vencida;
- resumo mensal;
- logs completos dos registros filtrados.

O resumo mensal informa, para cada mês com retorno:

- total de registros;
- quantidade sem fechamento;
- quantidade com data vencida;
- quantidade concluída.

Essa estrutura permite comparar o volume por competência e identificar acúmulo de pendências em meses anteriores.

## 11. Logs gerais e dados apresentados

A tabela de logs exibe, para cada retorno:

- data e hora de agendamento;
- quantidade de dias até o atendimento, quando estiver nos próximos sete dias;
- ID da solicitação;
- identificador da OS, quando disponível;
- ID da solicitação de origem;
- equipe/PLOA;
- endereço formatado;
- bairro;
- unidade/UVIS;
- tipo de operação;
- foco;
- situação operacional calculada;
- status original da solicitação;
- ação para abrir o formulário da OS.

Os endereços são apresentados com logradouro, número, bairro, cidade, UF e complemento, conforme a disponibilidade dos dados.

A listagem é paginada. O padrão é de 25 registros por página, com opções de 25, 50 ou 100 itens, evitando telas excessivamente longas e mantendo a navegação adequada em bases maiores.

## 12. Ordenação e priorização visual

A ordenação busca manter os itens pendentes e futuros em evidência e deslocar os registros atrasados para o final da lista. Dentro desses grupos, as datas mais recentes aparecem primeiro.

Essa regra evita que um grande passivo histórico esconda os retornos futuros que precisam ser planejados, sem retirar da central a visibilidade das pendências vencidas.

## 13. Proteção de acesso e segregação de dados

A central reaproveita as regras centrais de autorização do sistema:

- o usuário precisa estar autenticado;
- o perfil precisa possuir acesso à Central de Relatórios;
- usuários vinculados a uma prefeitura visualizam apenas os dados permitidos para essa prefeitura;
- usuários regionais visualizam somente a região associada ao seu perfil;
- a abertura do detalhe de uma equipe fora do escopo autorizado é rejeitada.

Esses controles são aplicados no backend, e não apenas na interface, reduzindo o risco de acesso indevido por manipulação de URL ou de parâmetros.

## 14. Fluxo operacional resumido

```text
Sistema gera uma solicitação de retorno
  -> retorno passa a integrar a Central
  -> gestão consulta indicadores e filtros
  -> retorno é associado a uma PLOA ou destacado como sem equipe
  -> responsável abre o detalhe da equipe
  -> registro é acompanhado até o fechamento
  -> situação operacional é recalculada nas próximas consultas
```

## 15. Benefícios para a gestão

### 15.1. Planejamento

- antecipação dos retornos previstos para os próximos dias;
- melhor distribuição da agenda entre as equipes;
- identificação de demandas ainda sem PLOA;
- visão mensal da carga de trabalho.

### 15.2. Controle operacional

- identificação objetiva de OSs sem fechamento;
- visibilidade de datas vencidas;
- acesso rápido ao registro detalhado da OS;
- redução da dependência de conferências manuais.

### 15.3. Governança e rastreabilidade

- manutenção do vínculo entre retorno e solicitação de origem;
- aplicação das mesmas regras de escopo usadas no restante do sistema;
- indicadores calculados a partir dos registros oficiais da aplicação;
- padronização da análise entre gestão, região e prefeitura.

## 16. Indicadores recomendados para acompanhamento gerencial

Além dos números já apresentados na tela, recomenda-se acompanhar periodicamente:

| Indicador | Fórmula sugerida | Finalidade |
| --- | --- | --- |
| Taxa de conclusão | retornos concluídos / total de retornos | Medir a capacidade de fechamento da agenda. |
| Taxa sem fechamento | retornos sem fechamento / total de retornos | Identificar falhas de encerramento no sistema. |
| Taxa de vencimento | retornos com data vencida / total de retornos | Monitorar perda de prazo. |
| Cobertura de equipe | retornos com equipe / total de retornos | Avaliar a qualidade da distribuição operacional. |
| Carga por PLOA | total de retornos por equipe | Comparar volume e apoiar balanceamento. |

Esses indicadores podem ser extraídos dos totais já calculados pela central e utilizados em reuniões de acompanhamento.

## 17. Validação e cobertura automatizada

A implementação possui testes automatizados para os principais comportamentos da central, incluindo:

- inclusão apenas de retornos automáticos;
- agrupamento por equipe e lista geral;
- contabilização de registros sem equipe;
- funcionamento sem filtro obrigatório de período;
- ordenação de datas futuras e vencidas;
- classificação de situação operacional;
- filtro por situação operacional;
- exibição de equipe ativa sem retornos;
- paginação;
- detalhamento por equipe;
- combinação de filtros de busca;
- recuperação da equipe a partir da solicitação ou OS de origem;
- isolamento por prefeitura.

## 18. Componentes técnicos envolvidos

Os principais componentes são:

- `app/modules/relatorios/service.py`: consulta, filtros, classificação, indicadores, agrupamento, serialização e paginação;
- `app/modules/relatorios/routes.py`: rotas da central, detalhe por equipe e visão sem equipe;
- `app/templates/relatorios_menu.html`: acesso pela Central de Relatórios;
- `app/templates/relatorios_retornos_automaticos.html`: visão consolidada;
- `app/templates/relatorios_retornos_automaticos_equipe.html`: visão detalhada da PLOA;
- `app/templates/_retornos_automaticos_table.html`: tabela reutilizável de logs;
- `tests/test_relatorios_retornos_automaticos.py`: testes automatizados da funcionalidade.

## 19. Pontos de atenção e evolução

A central atualmente oferece consulta e acompanhamento em tela. Não foi identificada, nessa funcionalidade específica, uma exportação dedicada para PDF ou planilha. Caso a gestão precise distribuir relatórios fora do sistema, esse é um possível próximo passo.

Outras evoluções que podem ampliar o valor gerencial são:

- percentual de conclusão e vencimento diretamente nos cards;
- comparação entre períodos;
- exportação dos dados filtrados;
- alertas automáticos para OSs sem fechamento;
- histórico da mudança de equipe;
- painel de tendência por região, UVIS e PLOA;
- metas de prazo e indicadores de nível de serviço.

## 20. Conclusão

A Central de Retornos Automáticos consolida o acompanhamento de uma etapa crítica do ciclo operacional. A solução entrega visibilidade de volume, prazo, equipe, origem e situação de cada retorno, preservando os controles de acesso do sistema.

Do ponto de vista gerencial, a funcionalidade reduz o esforço de conferência, melhora a priorização da agenda e cria uma base objetiva para cobrança de fechamento e tomada de decisão. Do ponto de vista técnico, utiliza dados já vinculados às solicitações e OSs, aplica regras consistentes de classificação e possui cobertura automatizada para seus cenários principais.
