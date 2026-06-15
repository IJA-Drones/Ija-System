# Banco de Talentos Agro com Inteligência Artificial

## Visão geral

O **Banco de Talentos Agro** é uma nova funcionalidade do IJA System destinada à organização, consulta e acompanhamento de currículos recebidos para oportunidades relacionadas à operação Agro.

A solução reúne, em um único ambiente:

- armazenamento dos currículos em PDF;
- leitura automatizada dos documentos;
- criação de perfis profissionais estruturados;
- identificação de experiências, formações e habilidades;
- indicação de possíveis áreas de atuação e desenvolvimento;
- pesquisa rápida de candidatos;
- acompanhamento das etapas administrativas de cada perfil.

O objetivo é transformar currículos que antes ficavam dispersos em arquivos, e-mails ou pastas em uma base centralizada, pesquisável e mais útil para decisões administrativas.

---

## Objetivo da funcionalidade

O Banco de Talentos foi criado para apoiar a administração na formação de uma base organizada de profissionais que possam atender às necessidades atuais ou futuras da área Agro.

Com essa funcionalidade, a empresa passa a ter maior facilidade para:

- localizar profissionais com conhecimentos específicos;
- consultar candidatos já recebidos anteriormente;
- reduzir o tempo utilizado na leitura inicial dos currículos;
- acompanhar o andamento de cada candidato;
- identificar perfis aderentes às atividades administrativas, técnicas e operacionais;
- preservar o histórico de talentos para futuras oportunidades;
- apoiar o planejamento de contratação e formação de equipes.

---

## Onde acessar

O acesso é realizado dentro do módulo **Agro**:

1. Acesse o **Painel Agro**.
2. Selecione **Banco de Talentos**.
3. Para cadastrar um novo currículo, clique em **Enviar currículo**.

Por envolver dados pessoais e profissionais, o Banco de Talentos é destinado aos perfis administrativos autorizados. Usuários com acesso exclusivamente financeiro não visualizam essa área.

---

## Como funciona o processo

### 1. Recebimento do currículo

O responsável administrativo recebe o currículo do candidato e acessa a opção **Enviar currículo**.

O documento deve estar no formato **PDF**, com tamanho máximo de **20 MB**.

### 2. Validação do arquivo

Antes do processamento, o sistema verifica:

- se o arquivo foi realmente enviado;
- se está no formato PDF;
- se o documento não está vazio;
- se respeita o limite de tamanho;
- se o mesmo arquivo já foi cadastrado anteriormente.

Essa validação reduz duplicidades e evita o armazenamento de documentos inválidos.

### 3. Armazenamento no Dropbox

Após a validação, o PDF é armazenado no Dropbox em uma estrutura privada e organizada.

O sistema registra no banco de dados as informações necessárias para localizar o arquivo, incluindo:

- nome original;
- tamanho;
- identificação digital do documento;
- caminho de armazenamento;
- data de cadastro;
- usuário responsável pelo envio.

O PDF não fica exposto por um endereço público. A consulta ocorre por meio do próprio sistema e respeita as permissões de acesso.

### 4. Leitura pela Inteligência Artificial

Depois do armazenamento, o sistema envia o conteúdo do PDF ao **Gemini**, que realiza a leitura do currículo.

A IA organiza as informações profissionais encontradas no documento e devolve os dados em uma estrutura padronizada.

### 5. Criação do perfil profissional

Com base na leitura, o sistema cria o perfil do candidato, que pode conter:

- nome;
- e-mail;
- telefone;
- cidade e estado;
- endereço do LinkedIn, quando informado;
- título profissional;
- área profissional principal;
- resumo do perfil;
- objetivo profissional;
- experiências;
- formação acadêmica;
- certificações;
- idiomas;
- habilidades técnicas;
- habilidades comportamentais;
- áreas de atuação;
- possíveis caminhos de especialização ou desenvolvimento.

### 6. Revisão administrativa

O perfil gerado fica disponível para consulta no Banco de Talentos.

O responsável pode comparar o resumo produzido pela IA com o PDF original, que permanece disponível na tela do candidato.

A revisão humana continua sendo necessária, pois a IA atua como ferramenta de apoio à organização e à análise inicial.

### 7. Acompanhamento do candidato

Cada candidato pode ser classificado em uma etapa administrativa:

- **Novo:** currículo recebido e disponível para triagem;
- **Em análise:** perfil em avaliação pela equipe;
- **Entrevista:** candidato direcionado para conversa ou processo seletivo;
- **Aprovado:** candidato aprovado para a finalidade avaliada;
- **Arquivado:** perfil mantido para histórico ou oportunidades futuras.

Também existe um campo de **observações internas**, destinado ao registro de informações administrativas relevantes para o acompanhamento.

---

## Como a Inteligência Artificial ajuda

A IA não substitui a decisão administrativa. Sua função é reduzir atividades repetitivas e transformar o conteúdo dos currículos em informações mais fáceis de consultar.

### Leitura automatizada

O Gemini lê o PDF e identifica os principais dados profissionais sem exigir que o responsável transcreva manualmente cada informação.

### Padronização dos perfis

Currículos possuem formatos, estilos e níveis de detalhamento diferentes. A IA organiza esse conteúdo em campos padronizados, facilitando a comparação entre candidatos.

### Resumo profissional

O sistema gera uma síntese do histórico, da formação e das competências apresentadas no documento. Isso permite uma triagem inicial mais rápida.

### Identificação de habilidades

A IA separa as habilidades em grupos, como:

- conhecimentos técnicos;
- competências comportamentais;
- áreas de atuação;
- certificações;
- idiomas.

### Indicação de possibilidades de desenvolvimento

Com base nas experiências e formações descritas no currículo, a IA pode indicar áreas coerentes para especialização ou desenvolvimento profissional.

Essas indicações não significam que o candidato já possui a especialização. Elas servem como referência para planejamento, capacitação ou avaliação de potencial.

### Facilidade de pesquisa

Depois que as informações são estruturadas, a administração pode localizar candidatos por:

- nome;
- área profissional;
- formação;
- habilidade;
- contato;
- resumo;
- área de atuação;
- possibilidade de especialização.

---

## Benefícios administrativos

### Centralização das informações

Os currículos deixam de depender de caixas de e-mail, computadores individuais ou pastas sem padronização.

### Redução de trabalho manual

A leitura inicial e a transcrição de informações são realizadas automaticamente, reduzindo tempo operacional da equipe administrativa.

### Agilidade na triagem

O resumo e as habilidades em destaque permitem compreender rapidamente o perfil antes da leitura integral do documento.

### Formação de uma base permanente

Mesmo quando não há uma vaga imediata, o perfil pode ser mantido para futuras demandas, reduzindo a necessidade de reiniciar buscas do zero.

### Apoio ao planejamento de equipes

A base permite identificar a disponibilidade de conhecimentos relacionados às necessidades do Agro, apoiando contratações, substituições, expansão e composição de equipes.

### Melhor aproveitamento dos currículos recebidos

Um candidato que não atende a uma necessidade atual pode possuir competências úteis para outra área ou oportunidade futura.

### Rastreabilidade

O sistema registra o documento, o momento do cadastro, o usuário responsável e a etapa administrativa do candidato.

---

## Exemplo de uso administrativo

### Cenário

A gestão precisa localizar profissionais com experiência em agricultura de precisão, elaboração de relatórios e uso de ferramentas de análise de dados.

### Procedimento

1. Acesse o **Banco de Talentos**.
2. Utilize o campo **Busca geral**.
3. Pesquise por termos como:
   - `agricultura de precisão`;
   - `Power BI`;
   - `relatórios`;
   - `operações agrícolas`.
4. Consulte os candidatos apresentados.
5. Abra o perfil para analisar:
   - resumo profissional;
   - experiências;
   - formação;
   - habilidades;
   - possíveis especializações;
   - currículo original em PDF.
6. Atualize a etapa do candidato conforme o andamento da avaliação.
7. Registre observações internas quando necessário.

### Resultado esperado

A gestão encontra rapidamente os perfis relacionados à necessidade, reduzindo o tempo de procura e aproveitando melhor os currículos já disponíveis.

---

## Situações de processamento

A leitura do currículo pode apresentar os seguintes estados:

- **Processando:** o documento está sendo analisado;
- **Concluída:** o perfil foi criado com sucesso;
- **Erro:** o PDF foi armazenado, mas a leitura automática não foi concluída.

Quando ocorrer um erro, o documento não é perdido. O usuário autorizado pode utilizar a opção **Reprocessar IA** para realizar uma nova tentativa.

---

## Atualização e reprocessamento

O reprocessamento pode ser utilizado quando:

- a análise inicial apresentar erro;
- houver necessidade de tentar uma nova leitura;
- o processamento anterior não tiver sido concluído.

Ao reprocessar, o sistema recupera o PDF armazenado no Dropbox e solicita uma nova análise ao Gemini.

---

## Exclusão de candidatos

Usuários autorizados podem excluir um candidato do Banco de Talentos.

Esse procedimento remove:

- o perfil estruturado do banco de dados;
- as observações administrativas;
- o PDF armazenado no Dropbox.

A exclusão é permanente e deve ser realizada somente quando houver segurança de que o registro não precisa mais ser mantido.

---

## Segurança e uso responsável

O Banco de Talentos trabalha com dados pessoais e profissionais. Por isso, o uso deve seguir critérios de necessidade, confidencialidade e responsabilidade.

### Controle de acesso

A consulta é restrita aos usuários administrativos autorizados e respeita o escopo de cada prefeitura quando aplicável.

### Arquivo privado

O currículo é armazenado no Dropbox sem exposição por link público.

### Proteção contra duplicidade

O sistema utiliza uma identificação digital do arquivo para evitar o cadastro repetido do mesmo PDF dentro do mesmo escopo.

### Limites da análise

A IA é orientada a:

- utilizar somente informações presentes no currículo;
- não inventar experiências, cursos, empregadores ou habilidades;
- não atribuir nota ou classificação ao candidato;
- não tomar decisões de contratação;
- não inferir dados pessoais sensíveis;
- tratar sugestões de especialização como possibilidades de desenvolvimento.

### Revisão humana obrigatória

O perfil gerado deve ser entendido como um apoio administrativo.

Decisões relacionadas a entrevista, aprovação, contratação ou eliminação de candidatos devem permanecer sob responsabilidade das pessoas designadas pela organização.

---

## Boas práticas administrativas

- Verifique se o PDF está legível antes do envio.
- Consulte o currículo original antes de tomar decisões.
- Utilize observações objetivas e profissionais.
- Evite registrar opiniões discriminatórias ou informações pessoais desnecessárias.
- Atualize a etapa do candidato sempre que houver mudança no processo.
- Não compartilhe currículos fora dos canais autorizados.
- Exclua registros apenas conforme as políticas internas de retenção de dados.
- Trate as possíveis especializações indicadas pela IA como sugestões, não como qualificações comprovadas.

---

## Responsabilidades

### Responsabilidade do sistema

- armazenar o PDF;
- organizar os dados extraídos;
- disponibilizar busca e acompanhamento;
- registrar falhas de processamento;
- permitir nova tentativa de análise;
- respeitar as permissões configuradas.

### Responsabilidade da Inteligência Artificial

- ler o conteúdo profissional;
- estruturar as informações;
- produzir um resumo;
- identificar habilidades e áreas relacionadas;
- apresentar possibilidades coerentes de desenvolvimento.

### Responsabilidade da equipe administrativa

- confirmar a veracidade das informações no documento original;
- avaliar o candidato dentro dos critérios da organização;
- manter o acompanhamento atualizado;
- proteger os dados pessoais;
- realizar a decisão final.

---

## Perguntas frequentes

### A IA escolhe quem deve ser contratado?

Não. A IA apenas organiza e resume as informações do currículo. A decisão é exclusivamente humana.

### O currículo fica salvo mesmo se a IA apresentar erro?

Sim. O PDF permanece armazenado no Dropbox e pode ser reprocessado.

### É possível consultar o documento original?

Sim. A tela do candidato possui a opção **Abrir PDF**.

### A IA pode criar informações que não estão no currículo?

Ela é instruída a não inventar informações. Ainda assim, toda análise automatizada deve ser conferida por uma pessoa responsável.

### O sistema identifica possíveis especializações?

Sim. A IA pode sugerir caminhos de desenvolvimento coerentes com a formação e as experiências apresentadas. Essas sugestões não representam competências já comprovadas.

### É possível pesquisar por habilidade?

Sim. A busca considera informações como nome, área, formação, resumo, habilidades e possíveis áreas de desenvolvimento.

### Quem pode acessar o Banco de Talentos?

Os perfis administrativos autorizados dentro do módulo Agro. Usuários exclusivamente financeiros não possuem acesso.

---

## Resumo executivo

O **Banco de Talentos Agro** centraliza currículos, protege os documentos no Dropbox e utiliza o Gemini para transformar PDFs em perfis profissionais organizados.

A funcionalidade reduz tarefas manuais, agiliza a triagem, melhora a pesquisa de competências e preserva uma base de profissionais para demandas atuais e futuras.

A Inteligência Artificial atua como apoio à leitura e à organização das informações. A validação dos dados e todas as decisões administrativas permanecem sob responsabilidade humana.
