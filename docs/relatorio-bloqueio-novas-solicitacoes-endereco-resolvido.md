# Relatório executivo e técnico: bloqueio de novas solicitações para endereço resolvido

**Data de referência:** 14 de agosto de 2026  
**Status da funcionalidade:** implementada  
**Área do sistema:** Ordens de Serviço / Cadastro de solicitações

## 1. Resumo executivo

Foi implementado um mecanismo que impede a criação de novas solicitações para um endereço cujo ciclo já tenha sido encerrado pelo piloto e cuja Ordem de Serviço esteja concluída.

A funcionalidade foi concebida para evitar duplicidade de demandas, deslocamentos desnecessários, repetição de voos e retrabalho em locais já atendidos. O piloto
 registra a decisão operacional no formulário da OS por meio da opção **“Encerrar Ciclo do Endereço (Bloquear novas solicitações)”**. Depois que a OS é concluída, o endereço passa a ser validado em todo novo cadastro realizado dentro da mesma prefeitura.

A proteção ocorre em duas camadas:

1. **prevenção na interface:** o sistema alerta o usuário durante o preenchimento e desabilita o envio quando reconhece um endereço bloqueado;
2. **validação obrigatória no backend:** antes de gravar qualquer nova solicitação, o servidor repete a verificação e rejeita o cadastro se houver bloqueio ativo.

Essa dupla validação garante que a regra continue válida mesmo se houver falha na interface, manipulação do navegador ou tentativa de envio direto da requisição.

## 2. Contexto e problema de negócio

Antes da trava, um endereço já atendido poderia receber uma nova solicitação porque o cadastro de demandas não considerava a decisão operacional registrada pelo piloto no encerramento da OS.

Essa situação poderia gerar:

- abertura duplicada para o mesmo local;
- novo deslocamento de equipe sem necessidade;
- repetição de voo ou monitoramento;
- consumo desnecessário de equipe, veículo, drone e insumos;
- divergência entre a situação observada em campo e a agenda administrativa;
- dificuldade para medir corretamente a quantidade de endereços ainda pendentes.

O bloqueio conecta o encerramento realizado em campo ao processo de entrada de novas solicitações. Assim, a informação deixa de ser apenas um registro da OS e passa a funcionar como uma regra preventiva no sistema.

## 3. Objetivos da funcionalidade

### 3.1. Objetivo principal

Impedir que o sistema aceite uma nova solicitação para o mesmo endereço depois que o piloto tiver encerrado o ciclo e a OS correspondente estiver concluída.

### 3.2. Objetivos específicos

- reduzir solicitações duplicadas;
- preservar a decisão operacional tomada em campo;
- evitar mobilização desnecessária de recursos;
- informar imediatamente ao solicitante que o endereço já foi concluído;
- garantir a aplicação da regra no servidor;
- permitir que diferentes formas de escrita do mesmo endereço sejam reconhecidas;
- manter a separação dos bloqueios por prefeitura.

## 4. Regra de ativação do bloqueio

O endereço somente bloqueia novos cadastros quando **as duas condições abaixo são verdadeiras ao mesmo tempo**:

1. a solicitação possui o campo `endereco_bloqueado` marcado como verdadeiro; e
2. o status da solicitação está como `CONCLUIDO` ou `CONCLUÍDO`.

Essa composição é importante. Apenas marcar a opção no formulário não bloqueia uma OS que ainda esteja em andamento. O bloqueio torna-se efetivo quando a solicitação também alcança o estado de conclusão.

Em termos simplificados:

```text
Endereço marcado para encerramento
  + OS concluída
  = novas solicitações bloqueadas
```

## 5. Ação do piloto no formulário da OS

No formulário operacional existe o campo **Status do Endereço**, com a opção:

> Encerrar Ciclo do Endereço (Bloquear novas solicitações)

O controle é apresentado ao piloto quando a situação da aplicação selecionada é uma das seguintes:

- `APENAS MONITORADO`;
- `NENHUM VOO REALIZADO`.

Se o piloto alterar a situação da aplicação para uma opção que não permite o encerramento, o controle é ocultado e a marcação é removida na interface.

Ao salvar o formulário, o valor escolhido é persistido na solicitação associada à OS. Depois que a OS é concluída, o registro passa a integrar a base consultada pelo mecanismo de bloqueio.

## 6. Fluxo operacional completo

```text
Piloto acessa a OS
  -> preenche a situação da aplicação
  -> sistema apresenta a opção de encerrar o ciclo, quando aplicável
  -> piloto marca o endereço para bloqueio
  -> formulário salva a decisão na solicitação
  -> OS é concluída
  -> bloqueio torna-se ativo
  -> usuário tenta cadastrar nova solicitação para o local
  -> sistema identifica o mesmo endereço
  -> interface exibe alerta e impede o envio
  -> backend confirma a regra antes da gravação
```

## 7. Identificação do mesmo endereço

O sistema utiliza duas estratégias complementares para reconhecer que o novo cadastro se refere a um endereço já resolvido.

### 7.1. Correspondência pelo Google Place ID

A primeira tentativa utiliza o `place_id`, identificador fornecido pelo serviço de geolocalização. Quando a nova solicitação e o registro concluído possuem o mesmo `place_id`, o endereço é considerado o mesmo.

Essa é a comparação prioritária porque utiliza um identificador geográfico estável, reduzindo ambiguidades causadas por abreviações ou diferenças de digitação.

### 7.2. Correspondência pelo endereço normalizado

Se o `place_id` não estiver disponível ou não localizar um bloqueio, o sistema compara os componentes textuais do endereço.

Antes da comparação, os valores são normalizados:

- conversão para letras minúsculas;
- remoção de acentos;
- remoção de pontuação e caracteres especiais;
- redução de espaços repetidos;
- remoção da formatação do CEP;
- padronização de abreviações comuns, como `R.` para `rua`, `Av.` para `avenida` e `Al.` para `alameda`.

Os campos obrigatórios para a correspondência são:

- logradouro;
- número;
- cidade;
- UF.

Esses quatro campos precisam ser iguais após a normalização. Bairro e CEP também são comparados quando estiverem preenchidos nos dois registros. Caso um deles esteja ausente em uma das partes, sua ausência não impede a correspondência.

O complemento não participa da chave de comparação. Assim, o bloqueio é aplicado ao endereço físico formado principalmente por via e número, e não apenas a um texto completo digitado de forma idêntica.

### 7.3. Exemplo de normalização

Os endereços abaixo podem ser reconhecidos como equivalentes:

```text
R. Hiroshima, 100 - Vila Maria Alta - São Paulo/SP
Rua Hiroshima, 100 - Vila Maria Alta - Sao Paulo/SP
```

O primeiro pode ter sido salvo sem `place_id`; ainda assim, a normalização permite localizar a OS concluída.

## 8. Escopo por prefeitura

O bloqueio é isolado por prefeitura. Um endereço marcado como resolvido em uma prefeitura não impede automaticamente um cadastro pertencente a outra prefeitura.

Para usuários administrativos que selecionam uma UVIS responsável no momento do cadastro, o sistema determina a prefeitura a partir da UVIS escolhida. Para um administrador de prefeitura, a seleção de uma UVIS de outra prefeitura não amplia o seu escopo.

Essa regra evita vazamento de informações e bloqueios indevidos entre organizações distintas que utilizam a mesma aplicação.

## 9. Validação preventiva na interface

Durante o cadastro de uma nova solicitação, o sistema geocodifica o endereço informado. Quando a geocodificação retorna um `place_id`, o navegador consulta o endpoint autenticado de verificação:

```text
GET /api/solicitacao/checar-bloqueio
```

A consulta envia o `place_id`, os componentes do endereço e, quando aplicável, a UVIS responsável. A resposta informa:

- se a consulta foi processada;
- se o endereço está bloqueado;
- o ID da solicitação/OS que originou o bloqueio;
- uma mensagem de contexto.

Quando existe bloqueio, a tela apresenta um alerta com a informação de que o endereço foi marcado como concluído pelo piloto e não aceita novas solicitações. O botão de envio é desabilitado.

Essa camada melhora a experiência do usuário porque evita que ele preencha e envie todo o formulário para somente depois descobrir a restrição.

## 10. Validação obrigatória no backend

A prevenção visual não é a única barreira. O serviço responsável por criar a solicitação consulta novamente os bloqueios imediatamente antes de inserir o novo registro no banco de dados.

Quando encontra um endereço bloqueado, o backend interrompe o cadastro e devolve uma mensagem de erro no formato:

```text
O endereço selecionado já foi concluído na OS #<id> e não aceita novas solicitações.
```

Nenhuma nova solicitação é gravada nesse cenário. Essa validação é essencial porque o JavaScript do navegador pode estar desativado, pode falhar ou pode ser contornado por uma chamada direta ao servidor.

## 11. Dados persistidos

A funcionalidade adicionou à entidade de solicitação o campo lógico:

```text
endereco_bloqueado: verdadeiro ou falso
```

O valor padrão é falso. Dessa forma, solicitações existentes ou novas OSs que não forem explicitamente marcadas continuam permitindo novos cadastros para o endereço.

A migração de banco adiciona a coluna como obrigatória e define valor padrão no servidor, evitando registros nulos durante a atualização da base.

O `place_id` já armazenado na solicitação possui índice e é utilizado como primeira referência de correspondência geográfica.

## 12. Perfis e responsabilidades

| Ator | Responsabilidade na funcionalidade |
| --- | --- |
| Piloto/equipe operacional | Avaliar a situação em campo e marcar o encerramento do ciclo quando o controle estiver disponível. |
| Usuário solicitante/UVIS | Receber o alerta e não abrir nova solicitação para o endereço encerrado. |
| Administração | Garantir o correto vínculo de prefeitura e orientar exceções operacionais. |
| Sistema | Persistir a decisão, identificar o mesmo endereço e rejeitar novos cadastros. |

## 13. Cenários de comportamento

### 13.1. Mesmo Place ID e mesma prefeitura

Se uma OS concluída está marcada para bloqueio e o novo cadastro possui o mesmo `place_id`, a solicitação é rejeitada.

### 13.2. Endereço equivalente sem Place ID anterior

Se a OS concluída não possui `place_id`, o sistema tenta reconhecer logradouro, número, cidade e UF normalizados. Abreviações e acentuação não impedem o bloqueio.

### 13.3. Mesmo Place ID em outra prefeitura

O cadastro é permitido, pois o bloqueio não atravessa o limite organizacional da prefeitura.

### 13.4. Endereço marcado, mas OS ainda não concluída

O cadastro não é bloqueado apenas pela marcação. A regra exige também o status concluído.

### 13.5. OS concluída sem marcação de encerramento

O endereço continua aceitando novas solicitações, porque a conclusão isolada não representa uma decisão de bloqueio.

### 13.6. Place ID diferente, mas endereço textual equivalente

O fallback por componentes normalizados ainda pode identificar o local e bloquear a solicitação.

## 14. Benefícios esperados

### 14.1. Eficiência operacional

- redução de deslocamentos desnecessários;
- menor risco de repetição de voos;
- melhor utilização das equipes e equipamentos;
- diminuição de cadastros duplicados.

### 14.2. Qualidade da informação

- conexão direta entre a conclusão de campo e a entrada de novas demandas;
- base de solicitações mais consistente;
- menor divergência entre realidade operacional e registros administrativos;
- identificação da OS responsável pelo bloqueio.

### 14.3. Governança

- decisão de encerramento registrada no sistema;
- aplicação automática e padronizada da regra;
- separação por prefeitura;
- validação no backend para evitar contorno da interface.

## 15. Validação e cobertura automatizada

A funcionalidade possui testes automatizados para os principais critérios de bloqueio:

- rejeição do mesmo `place_id` quando a OS está concluída e pertence à mesma prefeitura;
- rejeição pelo endereço normalizado quando o registro anterior não possui `place_id`;
- permissão do mesmo `place_id` quando o novo cadastro pertence a outra prefeitura;
- garantia de que a tentativa bloqueada não cria um novo registro no banco.

## 16. Componentes técnicos envolvidos

Os principais componentes são:

- `app/models.py`: campo `endereco_bloqueado` e armazenamento do `place_id`;
- `migrations/versions/3c86bbd26982_.py`: inclusão da coluna de bloqueio no banco;
- `app/templates/piloto_os_formulario.html`: controle utilizado pelo piloto;
- `app/modules/piloto_os/routes.py`: persistência da escolha no formulário da OS;
- `app/templates/cadastro.html`: consulta preventiva e alerta ao solicitante;
- `app/modules/solicitacoes/routes.py`: endpoint autenticado de consulta do bloqueio;
- `app/modules/solicitacoes/service.py`: normalização, busca e rejeição no cadastro;
- `tests/test_solicitacao_place_id_block.py`: testes automatizados das regras principais.

## 17. Controles de segurança e integridade

A implementação incorpora os seguintes controles:

- autenticação obrigatória no endpoint de consulta;
- validação definitiva no backend;
- isolamento por prefeitura;
- comparação por identificador geográfico e por endereço normalizado;
- referência à OS que originou o bloqueio na mensagem de rejeição;
- valor padrão falso para impedir bloqueios acidentais em registros legados.

## 18. Pontos de atenção e recomendações

### 18.1. Processo de desbloqueio

Não foi identificada uma tela administrativa dedicada para reabrir um endereço após a OS já estar concluída. Recomenda-se definir formalmente:

- quem pode autorizar a reabertura;
- em quais situações ela é permitida;
- qual justificativa deve ser registrada;
- como preservar o histórico do bloqueio e do desbloqueio.

### 18.2. Auditoria da decisão

Atualmente, o campo registra o estado do bloqueio, mas não possui campos específicos para data, hora, usuário e justificativa da marcação. Como evolução de governança, recomenda-se armazenar:

- data e hora do encerramento do endereço;
- usuário responsável;
- motivo ou observação;
- data e responsável por eventual desbloqueio.

### 18.3. Desempenho da comparação textual

A busca alternativa analisa até os 300 bloqueios mais recentes do escopo quando não encontra correspondência por `place_id`. Esse limite protege o desempenho, mas pode deixar de localizar um bloqueio textual mais antigo em uma base muito grande.

Como evolução, recomenda-se persistir uma chave normalizada e indexada do endereço, permitindo comparação direta no banco de dados.

### 18.4. Cadastros simultâneos

A regra é validada antes da inserção, mas não existe uma restrição única de banco baseada no endereço normalizado. Em um cenário raro de requisições simultâneas para o mesmo local, duas tentativas podem ser avaliadas antes que uma delas seja gravada.

Uma chave de endereço controlada em banco ou uma estratégia transacional específica pode reforçar essa proteção caso o volume de cadastros simultâneos aumente.

### 18.5. Comunicação operacional

Recomenda-se orientar os pilotos sobre o significado da marcação. O endereço não deve ser encerrado apenas porque uma visita terminou; a opção deve representar a decisão de que novas solicitações para aquele local não devem ser aceitas dentro do fluxo vigente.

## 19. Indicadores recomendados para gestão

Para medir o impacto da funcionalidade, podem ser acompanhados:

| Indicador | Finalidade |
| --- | --- |
| Quantidade de endereços bloqueados | Dimensionar o volume de ciclos encerrados. |
| Tentativas de cadastro impedidas | Medir duplicidades evitadas. |
| Bloqueios por piloto/equipe | Acompanhar uso e necessidade de orientação. |
| Solicitações reabertas por exceção | Avaliar a qualidade das decisões de encerramento. |
| Economia estimada de deslocamentos | Demonstrar impacto operacional e financeiro. |

Os dois primeiros indicadores exigiriam registro histórico das tentativas e eventos de bloqueio para uma medição completa.

## 20. Conclusão

O bloqueio de novas solicitações para endereços resolvidos integra a decisão do piloto ao controle administrativo de entrada de demandas. A funcionalidade reduz duplicidade, retrabalho e uso desnecessário de recursos, ao mesmo tempo em que mantém a regra limitada ao escopo correto de prefeitura.

A arquitetura em duas camadas — aviso preventivo na interface e validação obrigatória no backend — oferece uma proteção consistente. A comparação pelo Google Place ID, complementada pela normalização do endereço, amplia a capacidade de reconhecer o mesmo local mesmo quando os dados foram digitados de formas diferentes.

Como próximos passos de maturidade, os maiores ganhos virão da criação de uma trilha de auditoria, de um processo formal de desbloqueio e de uma chave normalizada e indexada para endereços. A funcionalidade atual, entretanto, já atende ao objetivo central de impedir novas demandas para locais que foram oficialmente encerrados no fluxo operacional.
