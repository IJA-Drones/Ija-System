# Aprender na prática com a Azul

O botão **Guia prático** do menu e da Azul abre um modal com a identidade visual
**Aprenda fazendo, com Azul**. Os cartões são organizados por módulo, com filtros
para Prefeitura, Agro, Financeiro e Sistema, conforme o acesso da conta.

1. Escolha um módulo, como Solicitações, Clientes Agro ou Contas.
2. Escolha a função, como Nova solicitação, Cadastrar cliente ou Contas a pagar.
3. O sistema abre a tela correspondente. A Azul usa os rótulos e controles
   disponíveis nessa tela para gerar o tutorial pela integração de IA existente.
4. Use **Próximo**, **Voltar** ou **Ver todas as etapas**. **Ouvir etapa** solicita
   a narração pela voz configurada da Azul.
5. Escreva uma dúvida em **Perguntar à Azul** para continuar o tutorial. Se o
   formulário mudar, **Atualizar etapas com a Azul** gera um plano atualizado.
6. **Escolher outro tutorial** retorna aos cartões. Escape ou o botão de fechar
   encerra o guia e interrompe a requisição e a reprodução no navegador.

A interface usa as telas reais. As ações da página continuam disponíveis para
revisão e confirmação pelo usuário. O guia não preenche ou confirma formulários.

## Perfis, módulos e funções

`app/modules/chatbot/practical.py` monta o catálogo a partir da navegação
`SCREENS`, dos guards legados revisados e das permissões atuais da Central de TI.
A função escolhida é novamente autorizada em cada chamada de IA. Perfis de UVIS
recebem as funções municipais permitidas; os guias de piloto, Agro e Financeiro
seguem seus respectivos módulos. A permissão de usar a Azul também é necessária.

No navegador, controles ocultos, desabilitados ou bloqueados são ignorados.
Campos independentes expressamente liberados em formulários bloqueados seguem
`permission-controls.js`. Campos condicionais são considerados quando visíveis.
A geração de outro plano depende de um novo clique explícito.

## IA, voz e dados

O tutorial usa `/api/azul/ajuda` com a intenção `practical_guide`, preservando
login, CSRF, vínculo da sessão, configurações, limites, orçamento e medição da Azul.
O provedor recebe apenas os rótulos e orientações dos controles, o contexto
permitido e as dúvidas digitadas no próprio guia. Os valores preenchidos nos
formulários, senhas, anexos e registros da tabela não entram nesse retrato da tela.

A resposta estruturada é validada: etapas precisam usar IDs dos controles
recebidos. A IA não fornece seletores, URLs navegáveis ou comandos executáveis.
O tutorial não disponibiliza ferramentas de consulta ou alteração de registros.
Falhas do provedor são apresentadas com opção de tentar novamente.

A voz usa as ofertas assinadas e as configurações de áudio já existentes.
A geração de texto ocorre ao escolher uma função, atualizar etapas ou perguntar;
a narração ocorre ao clicar em ouvir. Apenas abrir ou pesquisar os cartões não
consome IA. Um marcador temporário de sessão permite iniciar após a navegação;
ele é consumido uma vez para evitar nova geração silenciosa ao recarregar a página.

## Integração e verificação

`inventario-guia-pratico.json` registra os templates que carregam o componente e
os identificadores de perfil. Execute `python scripts/inventory_screen_guides.py`
para atualizá-lo. A lista de funções depende das entradas de navegação e das
permissões, e não da contagem de templates. Ao acrescentar uma função, registre
sua navegação e verifique o guard legado e a política da Central de TI.

Os testes de servidor usam SQLite descartável e provedor simulado; não alteram
Neon ou Render. Cobrem isolamento entre módulos, remoção de permissão da Azul,
chamada à integração de IA sem ferramentas operacionais, validação dos controles
e tratamento explícito de falhas. O navegador é conferido com respostas simuladas
sem custo, incluindo cartões, escolha de função, navegação, dúvidas, narração
opcional, celular, cancelamento e preservação dos valores do formulário.

A sala anterior em `/azul/tutorial` permanece disponível para os exercícios
simulados legados. As páginas públicas e o aplicativo público preservam seu guia
contextual atual; os tutoriais por módulo com IA pertencem ao ambiente autenticado.
