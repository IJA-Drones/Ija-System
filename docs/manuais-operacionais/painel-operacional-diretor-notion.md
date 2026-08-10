# Painel Operacional do Diretor

## Visão geral

O **Painel Operacional** é uma nova funcionalidade do IJA System criada para apoiar decisões rápidas de operação em campo, principalmente em atividades que envolvem drones.

A tela permite que o usuário informe um endereço operacional e receba um contexto local consolidado com:

- localização georreferenciada;
- mapa do ponto informado;
- clima atual;
- vento, rajada, chuva, nuvens, umidade e temperatura;
- decisão automática de risco operacional;
- checklist de preparação;
- histórico de OS próximas;
- resumo de recursos disponíveis para a operação;
- links rápidos para rota, Google Maps e Windy.

O objetivo é centralizar informações importantes antes do deslocamento da equipe e antes da liberação de voo.

---

## Perfil de acesso

O Painel Operacional é destinado ao novo tipo de usuário **diretor**.

Na hierarquia do sistema, o perfil **diretor** fica:

- acima do **admin**;
- abaixo do **dev**.

O diretor possui acesso às funcionalidades administrativas comuns, como o admin, e também recebe acesso ao **Painel Operacional**.

Atualmente, o Painel Operacional é acessível para:

- **diretor**;
- **dev**.

O perfil **admin** comum não acessa essa tela.

---

## Onde acessar

O acesso é feito pelo menu lateral do sistema:

**Painel Operacional**

Rota interna:

`/diretor/painel-operacional`

API utilizada pela tela:

`/api/painel-operacional/contexto-local`

---

## Objetivo da funcionalidade

O Painel Operacional foi criado para responder rapidamente à pergunta:

**“Esse endereço está adequado para planejar ou liberar uma operação com equipe e drone?”**

Para isso, a tela reúne informações que antes precisariam ser consultadas em locais diferentes, como mapa, clima, vento, histórico de solicitações próximas e disponibilidade de recursos.

---

## Como usar

### 1. Abrir o Painel Operacional

O usuário diretor ou dev acessa o painel pelo menu lateral.

### 2. Informar o endereço

No campo **Endereço operacional**, digite um endereço completo ou suficientemente detalhado.

Exemplos:

- `Rua Francisco Mendes, 283, Socorro, São Paulo/SP`
- `Avenida Atlântica, Copacabana, Rio de Janeiro/RJ`
- `Praça da Sé, São Paulo/SP`

Quanto mais completo o endereço, maior a chance de o mapa e o contexto local retornarem o ponto correto.

### 3. Consultar o contexto

Após clicar em **Consultar**, o sistema:

- localiza o endereço no Google Maps;
- extrai latitude e longitude;
- consulta o clima atual pela coordenada;
- monta uma análise automática de risco;
- busca OS próximas no sistema;
- resume recursos operacionais disponíveis;
- atualiza o mapa local e os links externos.

### 4. Analisar a decisão de voo

O bloco **Decisão de voo** apresenta uma classificação operacional:

- **Favorável:** não há alerta automático relevante para vento, chuva ou temperatura;
- **Atenção:** há algum fator que exige conferência antes da liberação;
- **Crítico:** há condição que pode comprometer a operação e exige reavaliação.

Essa decisão não substitui a análise humana. Ela funciona como apoio rápido para planejamento e triagem operacional.

---

## Informações exibidas no painel

### Contexto climático

O painel exibe dados atuais do ponto consultado:

- temperatura;
- descrição do tempo;
- velocidade do vento;
- rajada de vento;
- chuva;
- cobertura de nuvens;
- umidade;
- coordenadas.

Esses dados ajudam a avaliar se a equipe pode se deslocar e se há condições mínimas para planejar voo com drone.

### Localização

O endereço informado é convertido em coordenadas.

O painel exibe:

- latitude;
- longitude;
- endereço formatado de referência;
- mapa local em visualização híbrida.

Também são disponibilizados links rápidos para:

- abrir rota no Google Maps;
- abrir o ponto no Google Maps;
- abrir o ponto no Windy.

### Decisão de risco

O sistema calcula o risco com base em critérios automáticos:

- vento forte;
- rajadas elevadas;
- chuva ou instabilidade;
- temperatura elevada.

Quando algum desses fatores é identificado, o painel informa o motivo da atenção ou criticidade.

### Checklist operacional

O painel apresenta uma lista de verificação para apoiar a equipe antes da saída ou liberação.

Itens considerados:

- autorização do local;
- equipe responsável em campo;
- baterias;
- hélices;
- firmware;
- memória;
- link entre controle e drone;
- área de decolagem e pouso;
- pessoas, fios, árvores e obstáculos;
- coordenadas, referência visual e rota de acesso.

Quando o risco não está favorável, o checklist inclui uma recomendação de reavaliação da janela de voo.

### Histórico próximo

O painel busca OS cadastradas próximas ao endereço informado.

Critério atual:

- raio de até **1,5 km** do ponto consultado.

Para cada OS próxima, o painel pode apresentar:

- número da OS;
- distância aproximada;
- endereço;
- foco;
- tipo de operação;
- data de agendamento;
- UVIS;
- equipe;
- status.

Esse histórico ajuda a entender se já houve atendimento, recorrência ou demanda operacional na região.

### Recursos da operação

O painel também resume dados operacionais do sistema:

- drones ativos;
- drones em manutenção;
- baterias em alerta;
- veículos próximos da revisão;
- equipes ativas.

Essas informações ajudam o diretor a ter uma visão rápida da capacidade operacional antes de uma decisão.

---

## Fontes de dados

O Painel Operacional utiliza dados internos e externos.

### Dados externos

- **Google Maps / Geocoding:** usado para transformar o endereço em coordenadas.
- **Google Maps front-end:** usado para exibir o mapa no painel.
- **Open-Meteo:** usado para consultar o clima atual pela latitude e longitude.
- **Windy:** usado como link externo de apoio para análise de vento.

### Dados internos

O painel consulta informações já existentes no IJA System:

- solicitações cadastradas;
- drones;
- baterias;
- veículos;
- equipes;
- dados de prefeitura e região conforme o escopo do usuário.

---

## Regras de permissão e escopo

O acesso à tela é restrito aos tipos:

- `diretor`;
- `dev`.

As consultas internas respeitam o escopo aplicado ao usuário logado.

Isso significa que os dados de solicitações, prefeitura, região, drones, baterias, veículos e equipes seguem as mesmas regras de visibilidade usadas no restante do sistema.

---

## Comportamentos esperados

### Endereço válido

Quando o endereço é localizado corretamente:

- o mapa centraliza no ponto;
- as métricas climáticas são preenchidas;
- a decisão de risco é exibida;
- os recursos operacionais são atualizados;
- OS próximas são listadas quando existirem;
- links externos são habilitados.

### Endereço incompleto

Se o endereço tiver poucos caracteres ou estiver muito genérico, o sistema solicita um endereço mais completo.

Mensagem esperada:

`Informe um endereço mais completo para consultar.`

### Endereço não localizado

Se o Google Maps não encontrar o endereço, o painel informa que não foi possível localizar o ponto.

Mensagem esperada:

`Não foi possível localizar esse endereço.`

### Falha em serviço externo

Se houver falha temporária em mapas, geocodificação ou clima, o painel exibe erro de consulta.

Mensagem esperada:

`Não foi possível consultar o contexto local agora.`

---

## Benefícios operacionais

- Reduz o tempo de preparação antes de uma operação.
- Centraliza informações de clima, mapa e recursos em uma única tela.
- Ajuda a identificar risco por vento, chuva ou temperatura.
- Facilita a conferência de OS próximas ao ponto informado.
- Apoia a tomada de decisão do diretor.
- Melhora a comunicação entre gestão e equipe de campo.
- Evita que a equipe dependa de várias ferramentas abertas ao mesmo tempo.

---

## Exemplo de uso operacional

### Cenário

O diretor precisa avaliar se uma equipe pode ser deslocada para uma operação com drone em um endereço específico.

### Procedimento

1. Acessar **Painel Operacional**.
2. Digitar o endereço completo da operação.
3. Clicar em **Consultar**.
4. Conferir a **Decisão de voo**.
5. Verificar vento, rajada, chuva, temperatura e umidade.
6. Conferir se há OS próximas no raio de 1,5 km.
7. Avaliar drones, baterias, veículos e equipes disponíveis.
8. Abrir a rota ou o Windy, se necessário.
9. Decidir se a operação pode seguir, precisa de ajuste ou deve ser reagendada.

### Resultado esperado

O diretor recebe uma visão consolidada do ponto operacional e consegue orientar a equipe com mais segurança e agilidade.

---

## Limites da funcionalidade

O Painel Operacional é uma ferramenta de apoio.

Ele não substitui:

- avaliação técnica do piloto;
- regras internas de segurança;
- autorização do local;
- legislação aplicável;
- checagem física do ambiente;
- análise final da equipe responsável.

Dados climáticos podem variar rapidamente. Em operações sensíveis, recomenda-se confirmar as condições pouco antes do voo.

---

## Observações técnicas

Arquivos principais da funcionalidade:

- `app/modules/painel_operacional/routes.py`
- `app/modules/painel_operacional/service.py`
- `app/templates/painel_operacional.html`
- `app/templates/base.html`
- `app/shared/access.py`

Rotas principais:

- `GET /diretor/painel-operacional`
- `POST /api/painel-operacional/contexto-local`

Configurações esperadas para mapas:

- `Maps_KEY_FRONT`
- `Maps_KEY_BACK`
- `KEY_API_GOOGLE_MAPS`
- `GOOGLE_MAPS_KEY_BACK`

---

## Status

Funcionalidade implementada.

O Painel Operacional está disponível para usuários **diretor** e **dev**, com consulta de endereço, mapa, contexto climático, risco operacional, checklist, histórico próximo e resumo de recursos.

---

## Resumo executivo

O **Painel Operacional do Diretor** oferece uma visão rápida e consolidada de um endereço de operação.

A funcionalidade combina mapa, clima, risco, checklist, histórico de OS próximas e recursos disponíveis para apoiar decisões de campo, especialmente em operações com drones.

O diretor passa a ter uma ferramenta exclusiva para análise operacional, acima do acesso administrativo comum e abaixo do nível dev.
