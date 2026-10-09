# Relatório executivo e técnico: melhoria com Place ID para vincular rotas KML às Ordens de Serviço

**Data de referência:** 14 de agosto de 2026  
**Status da melhoria:** implementada no código; primeira etapa do preenchimento retroativo concluída  
**Área do sistema:** Logs de voo DJI / Rotas KML / Ordens de Serviço

## 1. Resumo executivo

Foi implementada uma melhoria no processo de vinculação das rotas KML às Ordens de Serviço (OS), utilizando o **Google Place ID** como uma das principais referências para identificar o local correto do voo.

O fluxo de aprovação das solicitações permanece manual. O sistema somente procura uma correspondência de KML depois que a solicitação foi aprovada e gerou uma OS. A automação ocorre na etapa seguinte: existindo a OS, a rota KML pode ser vinculada automaticamente com base no Place ID e nas demais evidências operacionais.

O Place ID é um identificador fornecido pelo Google para representar um local geográfico. Diferentemente do endereço digitado, que pode variar por abreviação, acentuação ou formatação, o Place ID permite comparar a solicitação e a rota por uma referência comum do local.

É importante destacar que **nem todas as solicitações possuem Place ID**. O campo é opcional no banco de dados, e registros antigos ou cadastros em que a geocodificação não retornou o identificador podem permanecer sem esse dado. Por isso, a melhoria não depende exclusivamente do Place ID: quando ele não existe, o sistema utiliza a combinação de endereço, data, horário, aeronave, piloto e distância geográfica.

Com a melhoria, o sistema consegue:

- armazenar o Place ID no cadastro da solicitação;
- receber o Place ID nos dados do voo DJI ou no próprio arquivo KML;
- descobrir o Place ID de uma rota por geocodificação reversa quando ele não estiver no arquivo;
- comparar o local da rota com o local da OS;
- combinar essa comparação com data, horário, aeronave, piloto, endereço e distância;
- vincular automaticamente o KML à OS quando o resultado atingir um nível seguro de confiança;
- evitar o vínculo automático quando houver dúvida entre duas OSs;
- manter uma opção de vínculo manual para tratamento das exceções.

O ganho principal é a redução do trabalho manual e do risco de associar uma rota de voo à OS errada. A melhoria também aumenta a rastreabilidade, pois a rota executada pode ser aberta diretamente a partir do formulário da OS.

## 2. Contexto e problema de negócio

As rotas KML registram o percurso geográfico executado pelo drone. Para que esse arquivo tenha valor operacional, documental e gerencial, ele precisa estar associado à Ordem de Serviço correspondente.

Antes da melhoria baseada em Place ID, o vínculo dependia principalmente de referências como:

- código do registro de voo;
- data e horário;
- aeronave;
- piloto;
- endereço informado em texto;
- proximidade entre as coordenadas da rota e da solicitação;
- seleção manual da OS.

Essas informações continuam importantes, mas podem apresentar ambiguidades. Um piloto pode executar mais de uma OS no mesmo dia, a mesma aeronave pode realizar vários voos e o endereço pode ser registrado de formas diferentes em cada origem de dados.

Exemplos de variação textual:

```text
R. Francisco Guimarães da Silva, 111
Rua Francisco Guimaraes Silva, nº 111
Francisco Guimaraes da Silva, 111 - Varginha
```

Mesmo representando o mesmo local, essas descrições não são idênticas. O Place ID adiciona uma referência geográfica comum e reduz a dependência da comparação textual isolada.

## 3. Objetivos da melhoria

### 3.1. Objetivo principal

Aumentar a precisão e automatizar, com controle de confiança, a associação entre uma rota KML importada e a Ordem de Serviço executada no mesmo local.

### 3.2. Objetivos específicos

- utilizar o Place ID como referência consistente entre solicitação, voo DJI e KML;
- reduzir vínculos manuais;
- diminuir o risco de associação incorreta;
- aproveitar as coordenadas da rota quando o KML não trouxer o Place ID;
- combinar sinais geográficos e operacionais;
- recusar correspondências fracas ou ambíguas;
- permitir o processamento de rotas antigas ainda sem OS;
- manter uma alternativa administrativa de vínculo manual;
- disponibilizar a rota vinculada no formulário da OS.

### 3.3. Preservação da aprovação manual

A melhoria não aprova solicitações, não cria OSs por conta própria e não altera a decisão do responsável pela análise. A separação de responsabilidades é:

```text
Solicitação recebida
  -> análise e aprovação manual
  -> geração da Ordem de Serviço
  -> importação do log e da rota KML
  -> vínculo automático entre KML e OS, quando a confiança for suficiente
```

Como a busca de candidatas consulta exclusivamente registros da tabela de Ordens de Serviço, uma solicitação ainda não aprovada e sem OS não pode receber um KML por esse mecanismo.

## 4. O que é o Place ID

O Place ID é uma identificação textual atribuída pelo serviço Google Maps a um lugar reconhecido. Ele pode representar um endereço, estabelecimento ou outra referência geográfica.

Um valor possui formato semelhante a:

```text
ChIJxxxxxxxxxxxxxxxxxxxx
```

No sistema, esse identificador funciona como uma chave de correspondência geográfica. Quando a solicitação e a rota possuem o mesmo Place ID, existe um sinal forte de que ambas se referem ao mesmo local.

O Place ID não substitui os demais dados. A implementação o utiliza como evidência principal, mas exige pelo menos um sinal adicional, como compatibilidade de data, distância, aeronave ou piloto. Essa decisão reduz o risco de um vínculo automático baseado apenas no local, especialmente quando existem várias operações no mesmo endereço.

Também não existe obrigatoriedade de preenchimento do Place ID. Ele funciona como um reforço de precisão quando está disponível, enquanto o mecanismo de correspondência por múltiplas evidências preserva a compatibilidade com solicitações legadas ou incompletas.

## 5. Onde o Place ID é armazenado

A melhoria incluiu o Place ID em três pontos do fluxo:

| Entidade | Campo | Finalidade |
| --- | --- | --- |
| Solicitação | `solicitacoes.place_id` | Identificar o local solicitado e, consequentemente, o endereço da OS. |
| Registro de voo DJI | `dji_flight_records.place_id` | Identificar o local informado no relatório Excel do voo. |
| Rota KML | `dji_flight_kml_routes.place_id` | Identificar geograficamente a rota importada. |

Os campos possuem índice no banco de dados, favorecendo consultas e futuras evoluções de busca direta por local.

Os três campos de Place ID são opcionais. Portanto, a ausência do identificador em uma solicitação, registro DJI ou rota KML é um cenário esperado e tratado pelo mecanismo de vinculação.

### 5.1. Diagnóstico da base em 14 de agosto de 2026

Foi realizada uma consulta somente de leitura no banco configurado pela aplicação. O levantamento encontrou:

| Indicador | Resultado |
| --- | ---: |
| Total de solicitações | 4.732 |
| Solicitações com Place ID antes do preenchimento | 730 |
| Solicitações sem Place ID antes do preenchimento | 4.002 |
| Cobertura geral antes do preenchimento | 15,43% |
| Solicitações com Place ID após a primeira etapa | 1.054 |
| Solicitações sem Place ID após a primeira etapa | 3.678 |
| Cobertura geral após a primeira etapa | 22,27% |

A solicitação criada mais recentemente com Place ID foi a **#4897**, registrada em **13/08/2026 às 18:23:28**, com agendamento para 27/08/2026.

A solicitação mais recente sem Place ID foi a **#4910**, registrada em **14/08/2026 às 11:43:40**, com agendamento para 29/09/2026.

O primeiro registro localizado com Place ID foi criado em 14/05/2026. Essa data não representa, necessariamente, o início de uma cobertura contínua, pois existem períodos posteriores com preenchimento parcial ou inexistente.

Entre 05/08/2026 e 13/08/2026, todos os registros criados nas datas que possuíam solicitações apresentaram Place ID. Em 14/08/2026, as 13 solicitações criadas até o momento da consulta estavam sem o identificador.

### 5.2. Causa das solicitações recentes sem Place ID

As 13 solicitações de 14/08/2026 correspondem aos IDs **#4898 a #4910**. Todas são retornos automáticos, possuem endereço e coordenadas, mas foram geradas a partir de solicitações de origem que também não possuem Place ID.

O fluxo anterior copiava endereço, latitude e longitude para o retorno, mas não copiava nem resolvia o Place ID no backend. Essa foi identificada como a causa direta da interrupção observada nos registros mais recentes.

### 5.3. Correção preventiva adicionada

A melhoria foi ampliada para resolver o Place ID automaticamente no backend:

- no cadastro normal, quando o navegador não enviar o identificador;
- na criação de retorno automático pelo piloto;
- na criação de retorno automático pela equipe UVIS;
- na edição de uma solicitação sem Place ID;
- na edição que altera o endereço, evitando manter o identificador do local anterior.

Nos retornos, o sistema primeiro reutiliza o Place ID da solicitação de origem. Se a origem também não possuir o dado, consulta a API de geocodificação do Google usando o endereço copiado.

Foi criado ainda um script de preenchimento retroativo com seleção explícita por IDs, data de criação ou período operacional dos voos. Ele executa em modo de simulação por padrão e somente grava alterações com a opção `--commit`.

As 13 solicitações recentes citadas não fizeram parte da primeira etapa retroativa, cujo recorte foi definido pelos logs de voo de junho e julho. Para novos registros e retornos automáticos, a correção preventiva passa a copiar o Place ID da origem ou resolvê-lo pela API do Google quando necessário.

### 5.4. Recorte dos logs de voo e preenchimento executado

O período foi definido pela cobertura efetiva dos registros DJI disponíveis:

| Indicador | Resultado |
| --- | ---: |
| Registros de voo DJI entre 01/06/2026 e 31/07/2026 | 941 |
| Registros em junho | 458 |
| Registros em julho | 483 |
| Rotas KML correspondentes | 941 |
| Rotas KML com Place ID | 941 |
| OSs já vinculadas a uma dessas rotas | 408 |

Para respeitar as aprovações manuais, o processo retroativo selecionou somente solicitações que já possuíam uma OS. A solicitação entrou no recorte quando a data de aplicação da OS, a data agendada da solicitação ou a data de resposta da OS estava entre **01/06/2026 e 31/07/2026**.

Antes da execução, 1.516 solicitações desse recorte estavam sem Place ID. A primeira etapa foi executada sem acesso à API do Google e produziu o seguinte resultado:

| Resultado da primeira etapa | Quantidade |
| --- | ---: |
| Solicitações analisadas | 1.516 |
| Place IDs preenchidos | 324 |
| Copiados do KML já vinculado | 312 |
| Herdados da solicitação de origem | 12 |
| Chamadas à API do Google | 0 |
| Solicitações ainda sem resultado no recorte | 1.192 |

Após a execução, as **408 OSs que já possuem KML vinculado** ficaram com Place ID em suas respectivas solicitações. Nenhum vínculo entre OS e KML foi criado, removido ou alterado nessa etapa; somente o campo `solicitacoes.place_id` foi preenchido quando já existia uma fonte interna confiável.

As 1.192 solicitações restantes exigem geocodificação do endereço pela API do Google. Essa segunda etapa deve ser executada separadamente, preferencialmente em lotes, com acompanhamento de resultados e consumo da API.

O vínculo final entre a OS e a rota é armazenado em:

```text
ordens_servico.dji_kml_route_id
```

Esse campo referencia a rota registrada em `dji_flight_kml_routes`.

## 6. Origem do Place ID em cada etapa

### 6.1. Solicitação

Durante o cadastro da solicitação, o endereço é geocodificado. Quando o Google retorna um Place ID válido, ele é armazenado junto aos dados de endereço e coordenadas.

Com isso, a futura OS pode nascer com uma referência geográfica associada à solicitação. Entretanto, o campo pode permanecer vazio nos seguintes casos:

- solicitação criada antes da implantação do Place ID;
- geocodificação sem resultado válido;
- indisponibilidade temporária do serviço externo;
- endereço incompleto ou não reconhecido;
- registros legados inseridos por outros fluxos.

### 6.2. Planilha de voo DJI

O importador de planilhas reconhece colunas com nomes equivalentes a:

- `PlaceId`;
- `GooglePlaceId`.

Quando a coluna está presente, o valor é gravado no registro do voo DJI e também permanece disponível no conteúdo bruto importado.

### 6.3. Arquivo KML

O importador procura o Place ID nos dados estendidos do KML, aceitando variações como:

- `Place ID`;
- `PlaceId`;
- `Google Place ID`;
- `google_place_id`.

### 6.4. Geocodificação reversa

Quando o arquivo KML não contém Place ID, o sistema calcula um ponto representativo da rota usando a média das latitudes e longitudes válidas.

Esse ponto é enviado ao serviço de geocodificação reversa, que pode retornar:

- endereço formatado;
- Place ID correspondente.

O identificador obtido é salvo na rota KML e passa a participar do mecanismo de vinculação.

Se a consulta externa falhar, a importação não é interrompida. O sistema continua tentando identificar a OS pelos demais sinais disponíveis.

## 7. Fluxo completo da melhoria

```text
Usuário cadastra a solicitação
  -> Google pode retornar o Place ID do endereço
  -> quando disponível, o Place ID é salvo na solicitação

Responsável analisa a solicitação
  -> aprovação continua sendo manual
  -> somente após a aprovação é gerada a OS

Administrador importa o KML
  -> sistema lê código, data, aeronave, piloto e coordenadas
  -> tenta obter o Place ID do próprio KML
  -> se necessário, faz geocodificação reversa da rota
  -> busca OSs candidatas ainda sem KML
  -> calcula a compatibilidade de cada OS com ou sem Place ID
  -> seleciona a melhor correspondência segura
  -> grava dji_kml_route_id na OS
  -> rota passa a aparecer no formulário e nos relatórios
```

## 8. Seleção inicial de OSs candidatas

O sistema avalia apenas OSs que já foram geradas a partir de solicitações aprovadas e que ainda não possuem uma rota KML vinculada. Solicitações pendentes ou reprovadas, por não possuírem OS, ficam fora da seleção automática.

Quando a rota possui data e hora, a busca é limitada às OSs que apresentem alguma referência operacional no intervalo de dois dias antes até dois dias depois da rota. São consideradas:

- data de aplicação da OS;
- data de agendamento da solicitação;
- data de resposta/fechamento da OS.

A consulta ordena os registros mais recentes primeiro e analisa até 300 candidatas. Essa pré-seleção reduz o custo da comparação completa e diminui a possibilidade de confrontar a rota com OSs sem relação temporal.

## 9. Mecanismo de pontuação

Cada OS candidata recebe uma pontuação composta por seis grupos de evidências.

| Evidência | Pontuação máxima | O que é comparado |
| --- | ---: | --- |
| Place ID | 65 pontos | Place ID da solicitação contra o KML, o voo relacionado ou os dados brutos do voo. |
| Horário/data | 40 pontos | Momento da rota contra aplicação, agendamento e fechamento da OS. |
| Aeronave | 35 pontos | Identificação do drone no KML contra prefixos, denominações e números de série da OS. |
| Piloto | 15 pontos | Nome do piloto da rota contra piloto e auxiliar informados na OS. |
| Endereço | 30 pontos | Texto e componentes normalizados do endereço. |
| Proximidade geográfica | 35 pontos | Menor distância entre a coordenada da solicitação e os pontos da rota. |

A pontuação total não é uma porcentagem. Ela representa a soma das evidências compatíveis.

### 9.1. Peso do Place ID

Uma correspondência exata de Place ID adiciona 65 pontos, tornando-se um dos sinais mais fortes do mecanismo.

O Place ID da solicitação pode ser comparado com:

1. o Place ID salvo diretamente na rota KML;
2. o Place ID do registro de voo DJI relacionado;
3. o Place ID encontrado no conteúdo bruto do registro de voo.

Essa busca em múltiplas fontes permite aproveitar dados importados em formatos diferentes.

### 9.2. Compatibilidade temporal

O sistema monta janelas de tempo com base em:

- data e horário de início e término da aplicação;
- data de aplicação sem horários detalhados;
- horário de resposta/fechamento;
- data e hora de agendamento da solicitação.

A rota recebe pontuação maior quando seu horário está dentro da janela operacional e pontuação progressivamente menor quando está próxima, no mesmo dia ou até algumas horas de distância.

### 9.3. Compatibilidade da aeronave

A identificação da aeronave do KML é confrontada com:

- prefixo da aeronave de pulverização;
- prefixo da aeronave de monitoramento;
- denominação dos drones;
- números de série dos drones.

Uma igualdade normalizada recebe pontuação superior a uma correspondência parcial.

### 9.4. Compatibilidade do piloto

O nome do piloto informado na rota é comparado com o piloto e o auxiliar da OS. O piloto principal possui peso maior, mas o auxiliar também pode fornecer evidência complementar.

### 9.5. Compatibilidade do endereço

O endereço da OS é comparado com o endereço e o nome de campo disponíveis na rota ou no registro de voo. O processo remove acentos, pontuação e palavras comuns para comparar os elementos mais relevantes, como:

- nome do logradouro;
- número;
- bairro;
- cidade;
- CEP.

### 9.6. Proximidade geográfica

O sistema calcula a menor distância entre a coordenada da solicitação e os pontos da rota KML.

| Distância | Pontuação geográfica |
| --- | ---: |
| Até 150 metros | 35 pontos |
| Até 300 metros | 30 pontos |
| Até 750 metros | 22 pontos |
| Até 1.500 metros | 12 pontos |
| Até 3.000 metros | 5 pontos |
| Acima de 3.000 metros | 0 ponto |

O uso da menor distância até a rota é mais adequado do que comparar apenas o primeiro ponto do arquivo, pois o drone pode iniciar o registro antes de chegar ao local principal da operação.

## 10. Regra de confiança para vínculo automático

Uma OS não é vinculada apenas por possuir a maior pontuação. O sistema exige:

1. pontuação total mínima de 70 pontos; e
2. uma combinação de evidências considerada confiável.

As combinações aceitas incluem, de forma resumida:

- Place ID exato acompanhado por compatibilidade temporal, geográfica, de aeronave ou de piloto;
- endereço compatível, horário compatível e apoio de distância ou aeronave;
- endereço compatível e forte proximidade geográfica;
- horário compatível e identificação de aeronave ou forte proximidade;
- aeronave compatível e forte proximidade geográfica.

Portanto, o Place ID exato, isoladamente, não autoriza o vínculo automático. Essa proteção é importante para locais que podem receber várias operações em datas ou horários diferentes.

## 11. Controle de ambiguidade

Após pontuar todas as candidatas, o sistema ordena os resultados do maior para o menor.

Se a diferença entre a melhor e a segunda melhor candidata for inferior a 15 pontos, nenhum vínculo automático é realizado. A rota permanece sem OS para conferência administrativa.

Essa regra evita que o sistema escolha arbitrariamente entre duas OSs muito parecidas, como duas operações no mesmo endereço, realizadas pela mesma equipe em horários próximos.

## 12. Vinculação automática durante a importação

Ao importar um novo KML, o sistema executa as seguintes etapas:

1. valida a extensão `.kml`;
2. rejeita arquivo vazio;
3. calcula o hash do conteúdo para evitar duplicidade;
4. extrai código da rota, aeronave, piloto, data, coordenadas e demais metadados;
5. tenta relacionar o KML a um registro de voo DJI pelo código da rota;
6. obtém ou resolve o Place ID;
7. grava a rota no banco;
8. procura a OS mais compatível;
9. vincula automaticamente quando a confiança é suficiente;
10. informa no resultado da importação quantas rotas foram associadas automaticamente a OSs.

A operação é concluída em uma única transação de banco para o lote importado.

## 13. Tratamento das rotas já existentes

Foi criado um processo específico para analisar rotas KML importadas antes da melhoria ou que permaneceram sem OS.

O script disponível é:

```text
scripts/link_existing_kml_routes_to_os.py
```

Ele permite:

- executar uma simulação sem alterar o banco (`--dry-run`);
- limitar a quantidade de rotas (`--limit`);
- definir intervalo de IDs;
- processar por lotes;
- resolver Place IDs ausentes (`--resolve-place-id`);
- apresentar o resultado de cada rota;
- informar pontuação e composição das evidências.

Exemplo seguro de análise:

```bash
python scripts/link_existing_kml_routes_to_os.py --dry-run --resolve-place-id
```

Após a conferência dos resultados, o processamento pode ser executado sem `--dry-run` para efetivar os vínculos.

O resumo do script apresenta:

- rotas analisadas;
- rotas vinculadas;
- rotas sem correspondência;
- erros;
- Place IDs resolvidos;
- OS escolhida;
- pontuação total;
- pontuação por data, aeronave, piloto, Place ID, endereço e distância.

## 14. Vínculo manual de KML como contingência

Esse vínculo manual é uma contingência específica para a associação entre KML e OS. Ele não deve ser confundido com a aprovação da solicitação, que continua obrigatoriamente manual e ocorre antes da geração da OS.

Rotas que não atingem confiança suficiente permanecem disponíveis na tela de Logs de Voo DJI com status **Sem OS**.

Usuários administrativos autorizados podem informar o ID visual da solicitação e vincular a rota manualmente. Esse fluxo cobre situações como:

- ausência de Place ID;
- OS sem coordenadas;
- dados incompletos de aeronave ou piloto;
- rota com data fora da janela esperada;
- múltiplas OSs muito semelhantes;
- correção de um vínculo operacional conhecido pela administração.

Se a OS já possui outra rota, o sistema recusa a substituição direta. Se a mesma rota estiver vinculada a outra OS e for vinculada manualmente a uma nova OS válida, o vínculo anterior é removido antes da transferência.

## 15. Visualização do resultado

### 15.1. Tela de Logs de Voo DJI

A listagem de rotas KML informa:

- código e nome do arquivo;
- data da rota;
- aeronave e piloto;
- registro de voo DJI relacionado;
- status com OS ou sem OS;
- identificação da OS vinculada;
- acesso ao formulário da OS;
- visualização da rota no mapa;
- download do KML;
- vínculo manual, quando autorizado.

### 15.2. Formulário da OS

Quando existe vínculo, o formulário da OS exibe:

- código da rota;
- data e hora;
- aeronave;
- piloto;
- botão para visualizar o percurso no mapa.

Quando ainda não existe rota, a tela informa que o KML será vinculado após a importação dos logs ou rotas do drone.

## 16. Regras de acesso

A importação de logs/KML e o vínculo manual são restritos aos perfis administrativos autorizados: desenvolvimento, diretoria e administração.

A visualização de uma rota vinculada respeita o contexto da OS:

- administradores do módulo podem consultar as rotas;
- usuários do painel administrativo respeitam a região permitida;
- contas de equipe operacional visualizam rotas de OSs atribuídas à própria equipe;
- pilotos visualizam rotas de equipes às quais estão vinculados.

Rotas sem OS permanecem restritas aos perfis que possuem acesso administrativo aos logs DJI.

## 17. Benefícios para a operação

### 17.1. Redução de trabalho manual

- menos necessidade de localizar a OS por código;
- processamento automático durante a importação;
- possibilidade de tratar o acervo existente em lote;
- foco humano apenas nos casos ambíguos.

### 17.2. Maior precisão

- Place ID como referência geográfica consistente;
- combinação de seis grupos de evidência;
- exigência de sinal complementar ao local;
- rejeição automática quando duas candidatas são semelhantes.

### 17.3. Rastreabilidade

- rota executada acessível diretamente na OS;
- relação persistida entre OS e KML;
- possibilidade de visualizar e baixar o arquivo original;
- resultado detalhado disponível durante o processamento retroativo.

### 17.4. Gestão e prestação de contas

- confirmação visual do percurso realizado;
- maior confiabilidade na associação entre execução e demanda;
- base mais organizada para auditorias e relatórios;
- identificação das rotas que ainda permanecem sem OS.

## 18. Cenários de comportamento

### 18.1. Place ID igual e data compatível

A correspondência recebe 65 pontos pelo local e pontuação adicional pelo horário. Se atingir os critérios de confiança e não houver ambiguidade, o vínculo é realizado automaticamente.

### 18.2. Place ID igual, mas sem nenhum outro sinal

O vínculo automático não é realizado. O sistema exige evidência complementar para evitar associar voos diferentes executados no mesmo local.

### 18.3. KML sem Place ID

O sistema tenta obter o identificador por geocodificação reversa. Se isso não for possível, utiliza endereço, data, aeronave, piloto e distância.

### 18.4. Solicitação sem Place ID

O sistema atribui zero ao critério de Place ID e continua a análise pelos demais sinais. Ainda pode haver vínculo automático quando endereço, horário, aeronave e/ou proximidade geográfica formarem uma combinação confiável e não ambígua.

### 18.5. Endereço escrito de forma diferente

A normalização por tokens permite reconhecer componentes relevantes, mesmo com diferenças de acentuação, abreviação e pontuação.

### 18.6. Duas OSs com pontuações próximas

Se a vantagem da melhor candidata for inferior a 15 pontos, a rota permanece sem vínculo automático e deve ser conferida manualmente.

### 18.7. OS já vinculada a outro KML

A OS não entra na seleção automática. No fluxo manual, a tentativa de associar outra rota é recusada.

### 18.8. Rota antiga sem Place ID

O script de processamento retroativo pode resolver o Place ID e simular a correspondência antes da gravação definitiva.

## 19. Validação e cobertura automatizada

A melhoria possui testes automatizados que validam:

- simulação sem alteração da OS;
- gravação do vínculo e confirmação da transação;
- tratamento dos IDs de rotas já vinculadas;
- resolução de Place ID ausente por geocodificação reversa;
- uso do Place ID salvo na rota;
- uso do Place ID salvo no registro de voo;
- comparação de endereço com formatações diferentes;
- aceitação de Place ID com sinal complementar;
- cálculo do ponto representativo da rota;
- inclusão de Place ID e endereço na composição da pontuação.
- preservação da aprovação manual como requisito anterior à existência da OS;
- preenchimento do Place ID da solicitação a partir da rota após o vínculo;
- herança ou resolução do Place ID nos retornos automáticos;
- resolução no backend quando o cadastro não recebe o identificador do navegador.

## 20. Componentes técnicos envolvidos

Os principais componentes são:

- `app/modules/dji_flight_logs/service.py`: importação, geocodificação reversa, seleção de candidatas, pontuação e vínculo;
- `app/modules/dji_flight_logs/routes.py`: importação, vínculo manual, visualização, download e exclusão;
- `app/clients/google_maps_client.py`: consulta de geocodificação e geocodificação reversa;
- `app/shared/place_id.py`: normalização e resolução centralizada de Place ID;
- `app/models.py`: Place ID nos registros e chave da rota na OS;
- `app/templates/relatorios_dji_logs.html`: gestão das rotas e vínculos;
- `app/templates/piloto_os_formulario.html`: apresentação da rota dentro da OS;
- `scripts/link_existing_kml_routes_to_os.py`: processamento retroativo, simulação e lotes;
- `scripts/backfill_solicitacoes_place_id.py`: preenchimento retroativo das solicitações por fonte interna ou Google;
- `migrations/versions/4d9e8f1a2b3c_add_place_id_to_solicitacoes.py`: Place ID da solicitação;
- `migrations/versions/5a6b7c8d9e0f_add_place_id_to_dji_logs_and_kml.py`: Place ID dos registros DJI e KML;
- `migrations/versions/0f4a6b8c2d1e_add_dji_kml_route_to_os.py`: vínculo entre OS e rota;
- `tests/test_dji_kml_auto_link.py`: testes do mecanismo automático.

## 21. Pontos de atenção e recomendações

### 21.1. Dependência da geocodificação

A resolução automática de Place ID para KMLs que não possuem o campo depende da disponibilidade e configuração do serviço Google Maps. Falhas nessa consulta não impedem a importação, mas podem reduzir a pontuação geográfica do vínculo.

Recomenda-se monitorar erros, volume de consultas e disponibilidade das credenciais usadas pela integração.

O cliente de geocodificação prioriza `GOOGLE_MAPS_KEY_BACK`, destinada às chamadas realizadas pelo servidor, e utiliza `KEY_API_GOOGLE_MAPS` como fallback quando a chave específica não estiver disponível. Em produção, recomenda-se manter uma chave de backend própria, com restrições de API e origem adequadas ao ambiente do servidor.

### 21.2. Ponto representativo de rotas extensas

A geocodificação reversa usa a média das coordenadas da rota. Em percursos muito longos ou irregulares, esse ponto pode não representar exatamente o endereço principal. A comparação pela menor distância entre a solicitação e todos os pontos da rota reduz esse risco, mas o cenário deve permanecer nos testes operacionais.

### 21.3. Escopo organizacional das candidatas

A seleção automática atual considera OSs sem KML e aplica filtros temporais, mas não adiciona explicitamente prefeitura ou região como critério da consulta de candidatas. Os controles de confiança reduzem a chance de associação incorreta, porém recomenda-se incluir o escopo organizacional quando a origem da rota permitir identificar prefeitura, região ou equipe.

### 21.4. Auditoria persistente da decisão

A pontuação detalhada é apresentada pelo script, mas não é armazenada de forma permanente junto ao vínculo. Para fortalecer a auditoria, recomenda-se registrar:

- origem do vínculo: automático ou manual;
- data e hora;
- usuário ou processo responsável;
- pontuação total;
- pontuação por evidência;
- distância calculada;
- Place IDs comparados;
- motivo de eventual remoção ou troca.

### 21.5. Confirmação assistida para casos intermediários

Uma evolução possível é criar uma fila de sugestões para rotas com boa pontuação, mas abaixo do nível automático ou com pequena ambiguidade. A tela poderia apresentar as três melhores OSs candidatas e os motivos da sugestão, permitindo confirmação administrativa rápida.

### 21.6. Cobertura e atualização do Place ID das solicitações

Como o campo é opcional, recomenda-se continuar medindo a cobertura e executar a segunda etapa do preenchimento retroativo de forma controlada para as 1.192 solicitações do recorte que ainda não possuem o identificador.

Também é importante atualizar ou limpar o Place ID quando o endereço de uma solicitação for alterado. Sem esse cuidado, uma solicitação editada poderia manter o identificador do endereço anterior.

A correção implementada passa a resolver um novo Place ID quando o endereço é alterado e limpa o valor anterior caso o novo endereço não possa ser resolvido. A resolução foi centralizada para manter o comportamento consistente no cadastro, na edição e nos retornos automáticos.

## 22. Indicadores recomendados para gestão

| Indicador | Finalidade |
| --- | --- |
| Taxa de vínculo automático | Medir o percentual de KMLs associados sem intervenção manual. |
| Taxa de rotas sem OS | Identificar pendências de associação. |
| Percentual com Place ID | Avaliar a qualidade geográfica da base. |
| Vínculos por faixa de confiança | Monitorar a segurança das associações. |
| Casos ambíguos | Identificar operações, horários ou locais que exigem revisão. |
| Correções de vínculo | Medir a precisão real do mecanismo. |
| Tempo médio entre importação e vínculo | Avaliar a agilidade do processo documental. |

A tela atual já informa totais de rotas vinculadas e sem OS. Os demais indicadores podem ser desenvolvidos a partir de uma trilha de auditoria dos vínculos.

## 23. Conclusão

O uso do Place ID representa uma evolução importante no vínculo entre as rotas KML e as Ordens de Serviço. A melhoria transforma a localização geográfica em uma evidência estruturada e reutilizável desde o cadastro da solicitação até a importação do voo.

O principal diferencial da solução é não depender de um único dado. O Place ID possui peso elevado, mas é combinado com horário, aeronave, piloto, endereço e distância. Além disso, o sistema exige pontuação mínima, combinações confiáveis e vantagem clara sobre a segunda candidata.

Esse desenho equilibra automação e segurança: os casos evidentes são vinculados automaticamente, os casos duvidosos permanecem para conferência e o vínculo manual continua disponível como contingência. O resultado é maior produtividade administrativa, melhor rastreabilidade dos voos e uma relação mais confiável entre a execução registrada no KML e a OS correspondente.

A governança do processo permanece preservada: a aprovação da solicitação continua manual, a OS somente existe após essa aprovação e apenas então o sistema automatiza a associação documental com o KML. Na primeira etapa retroativa, 324 Place IDs foram recuperados exclusivamente de dados internos, sem chamadas ao Google e sem modificar aprovações ou vínculos existentes.
