# Resultados de vigilância e ensaio da prova de conceito

Entrada: **Vigilância → Resultados da vigilância**, `/vigilancia/resultados`.
Também há um atalho em **Focal e LIRAa → Resultados, gráficos e mapa**.
O SINAN aparece na mesma central para a COVISA municipal, nos dois formatos de
perfil suportados, respeitando configurações explícitas da Central de TI.
Contas de agente continuam restritas aos seus levantamentos.

## O que esta entrega acrescenta

- Tabelas e gráficos por levantamento, estrato e área: IIP, Breteau e ITR das
  sete categorias de recipientes. Informação ausente não vira zero; visitas
  repetidas não aumentam artificialmente o denominador.
- Filtros de atividade, levantamento, estrato, área, bairro e datas de inspeção.
  Tratamento focal segue o recorte territorial e as datas, pois não pertence a
  um levantamento LIRAa. Não entra no cálculo dos índices LIRAa.
- Mapa com contornos preservados no plano, agrupados por estrato/área e
  coloridos pelo IIP preliminar do grupo. A escala é numérica, de 0 a 100%, e
  não classifica risco de surto. Não se faz média simples dos índices.
- Camadas independentes de visitas LIRAa, ações focais e coordenadas de um
  lote SINAN autorizado ou demonstrativo, conforme o modo selecionado.
- Exportação dos índices em CSV, dos contornos em GeoJSON e impressão pelo
  navegador, com opção de salvar em PDF. A versão impressa inclui os gráficos,
  tabelas e um desenho dos contornos sem mapa-base. Não exporta imagens do
  Google nem as coordenadas individuais SINAN pelo GeoJSON.

O mapa de IIP exige selecionar um único levantamento. A comparação de vários
levantamentos permanece nas tabelas e gráficos. Contornos são os quarteirões
selecionados no plano: não representam a delimitação oficial completa do
estrato. Grupos sem contorno continuam disponíveis nas tabelas; cobertura
parcial de contornos é informada ao usuário. Atualizar o RG depois da liberação
não altera a geometria histórica do plano.

## Relação da prefeitura com o IBGE

`Prefeitura.id` é o ID interno. O painel não deduz IBGE por nome, endereço ou
coordenada. A relação precisa ser configurada no ambiente. Exemplo **somente
ilustrativo**, quando a prefeitura interna `7` corresponder a Pesqueira/PE:

```dotenv
VIGILANCIA_MUNICIPIOS_IBGE='{"7":"2610905"}'
```

Conferir a correspondência real antes de definir essa variável e reiniciar o
serviço. A ausência ou uma configuração inválida desabilita a comparação SINAN,
com aviso; não interfere nos índices de campo. Esta entrega não preenche essa
configuração no banco nem associa prefeituras automaticamente.

O catálogo contempla os 15 municípios do CONDOMAR já disponíveis no SINAN.
Para a POC regional, preencher uma entrada por ID interno real no mesmo objeto
JSON, preservando os IDs de cada ambiente. O banco de teste não deve receber
IDs presumidos do banco real; a relação é definida depois que os cadastros
estiverem disponíveis. O usuário municipal permanece na prefeitura de sua
conta; um administrador autorizado pode selecionar outra prefeitura cadastrada.
O [modelo de revisão dos 15 vínculos](exemplos/condomar-vinculos-ibge.json)
contém nomes e IBGEs, com IDs internos em branco para não presumir os do banco
real. Depois da revisão, converter as entradas preenchidas para o objeto
`{"ID_INTERNO":"IBGE"}` da variável de ambiente acima.

No painel, escolher doença e ano, aplicar para carregar a lista e selecionar
um lote. A lista contém até 20 snapshots publicados do **mesmo dono, IBGE,
ano, doença e modo demonstração/autorizado**. Não há soma entre lotes.
Snapshots parciais são identificados. O painel apenas lê as fontes, sem iniciar
importações nem expirar lotes em execução.

O CSV SINAN possui coordenadas fornecidas pela equipe; a API pública atual
possui agregações sem coordenadas individuais, portanto seus valores aparecem
como totais, sem pontos de casos no mapa. Não se transformam totais municipais
em endereços fictícios. Referências individuais não são incluídas no payload
do mapa integrado.

Os filtros temporais mantêm a origem: datas de inspeção no campo e semanas
de notificação `AAAASS` no SINAN. A coordenação precisa revisar os dois períodos;
o sistema não converte semana epidemiológica em semana ISO nem infere que
proximidade geográfica signifique transmissão ou vínculo com um imóvel.

## Ensaio completo com dados fictícios

Para carregar a amostra visual pronta em uma prefeitura ativa identificada
como teste/demonstração, usar o script abaixo. O primeiro comando só confere o
plano; o segundo insere exclusivamente `demo=True`, em uma única transação.
Não cria usuários, prefeituras ou OS e não altera dados autorizados.

```sh
.venv/bin/python -B scripts/seed_liraa_demo.py --prefeitura-id 2 --data-base 2026-10-19
IJA_ALLOW_TEST_SEED=1 .venv/bin/python -B scripts/seed_liraa_demo.py --prefeitura-id 2 --data-base 2026-10-19 --apply
```

O ID `2` foi conferido como **Prefeitura Teste** no banco de teste conectado em
19/10/2026. Em outro ambiente, conferir o ID antes de executar. A amostra usa o
levantamento `DEMO-LIRAA-20261019`: três estratos, seis quarteirões, 66 visitas
LIRAa (60 imóveis inspecionados, 13 positivos e seis pendências), 12 ações focais
e sete lotes. IIP esperado por estrato: **5%, 20% e 40%**. Coordenadas e resultados
são ilustrativos, sem validade epidemiológica. Repetir com a mesma data não
duplica a amostra; divergências são recusadas, sem sobrescrever edições.

Abrir **Vigilância → Resultados**, selecionar a prefeitura usada, o modo
**Demonstração** e esse levantamento. Os gráficos e os contornos de impressão
ficam disponíveis mesmo quando o Google Maps não funciona no endereço local.
O seed não cria lotes SINAN nem vínculos IBGE, que continuam na etapa de
configuração acordada. O roteiro abaixo também pode ser executado manualmente.

1. Usar o ambiente de demonstração. Criar ou selecionar uma prefeitura
   demonstrativa e uma conta individual de agente, sem dados pessoais reais.
2. Entrar pela COVISA e confirmar os quatro acessos na central: SINAN,
   Focal/LIRAa, resultados e arquivos. Entrar no SINAN e voltar pela central.
3. Cadastrar um quarteirão com contorno **antes de incluí-lo na amostra**.
   Criar levantamento, estrato, metas e atribuição do agente. Conferir e liberar.
4. Registrar e confirmar uma inspeção positiva com dois recipientes B, uma
   negativa com zeros nas sete categorias e uma visita fechada sem resultado.
   Usar três códigos distintos de imóvel e inspeção no mesmo estrato/área.
5. Reabrir os registros. O resultado esperado é: dois imóveis inspecionados,
   um positivo, uma pendência, **IIP 50%, Breteau 100 e ITR B 100%**.
6. Registrar uma ação focal no mesmo bairro/área e período. Ela deve aparecer
   na camada focal, preservando os resultados acima.
7. Abrir Resultados e selecionar o levantamento. Conferir o contorno azul, os
   valores ao clicar, os gráficos, os filtros e as exportações CSV/GeoJSON.
8. Configurar a relação IBGE correta e importar um CSV SINAN fictício pela
   mesma conta da coordenação. Selecionar seu lote no painel e conferir
   suspeitos/confirmados e semanas. Em lote da API, conferir a indicação de que
   não existem coordenadas individuais. Nenhum desses casos entra no IIP.
9. Imprimir/salvar PDF e conferir as tabelas, os gráficos e os contornos. Testar
   celular e tema escuro. O layout de impressão usa fundo branco.
10. Reiniciar o ambiente de demonstração e reabrir os dados. Reenviar a origem
    sem duplicar inspeções. Conferir bloqueio de outra prefeitura e de outra
    conta SINAN, bem como as restrições de consulta/exportação configuradas em TI.

As fixtures de testes automatizados são locais, com SQLite descartável. O teste
PostgreSQL usa um schema temporário removido no final. Nenhum cadastro de
demonstração é criado automaticamente pela aplicação. O script acima foi
aplicado ao banco de teste somente após solicitação explícita do usuário. A prévia de
validação usa uma porta temporária própria, sem reiniciar o serviço da porta 5003.

## Limites para o aceite

Esta entrega amplia a evidência técnica dos itens III (mapear IIP), VIII
(tabelas, gráficos e mapas) e XII (comparação espacial de fontes) do trecho
fornecido. Não certifica aprovação em roteiro de banca que não foi fornecido.

Ainda é necessário ensaiar no domínio autorizado do Google Maps, configurar a
prefeitura/IBGE efetivamente utilizada e validar um arquivo representativo da
prefeitura. O importador continua no layout próprio documentado, sem afirmar
compatibilidade com todos os sistemas governamentais. A chave Google e suas
restrições não foram alteradas. O mapa real em localhost permanece indisponível;
o navegador de teste usou um adaptador identificado como mapa simulado.

Permanecem as evoluções metodológicas e operacionais já documentadas: sorteio
nativo validado, coleta/laboratório completo, boletins oficiais, retificações
de planos liberados e ampliação dos limites de volume. Um registro direto gera
um lote; o limite atual de 200 lotes por prefeitura/modo não é adequado para
uma campanha municipal extensa de digitação sem essa evolução.

Referências: [manual LIRAa do Ministério da Saúde, 2013](https://bvsms.saude.gov.br/bvs/publicacoes/manual_liraa_2013.pdf),
[formas da Maps JavaScript API](https://developers.google.com/maps/documentation/javascript/shapes).
