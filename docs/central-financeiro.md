# Central Financeiro — estrutura inicial

## Objetivo e escopo

A central reúne empresas, cada uma identificada pelo CNPJ, e permite abrir o ambiente financeiro da empresa selecionada. É uma área própria dentro da aplicação Flask existente, ao lado de Prefeitura e Agro. A organização por empresa segue a ideia de aplicativos por CNPJ apresentada na [documentação do Omie](https://ajuda.omie.com.br/pt-BR/articles/5409954-compartilhamento-de-cadastros-entre-aplicativos), usando os componentes e as cores do IJA System.

Nesta entrega, o catálogo contém apenas a IJA, com o CNPJ fictício `11.111.111/0001-11`, explicitamente identificado como demonstração. A lista e o ambiente recebem dados de empresa; não estão limitados visualmente à IJA. Os testes verificam também a renderização de duas empresas simuladas.

O cadastro de empresas ainda não foi implementado. O botão **Cadastrar empresa**, desativado e marcado como **Em breve**, aparece apenas para `financeiro_admin`. Esse perfil será responsável pelo cadastro e pela configuração das empresas quando a função for desenvolvida. Os demais perfis não recebem esse controle.

Não foram criados modelos, tabelas, migrações ou registros em banco. Nenhum banco Neon foi acessado. Os recursos financeiros existentes no Agro continuam nas rotas atuais; não foram transferidos nem tiveram seu escopo de dados alterado.

## Navegação e permissões

1. No menu do usuário, selecionar **Financeiro**. Há também um acesso **Central Financeiro** no menu lateral dos perfis habilitados.
2. Em `/financeiro`, buscar uma empresa pelo nome ou CNPJ e selecionar **Acessar empresa**.
3. Em `/financeiro/empresas/ija`, conferir a identificação da empresa e a **Visão geral**. O ambiente está vazio nesta etapa: não há saldos, lançamentos ou abas financeiras operacionais.
4. Usar **Trocar empresa** para voltar ao catálogo.

| Perfil | Central | Ambiente demonstrativo da IJA | Cadastro/configuração |
| --- | --- | --- | --- |
| `financeiro_admin` | Sim | Com o vínculo `trabalha_agro` atual | Responsável; função ainda desativada |
| `financeiro` | Sim | Com o vínculo `trabalha_agro` atual | Não |
| `admin`, `diretor`, `dev` | Sim | Com o vínculo `trabalha_agro` atual | Não nesta central |
| Demais perfis | Não | Não | Não |

O login e a rota raiz dos perfis financeiros passam a abrir a central. Os destinos dos demais perfis são preservados. O seletor do menu mantém Agro disponível para quem já tem esse vínculo.

## Segurança e funcionamento

As duas páginas exigem autenticação e autorização no servidor, inclusive quando a URL é digitada diretamente. Empresa inexistente retorna 404; usuário sem permissão retorna 403. A identidade exibida usa o escape de HTML dos templates. As respostas do Financeiro usam `Cache-Control: private, no-store`.

A empresa é resolvida a cada requisição pela URL e pelo catálogo autorizado; não é gravada como seleção global na sessão. Isso evita que a escolha de empresa em uma aba troque o contexto de outra aba. A busca e o filtro funcionam no navegador, sem consultas adicionais ao servidor. A central pula os contadores dos menus operacionais e o carregamento do Google Maps, que não são usados nesse ambiente.

Não existe persistência ou isolamento de lançamentos por empresa nesta etapa, pois os novos módulos financeiros ainda não foram implementados. Para a próxima etapa, a empresa deverá ter um identificador interno associado a um CNPJ válido e único. Cada consulta e alteração deverá conferir o vínculo do usuário com essa empresa e filtrar pelo identificador interno. O CNPJ identifica a empresa; conhecer um CNPJ ou alterar uma URL não concede autorização.

As futuras abas e configurações deverão manter a empresa e o CNPJ visíveis, aplicar autorização no servidor e proteger as operações de escrita com o mecanismo de CSRF existente. Cadastro, atribuição de acesso e migração dos dados financeiros exigem implementação e validação próprias; o botão desativado não substitui essas regras.

## Como verificar

```bash
DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q tests/test_financeiro_central.py
node --test tests/financeiro_central_browser.test.cjs
.venv/bin/python scripts/build_css_bundle.py --check
```

Os testes da central usam uma aplicação isolada sem conexão de banco. Verificam permissões, navegação, a ausência de escrita e de seleção global na sessão, o cadastro reservado ao administrador financeiro, múltiplas empresas simuladas e escape de HTML. Os testes JavaScript usam DOM simulado e verificam busca por nome/CNPJ, filtro e estado vazio.

No navegador, conferir tema claro/escuro, celular, busca sem resultado, entrada na IJA e retorno ao catálogo. Após publicação, repetir esse percurso com um usuário real de homologação; a prévia visual local usa um usuário fictício e não valida integrações de produção.
